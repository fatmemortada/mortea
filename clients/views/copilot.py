"""
Accountant Copilot — instant client file summary.

When an accountant opens a client file, they see:
  - What's uploaded vs missing
  - Anomalies detected
  - Risk flags
  - Upcoming deadlines
  - Recommended actions
  - Corporate health score

3-minute review instead of 20-minute hunt.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import date, timedelta

from ._helpers import _get_firm


@login_required
def copilot_dashboard(request, client_id):
    """Accountant Copilot — complete client summary in one view."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    from ..models import (
        Client, T2Return, T1Organizer, ComplianceTask, Invoice,
        BookkeepingTask, Director, Shareholder, Document, Note,
    )

    client = get_object_or_404(Client.objects.select_related('corporate_profile'), id=client_id, firm=firm)
    today = date.today()
    cp = getattr(client, 'corporate_profile', None)

    # ── Corporate Health ──────────────────────────────────────────
    from ..corporate_health import calculate_corporate_health
    health = calculate_corporate_health(client)

    # ── T2 Status ─────────────────────────────────────────────────
    t2 = T2Return.objects.filter(client=client).order_by('-tax_year').first()
    t2_prior = T2Return.objects.filter(client=client, tax_year=(t2.tax_year - 1 if t2 else today.year - 1)).first()

    # ── T1 Status ─────────────────────────────────────────────────
    t1 = T1Organizer.objects.filter(client=client).order_by('-tax_year').first()

    # ── Anomaly Detection ─────────────────────────────────────────
    anomalies = []
    if t2:
        from ..ai_analyzer import detect_expense_anomalies, analyze_shareholder_loans, gst_review
        anomalies = detect_expense_anomalies(client, t2, t2_prior)
        shareholder_findings = analyze_shareholder_loans(client, t2, t2_prior)
        gst_findings = gst_review(client, t2)
    else:
        shareholder_findings = []
        gst_findings = []

    # ── Missing Deductions ────────────────────────────────────────
    missing_deductions = []
    if t1:
        from ..ai_analyzer import detect_missing_deductions
        missing_deductions = detect_missing_deductions(t1)

    # ── Deadlines ─────────────────────────────────────────────────
    from ..deadline_engine import calculate_entity_deadlines
    deadlines = calculate_entity_deadlines(client)
    urgent_deadlines = [d for d in deadlines if d['days_remaining'] <= 30]

    # ── Minute Book Health ────────────────────────────────────────
    from ..deadline_engine import minute_book_health_check
    mb_health = minute_book_health_check(client)

    # ── Compliance Summary ────────────────────────────────────────
    overdue_tasks = ComplianceTask.objects.filter(client=client, status='overdue').count()
    pending_tasks = ComplianceTask.objects.filter(client=client, status='pending').count()
    completed_tasks = ComplianceTask.objects.filter(client=client, status='completed').count()

    # ── Financial Summary ─────────────────────────────────────────
    total_invoiced = Invoice.objects.filter(client=client).count()
    unpaid_invoices = Invoice.objects.filter(client=client, status__in=['sent', 'overdue']).count()
    total_revenue = sum(float(inv.total_amount) for inv in Invoice.objects.filter(client=client, status='paid'))

    # ── Bookkeeping Status ────────────────────────────────────────
    bk_latest = BookkeepingTask.objects.filter(client=client).order_by('-year', '-id').first()
    bk_current_month = BookkeepingTask.objects.filter(
        client=client, month=today.strftime('%B'), year=today.year
    ).first()

    # ── Recommended Actions ───────────────────────────────────────
    actions = []
    if t2 and t2.status not in ['filed', 'accepted']:
        days = (t2.fiscal_year_end + timedelta(days=180) - today).days if t2.fiscal_year_end else 180
        actions.append({
            'priority': 'high' if days <= 30 else 'medium',
            'action': f'Prepare T2 {t2.tax_year} — {max(0, days)} days until deadline',
            'link': f'/t2/prepare/{client.id}/',
        })

    if overdue_tasks > 0:
        actions.append({
            'priority': 'high',
            'action': f'{overdue_tasks} compliance task(s) overdue — update now',
            'link': '/compliance/',
        })

    if unpaid_invoices > 0:
        actions.append({
            'priority': 'medium',
            'action': f'{unpaid_invoices} invoice(s) unpaid — send reminders',
            'link': '/billing/',
        })

    if mb_health['missing'] > 0:
        actions.append({
            'priority': 'medium' if mb_health['missing'] <= 3 else 'high',
            'action': f'{mb_health["missing"]} minute book items missing — generate documents',
            'link': f'/clients/{client.id}/minute-book-builder/',
        })

    if t1 and t1.completion_pct < 50 and t1.status in ['sent', 'in_progress']:
        actions.append({
            'priority': 'medium',
            'action': f'T1 {t1.tax_year} only {t1.completion_pct}% complete — remind client',
            'link': f'/t1/{t1.id}/',
        })

    if not bk_current_month:
        actions.append({
            'priority': 'low',
            'action': f'No bookkeeping task for {today.strftime("%B")} — create one',
            'link': '/automation/bookkeeping/',
        })

    if anomalies:
        critical_anomalies = [a for a in anomalies if a.get('level') == 'critical']
        if critical_anomalies:
            actions.append({
                'priority': 'high',
                'action': f'{len(critical_anomalies)} critical expense anomal{"y" if len(critical_anomalies) == 1 else "ies"} detected',
                'link': f'/t2/prepare/{client.id}/',
            })

    actions.sort(key=lambda a: {'high': 0, 'medium': 1, 'low': 2}.get(a['priority'], 3))

    # ── Recent Activity ────────────────────────────────────────────
    recent_docs = Document.objects.filter(client=client).order_by('-uploaded_at')[:5]
    recent_notes = Note.objects.filter(client=client).order_by('-created_at')[:5]

    return render(request, 'clients/copilot.html', {
        'firm': firm,
        'client': client,
        'health': health,
        't2': t2,
        't1': t1,
        'anomalies': anomalies,
        'shareholder_findings': shareholder_findings,
        'gst_findings': gst_findings,
        'missing_deductions': missing_deductions,
        'deadlines': deadlines[:10],
        'urgent_deadlines': urgent_deadlines,
        'mb_health': mb_health,
        'overdue_tasks': overdue_tasks,
        'pending_tasks': pending_tasks,
        'completed_tasks': completed_tasks,
        'total_invoiced': total_invoiced,
        'unpaid_invoices': unpaid_invoices,
        'total_revenue': total_revenue,
        'bk_latest': bk_latest,
        'bk_current_month': bk_current_month,
        'actions': actions,
        'recent_docs': recent_docs,
        'recent_notes': recent_notes,
    })
