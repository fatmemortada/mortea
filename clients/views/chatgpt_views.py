"""Views for ChatGPT-suggested features."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import date

from ..models import Client, Firm, CorporateProfile, ComplianceTask, Invoice, EngagementLetterRecord, AnnualFiling, ActivityLog, log_activity
from ..models.chatgpt_features import (
    DividendPackage, ReorganizationProject, ReorganizationStep,
    GovernmentFee, CRACorrespondence, DueDiligenceProject,
)
from ._helpers import _get_firm


# 22. Dividend Package
@login_required
def dividend_package(request, client_id):
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    shareholders = client.shareholders.all()
    today = date.today()
    result = None

    if request.method == 'POST':
        DividendPackage.objects.create(
            client=client, shareholder_name=request.POST.get('shareholder_name'),
            dividend_amount=request.POST.get('dividend_amount', 0),
            declaration_date=request.POST.get('declaration_date', today),
            created_by=request.user,
        )
        result = {
            'resolution': f'BOARD RESOLUTION\nDeclared dividend of ${request.POST.get("dividend_amount")} to {request.POST.get("shareholder_name")}\nDate: {today}',
            'journal': f'JOURNAL ENTRY\nDebit: Retained Earnings ${request.POST.get("dividend_amount")}\nCredit: Dividends Payable ${request.POST.get("dividend_amount")}',
        }
    return render(request, 'clients/dividend_package.html', {'client': client, 'shareholders': shareholders, 'today': today, 'result': result})


# 23. Reorganization Wizard
@login_required
def reorg_wizard(request, client_id):
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    projects = client.reorg_projects.all()

    if request.method == 'POST':
        proj = ReorganizationProject.objects.create(
            client=client, project_type=request.POST.get('project_type'),
            description=request.POST.get('description', ''), created_by=request.user,
        )
        steps_map = {
            'estate_freeze': ['Valuation of corporation', 'Share restructuring plan', 'Tax election forms', 'New share class creation', 'Board resolutions'],
            'holding_company': ['Incorporate holding company', 'Share transfer agreement', 'Tax election (S85)', 'Board resolutions', 'Update share registers'],
            'share_exchange': ['Share valuation', 'Exchange agreement', 'Board resolutions', 'Share certificates', 'Register updates'],
            's85_rollover': ['Asset valuation', 'Tax election form (T2057)', 'Purchase agreement', 'Board resolutions', 'CRA filing'],
            'amalgamation': ['Amalgamation agreement', 'Shareholder approval', 'Articles of Amalgamation', 'Board resolutions', 'Post-amalgamation registers'],
        }
        for i, step_title in enumerate(steps_map.get(proj.project_type, [])):
            ReorganizationStep.objects.create(project=proj, title=step_title, order=i)
        return redirect('reorg_wizard', client_id=client_id)

    return render(request, 'clients/reorg_wizard.html', {'client': client, 'projects': projects})


# 26. Fee Calculator
@login_required
def fee_calculator(request):
    jurisdiction = request.GET.get('jurisdiction', 'federal')
    fee_type = request.GET.get('fee_type', 'incorporation')
    fees = GovernmentFee.objects.filter(jurisdiction=jurisdiction, fee_type=fee_type)
    return render(request, 'clients/fee_calculator.html', {'fees': fees, 'jurisdiction': jurisdiction, 'fee_type': fee_type})


# 33. CRA Correspondence
@login_required
def cra_tracker(request, client_id):
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    items = client.cra_correspondence.all()

    if request.method == 'POST':
        CRACorrespondence.objects.create(
            client=client, title=request.POST.get('title'), agency=request.POST.get('agency', 'CRA'),
            reference_number=request.POST.get('reference', ''), received_date=request.POST.get('received_date'),
            response_deadline=request.POST.get('deadline') or None,
            assigned_to_id=request.POST.get('assigned_to') or None,
        )
        return redirect('cra_tracker', client_id=client_id)
    return render(request, 'clients/cra_tracker.html', {'client': client, 'items': items, 'today': date.today()})


# 34. Due Diligence
@login_required
def due_diligence(request, client_id):
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    projects = client.dd_projects.all()
    return render(request, 'clients/due_diligence.html', {'client': client, 'projects': projects})


# 36. FIRM COMMAND CENTER
@login_required
def command_center(request):
    firm = _get_firm(request.user)
    if not firm: return redirect('dashboard')
    today = date.today()
    thirty_days = today + timezone.timedelta(days=30)
    month_start = today.replace(day=1)

    clients = Client.objects.filter(firm=firm).prefetch_related(
        'compliance_tasks', 'invoices', 'corporate_profile', 'annual_filings'
    )
    total_clients = clients.count()

    # ── Compliance stats ──────────────────────────────────────────────
    overdue_tasks = ComplianceTask.objects.filter(client__firm=firm, status='overdue').count()
    pending_tasks = ComplianceTask.objects.filter(client__firm=firm, status='pending').count()
    in_progress_tasks = ComplianceTask.objects.filter(client__firm=firm, status='in_progress').count()

    # Filings due this month
    filings_due_month = ComplianceTask.objects.filter(
        client__firm=firm, status__in=['pending', 'in_progress'],
        due_date__gte=month_start, due_date__lte=thirty_days,
    ).count()

    # Overdue filings (AnnualFiling model)
    overdue_filings = AnnualFiling.objects.filter(
        client__firm=firm, status='overdue'
    ).count()

    # Annual returns due (next 30 days)
    annual_returns_due = ComplianceTask.objects.filter(
        client__firm=firm, task_type='annual_return',
        status__in=['pending', 'in_progress'],
        due_date__lte=thirty_days,
    ).count()

    # Quebec declarations due
    quebec_due = ComplianceTask.objects.filter(
        client__firm=firm, task_type='quebec_declaration',
        status__in=['pending', 'in_progress'],
        due_date__lte=thirty_days,
    ).count()

    # ── Invoice stats ─────────────────────────────────────────────────
    outstanding_inv = Invoice.objects.filter(
        client__firm=firm, status__in=['sent', 'overdue']
    ).aggregate(t=Sum('amount'))['t'] or 0
    unpaid_count = Invoice.objects.filter(
        client__firm=firm, status__in=['sent', 'overdue']
    ).count()
    overdue_inv_amount = Invoice.objects.filter(
        client__firm=firm, status='overdue'
    ).aggregate(t=Sum('amount'))['t'] or 0

    # ── Document & engagement gaps ────────────────────────────────────
    missing_minute = sum(1 for c in clients if c.minute_book_documents.count() == 0)
    missing_ubo = sum(1 for c in clients if c.ubo_records.count() == 0)
    eng_unsigned = sum(1 for c in clients if not hasattr(c, 'engagementletterrecord') or c.engagementletterrecord_set.count() == 0)

    # ── Pending signatures ────────────────────────────────────────────
    from ..models import SignatureRequest
    pending_signatures = SignatureRequest.objects.filter(
        client__firm=firm, status='pending'
    ).count()

    # ── Completed this month ──────────────────────────────────────────
    completed_month = ComplianceTask.objects.filter(
        client__firm=firm, status='completed',
        completed_at__date__gte=month_start,
    ).count()

    # ── "Needs Attention" clients ─────────────────────────────────────
    needs_attention = []
    for c in clients:
        ov = c.compliance_tasks.filter(status='overdue').count()
        mi = c.missing_items if hasattr(c, 'missing_items') else 0
        unp = c.invoices.filter(status__in=['sent', 'overdue']).count()
        if ov > 0 or unp > 0 or (hasattr(c, 'missing_items') and mi > 0):
            needs_attention.append({
                'id': c.id,
                'name': c.name,
                'status': c.get_status_display(),
                'overdue': ov,
                'missing': mi if hasattr(c, 'missing_items') else 0,
                'unpaid': unp,
                'health': 'red' if ov > 0 else 'amber',
            })
    needs_attention.sort(key=lambda x: x['overdue'] + x['unpaid'], reverse=True)
    needs_attention = needs_attention[:15]

    # ── Upcoming deadlines (merged) ───────────────────────────────────
    # Compliance tasks
    upcoming_tasks = ComplianceTask.objects.filter(
        client__firm=firm, status__in=['pending', 'in_progress'],
        due_date__gte=today, due_date__lte=thirty_days,
    ).select_related('client').order_by('due_date')[:15]

    # Annual filings
    upcoming_filings = AnnualFiling.objects.filter(
        client__firm=firm, status='pending',
        due_date__gte=today, due_date__lte=thirty_days,
    ).select_related('client').order_by('due_date')[:10]

    # Merge into single timeline
    merged_deadlines = []
    for t in upcoming_tasks:
        days = (t.due_date - today).days
        merged_deadlines.append({
            'client_name': t.client.name, 'client_id': t.client.id,
            'title': t.title, 'type': 'compliance', 'due_date': t.due_date,
            'days': days, 'status': t.get_status_display(),
        })
    for f in upcoming_filings:
        days = (f.due_date - today).days
        merged_deadlines.append({
            'client_name': f.client.name, 'client_id': f.client.id,
            'title': f"Annual Filing — {f.year}",
            'type': 'filing', 'due_date': f.due_date,
            'days': days, 'status': f.get_status_display(),
        })
    merged_deadlines.sort(key=lambda x: x['days'])

    # ── Chart: Health distribution ────────────────────────────────────
    from ._helpers import compute_health_score
    health_counts = {'green': 0, 'amber': 0, 'red': 0}
    for c in clients:
        score = compute_health_score(c)
        health_counts[score['color']] = health_counts.get(score['color'], 0) + 1

    # ── Chart: Monthly compliance trend (6 months) ───────────────────
    monthly_labels = []
    monthly_completed = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m < 1:
            m += 12; y -= 1
        month_start_dt = date(y, m, 1)
        if m == 12:
            month_end_dt = date(y + 1, 1, 1)
        else:
            month_end_dt = date(y, m + 1, 1)
        monthly_labels.append(month_start_dt.strftime('%b %Y'))
        monthly_completed.append(
            ComplianceTask.objects.filter(
                client__firm=firm, status='completed',
                completed_at__date__gte=month_start_dt,
                completed_at__date__lt=month_end_dt,
            ).count()
        )

    # ── Chart: Task type distribution ─────────────────────────────────
    task_type_labels = []
    task_type_counts = []
    for ttype, tlabel in ComplianceTask._meta.get_field('task_type').choices:
        count = ComplianceTask.objects.filter(
            client__firm=firm, status__in=['pending', 'in_progress'], task_type=ttype
        ).count()
        if count > 0:
            task_type_labels.append(tlabel)
            task_type_counts.append(count)

    # ── Recent activity ───────────────────────────────────────────────
    from ..models import ActivityLog
    recent_activity = ActivityLog.objects.filter(
        firm=firm
    ).select_related('user').order_by('-created_at')[:8]

    return render(request, 'clients/command_center.html', {
        'firm': firm, 'today': today,
        'total_clients': total_clients,
        'overdue_tasks': overdue_tasks,
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'filings_due_month': filings_due_month,
        'overdue_filings': overdue_filings,
        'annual_returns_due': annual_returns_due,
        'quebec_due': quebec_due,
        'outstanding_inv': outstanding_inv,
        'unpaid_count': unpaid_count,
        'overdue_inv_amount': overdue_inv_amount,
        'completed_month': completed_month,
        'missing_minute': missing_minute,
        'missing_ubo': missing_ubo,
        'eng_unsigned': eng_unsigned,
        'pending_signatures': pending_signatures,
        'needs_attention': needs_attention,
        'upcoming': merged_deadlines,
        'health_counts': health_counts,
        'monthly_labels': monthly_labels,
        'monthly_completed': monthly_completed,
        'task_type_labels': task_type_labels,
        'task_type_counts': task_type_counts,
        'recent_activity': recent_activity,
    })
