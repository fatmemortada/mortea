"""
AI Compliance Risk Detection views.

Scan entities for risks, view findings, resolve issues,
and generate bulk portfolio reports.
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Count, Sum

from ..models import (
    Client, Firm, CorporateProfile, Director, Shareholder, AnnualFiling,
    ComplianceTask, UBORecord, EntityRegistration, RiskScan, RiskFinding,
    BulkRiskScan, log_activity,
)
from ._helpers import _get_firm


@login_required
def risk_dashboard(request):
    """Main risk dashboard showing all entity risk scores and findings."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    clients = Client.objects.filter(firm=firm)

    # Latest scan per client (SQLite-compatible — Python dedup)
    all_scans = RiskScan.objects.filter(
        client__firm=firm, status='completed'
    ).order_by('-created_at').select_related('client')
    seen = set()
    scans = []
    for scan in all_scans:
        if scan.client_id not in seen:
            seen.add(scan.client_id)
            scans.append(scan)

    total_findings = RiskFinding.objects.filter(
        client__firm=firm, is_resolved=False
    ).count()
    critical = RiskFinding.objects.filter(
        client__firm=firm, severity='critical', is_resolved=False
    ).count()
    high = RiskFinding.objects.filter(
        client__firm=firm, severity='high', is_resolved=False
    ).count()

    # Clients at risk
    at_risk_clients = []
    for scan in scans:
        if scan.overall_score < 70:
            at_risk_clients.append({
                'client': scan.client,
                'score': scan.overall_score,
                'critical': scan.critical_count,
                'high': scan.high_count,
                'scanned_at': scan.created_at,
            })

    at_risk_clients.sort(key=lambda x: x['score'])

    # Recent findings
    recent_findings = RiskFinding.objects.filter(
        client__firm=firm, is_resolved=False
    ).select_related('client', 'scan').order_by('-severity', '-created_at')[:50]

    # Category breakdown
    by_category = RiskFinding.objects.filter(
        client__firm=firm, is_resolved=False
    ).values('category').annotate(count=Count('id')).order_by('-count')

    return render(request, 'clients/risk_dashboard.html', {
        'firm': firm, 'clients': clients, 'scans': scans,
        'total_findings': total_findings, 'critical': critical, 'high': high,
        'at_risk_clients': at_risk_clients, 'recent_findings': recent_findings,
        'by_category': by_category,
    })


@login_required
def run_risk_scan(request, client_id):
    """Run an AI-powered risk scan on a specific entity."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    client = get_object_or_404(Client, id=client_id, firm=firm)

    if request.method == 'POST':
        import time
        start_time = time.time()

        # Create scan
        scan = RiskScan.objects.create(
            client=client,
            requested_by=request.user,
            status='scanning',
        )

        # Run detection logic
        findings = _detect_entity_risks(client)

        # Count categories
        critical_count = sum(1 for f in findings if f['severity'] == 'critical')
        high_count = sum(1 for f in findings if f['severity'] == 'high')
        medium_count = sum(1 for f in findings if f['severity'] == 'medium')
        low_count = sum(1 for f in findings if f['severity'] == 'low')

        # Calculate score (0-100, 100 = perfect)
        penalty = critical_count * 25 + high_count * 10 + medium_count * 4 + low_count * 1
        score = max(0, 100 - penalty)

        # Create finding records
        for f_data in findings:
            RiskFinding.objects.create(
                scan=scan,
                client=client,
                severity=f_data['severity'],
                category=f_data['category'],
                title=f_data['title'],
                description=f_data['description'],
                detail=f_data.get('detail', {}),
                remediation=f_data.get('remediation', ''),
                estimated_hours=f_data.get('estimated_hours', 0),
                estimated_cost=f_data.get('estimated_cost', 0),
                ai_confidence=f_data.get('confidence', 0.85),
            )

        # Update scan
        scan.status = 'completed'
        scan.total_findings = len(findings)
        scan.critical_count = critical_count
        scan.high_count = high_count
        scan.medium_count = medium_count
        scan.low_count = low_count
        scan.overall_score = score
        scan.scan_duration_ms = int((time.time() - start_time) * 1000)
        scan.save()

        log_activity(client, f'Risk scan completed — score {score}, {len(findings)} findings', request.user)
        messages.success(request, f'Risk scan complete! Score: {score}/100, {len(findings)} findings.')

        return redirect('risk_scan_results', scan_id=scan.id)

    return render(request, 'clients/risk_scan_confirm.html', {
        'firm': firm, 'client': client,
    })


@login_required
def risk_scan_results(request, scan_id):
    """View results of a specific risk scan."""
    firm = _get_firm(request.user)
    scan = get_object_or_404(RiskScan, id=scan_id, client__firm=firm)
    findings = scan.findings.all().order_by('-severity', '-ai_confidence')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'resolve':
            finding_id = request.POST.get('finding_id')
            finding = findings.filter(id=finding_id).first()
            if finding:
                finding.resolve(user=request.user, notes=request.POST.get('notes', ''))
                log_activity(scan.client, f'Resolved risk: {finding.title}', request.user)
                messages.success(request, f'Risk "{finding.title}" resolved.')
        elif action == 'resolve_all_low':
            resolved = findings.filter(severity='low', is_resolved=False)
            count = resolved.count()
            for f in resolved:
                f.resolve(user=request.user)
            messages.success(request, f'Resolved {count} low-severity findings.')
        elif action == 'generate_remediation':
            return redirect('create_remediation_from_scan', scan_id=scan.id)

        return redirect('risk_scan_results', scan_id=scan.id)

    return render(request, 'clients/risk_scan_results.html', {
        'firm': firm, 'scan': scan, 'findings': findings,
    })


@login_required
def bulk_risk_scan(request):
    """Run risk scans across multiple entities at once."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if request.method == 'POST':
        client_ids = request.POST.getlist('client_ids')
        if not client_ids:
            messages.error(request, 'Please select at least one entity.')
            return redirect('risk_dashboard')

        clients = Client.objects.filter(id__in=client_ids, firm=firm)

        bulk = BulkRiskScan.objects.create(
            firm=firm,
            requested_by=request.user,
            status='scanning',
            total_clients=clients.count(),
        )

        total_findings = 0
        total_critical = 0
        total_high = 0
        scores = []

        for client in clients:
            scan = RiskScan.objects.create(client=client, requested_by=request.user, status='scanning')
            findings = _detect_entity_risks(client)

            critical = sum(1 for f in findings if f['severity'] == 'critical')
            high = sum(1 for f in findings if f['severity'] == 'high')
            medium = sum(1 for f in findings if f['severity'] == 'medium')
            low = sum(1 for f in findings if f['severity'] == 'low')
            penalty = critical * 25 + high * 10 + medium * 4 + low * 1
            score = max(0, 100 - penalty)

            for f_data in findings:
                RiskFinding.objects.create(
                    scan=scan, client=client,
                    severity=f_data['severity'], category=f_data['category'],
                    title=f_data['title'], description=f_data['description'],
                    detail=f_data.get('detail', {}),
                    remediation=f_data.get('remediation', ''),
                    estimated_hours=f_data.get('estimated_hours', 0),
                    estimated_cost=f_data.get('estimated_cost', 0),
                    ai_confidence=f_data.get('confidence', 0.85),
                )

            scan.status = 'completed'
            scan.total_findings = len(findings)
            scan.critical_count = critical
            scan.high_count = high
            scan.overall_score = score
            scan.save()

            total_findings += len(findings)
            total_critical += critical
            total_high += high
            scores.append(score)
            bulk.scanned_clients += 1
            bulk.save()

        bulk.status = 'completed'
        bulk.total_findings = total_findings
        bulk.critical_count = total_critical
        bulk.high_count = total_high
        bulk.average_score = int(sum(scores) / max(len(scores), 1))
        bulk.completed_at = timezone.now()
        bulk.save()

        log_activity(None, f'Bulk risk scan: {clients.count()} entities, {total_findings} findings', request.user)
        messages.success(request, f'Bulk scan complete! {clients.count()} entities, {total_findings} findings.')

        return redirect('risk_dashboard')

    clients = Client.objects.filter(firm=firm)
    return render(request, 'clients/bulk_risk_scan.html', {
        'firm': firm, 'clients': clients,
    })


def _detect_entity_risks(client):
    """
    Core detection engine — check entity records for anomalies.
    Returns a list of risk finding dicts.
    """
    findings = []
    today = timezone.now().date()

    profile = getattr(client, 'corporate_profile', None)
    directors = list(client.directors.all())
    shareholders = list(client.shareholders.all())
    tasks = list(client.compliance_tasks.all())
    filings = list(client.annual_filings.all())

    # 1. Director checks
    active_directors = [d for d in directors if d.is_active]
    resigned_directors = [d for d in directors if not d.is_active]

    if not active_directors:
        findings.append({
            'severity': 'critical', 'category': 'directors',
            'title': 'No active directors',
            'description': 'This entity has no active directors. Every corporation must have at least one director.',
            'remediation': 'Appoint at least one director and file Form 6 (Changes Regarding Directors) with the registry.',
            'estimated_hours': 0.5, 'estimated_cost': 100, 'confidence': 0.99,
        })
    elif profile:
        min_dirs = 1
        if profile.jurisdiction == 'federal' and getattr(profile, 'is_distributing', False):
            min_dirs = 3
        if len(active_directors) < min_dirs:
            findings.append({
                'severity': 'critical', 'category': 'directors',
                'title': f'Less than {min_dirs} active director(s)',
                'description': f'Only {len(active_directors)} active director(s). {profile.get_jurisdiction_display()} requires at least {min_dirs}.',
                'remediation': f'Appoint additional director(s) to meet the {min_dirs}-director minimum.',
                'estimated_hours': 1, 'estimated_cost': 200, 'confidence': 0.95,
            })

    # Check for directors with missing consent
    for d in active_directors:
        if not d.appointment_date:
            findings.append({
                'severity': 'medium', 'category': 'directors',
                'title': f'Missing appointment date for director {d.full_name}',
                'description': 'Director appointment date not recorded. Consent to act may be missing.',
                'remediation': 'Obtain and file signed Consent to Act as Director.',
                'detail': {'director_id': d.id, 'director_name': d.full_name},
                'estimated_hours': 0.25, 'estimated_cost': 0, 'confidence': 0.9,
            })

    # 2. Shareholder checks
    if not shareholders:
        findings.append({
            'severity': 'high', 'category': 'shareholders',
            'title': 'No shareholders recorded',
            'description': 'No shareholders in the register. Share structure may be incomplete.',
            'remediation': 'Record all shareholders in the securities register and issue share certificates.',
            'estimated_hours': 1, 'estimated_cost': 150, 'confidence': 0.95,
        })
    else:
        total_shares = sum(s.num_shares for s in shareholders)
        if total_shares == 0:
            findings.append({
                'severity': 'high', 'category': 'shareholders',
                'title': 'Zero shares issued',
                'description': 'Shareholders exist but no shares have been issued.',
                'remediation': 'Verify share issuance and update the securities register.',
                'estimated_hours': 0.5, 'estimated_cost': 50, 'confidence': 0.9,
            })

    # 3. Profile / registration checks
    if not profile:
        findings.append({
            'severity': 'critical', 'category': 'registrations',
            'title': 'No corporate profile',
            'description': 'No corporate profile exists. Entity may not be properly tracked.',
            'remediation': 'Create a corporate profile with jurisdiction, incorporation date, and registration details.',
            'estimated_hours': 0.5, 'estimated_cost': 0, 'confidence': 0.99,
        })
    else:
        if not profile.jurisdiction:
            findings.append({
                'severity': 'high', 'category': 'registrations',
                'title': 'Jurisdiction not set',
                'description': 'Corporate profile has no jurisdiction specified.',
                'remediation': 'Specify the incorporating jurisdiction.',
                'estimated_hours': 0.1, 'estimated_cost': 0, 'confidence': 0.99,
            })
        if not profile.incorporation_date:
            findings.append({
                'severity': 'high', 'category': 'registrations',
                'title': 'Incorporation date unknown',
                'description': 'Cannot calculate compliance deadlines without incorporation date.',
                'remediation': 'Look up incorporation date from corporate registry or articles.',
                'estimated_hours': 0.25, 'estimated_cost': 0, 'confidence': 0.99,
            })
        if not profile.business_number:
            findings.append({
                'severity': 'medium', 'category': 'tax',
                'title': 'CRA Business Number not recorded',
                'description': 'Business number missing from corporate profile.',
                'remediation': 'Obtain CRA business number from client or CRA My Business Account.',
                'estimated_hours': 0.25, 'estimated_cost': 0, 'confidence': 0.9,
            })

        # Registration checks
        registrations = list(client.entity_registrations.all()) if hasattr(client, 'entity_registrations') else []
        active_regs = [r for r in registrations if r.status == 'active']
        if not active_regs:
            findings.append({
                'severity': 'medium', 'category': 'registrations',
                'title': 'No active registrations recorded',
                'description': 'No corporate registrations tracked for this entity.',
                'remediation': 'Record all active corporate registrations (federal, provincial, extra-provincial).',
                'estimated_hours': 0.5, 'estimated_cost': 0, 'confidence': 0.85,
            })

    # 4. Compliance checks
    overdue_tasks = [t for t in tasks if t.status == 'overdue' or (t.status == 'pending' and t.due_date and t.due_date < today)]
    if overdue_tasks:
        findings.append({
            'severity': 'critical', 'category': 'compliance',
            'title': f'{len(overdue_tasks)} overdue compliance task(s)',
            'description': 'Overdue tasks: ' + ', '.join(t.title for t in overdue_tasks[:5]),
            'remediation': 'Address overdue tasks immediately to avoid further penalties.',
            'detail': {'task_ids': [t.id for t in overdue_tasks]},
            'estimated_hours': len(overdue_tasks) * 0.5, 'estimated_cost': len(overdue_tasks) * 100,
            'confidence': 0.99,
        })

    pending_filings = [f for f in filings if f.status == 'overdue']
    if pending_filings:
        findings.append({
            'severity': 'critical', 'category': 'registrations',
            'title': f'{len(pending_filings)} overdue annual filing(s)',
            'description': 'Overdue filings: ' + ', '.join(f'{f.year}' for f in pending_filings),
            'remediation': 'File overdue annual returns immediately. Late filing may result in dissolution.',
            'estimated_hours': len(pending_filings), 'estimated_cost': len(pending_filings) * 200,
            'confidence': 0.99,
        })

    # 5. UBO checks
    ubo_count = UBORecord.objects.filter(client=client).count() if hasattr(client, 'ubo_records') else 0
    if ubo_count == 0 and profile and profile.jurisdiction:
        findings.append({
            'severity': 'critical', 'category': 'ubo',
            'title': 'UBO register is empty',
            'description': 'No individuals with significant control recorded. Legally required under Bill C-86.',
            'remediation': 'Identify all individuals with significant control and record in the UBO register.',
            'estimated_hours': 2, 'estimated_cost': 300, 'confidence': 0.95,
        })

    # 6. Entity age / stale records
    if profile and profile.incorporation_date:
        years_since_inc = (today - profile.incorporation_date).days / 365
        if years_since_inc > 1:
            # Check if minute book has been updated recently
            has_recent_task = any(
                t.status == 'completed' and t.task_type == 'minute_book_update'
                for t in tasks
            )
            if not has_recent_task:
                findings.append({
                    'severity': 'medium', 'category': 'documents',
                    'title': f'Minute book not updated in {int(years_since_inc)} years',
                    'description': 'Entity is over 1 year old with no recent minute book updates recorded.',
                    'remediation': 'Schedule minute book update and annual resolutions.',
                    'estimated_hours': 2, 'estimated_cost': 300, 'confidence': 0.85,
                })

    # 7. Missing annual filings
    if profile and profile.incorporation_date:
        years = int((today - profile.incorporation_date).days / 365)
        filed_years = set(f.year for f in filings if f.status == 'filed')
        expected_years = set(range(profile.incorporation_date.year, today.year + 1))
        missing_years = expected_years - filed_years - {profile.incorporation_date.year}
        if missing_years:
            findings.append({
                'severity': 'high', 'category': 'registrations',
                'title': f'Missing annual filings for years: {sorted(missing_years)}',
                'description': f'Annual returns not filed for {len(missing_years)} year(s).',
                'remediation': 'File missing annual returns. Late fees may apply.',
                'detail': {'missing_years': list(missing_years)},
                'estimated_hours': len(missing_years) * 1, 'estimated_cost': len(missing_years) * 200,
                'confidence': 0.95,
            })

    return findings
