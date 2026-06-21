"""Firm Analytics + Benchmarking views."""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import date, timedelta

from ..models import (
    Client, Invoice, ComplianceTask, EntitySubscription, TimeEntry,
    IncorporationProject, CorporateProfile,
    FirmAnalyticsSnapshot, IndustryBenchmark, KPI,
    log_activity,
)
from ._helpers import _get_firm


@login_required
def analytics_dashboard(request):
    """Firm analytics dashboard — revenue, compliance, utilization."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    clients = Client.objects.filter(firm=firm)

    # ── Revenue metrics ──────────────────────────────────────────────
    total_revenue_ytd = Invoice.objects.filter(
        client__firm=firm, status='paid', paid_date__gte=year_start
    ).aggregate(t=Sum('total_amount'))['t'] or 0

    total_revenue_month = Invoice.objects.filter(
        client__firm=firm, status='paid', paid_date__gte=month_start
    ).aggregate(t=Sum('total_amount'))['t'] or 0

    outstanding = Invoice.objects.filter(
        client__firm=firm, status__in=['sent', 'overdue']
    ).aggregate(t=Sum('total_amount'))['t'] or 0

    overdue = Invoice.objects.filter(
        client__firm=firm, status='overdue'
    ).aggregate(t=Sum('total_amount'))['t'] or 0

    # MRR
    active_subs = EntitySubscription.objects.filter(firm=firm, status='active')
    mrr = sum(s.monthly_revenue for s in active_subs) / 100

    # Average revenue per client
    client_count = max(clients.count(), 1)
    avg_rev_per_client = float(total_revenue_ytd) / client_count

    # Collection rate
    total_invoiced = Invoice.objects.filter(
        client__firm=firm, invoice_date__gte=year_start
    ).aggregate(t=Sum('total_amount'))['t'] or 0
    total_paid = float(total_revenue_ytd)
    collection_rate = int((total_paid / max(float(total_invoiced), 1)) * 100)

    # ── Revenue by service type ─────────────────────────────────────
    rev_by_service = {}
    for inv in Invoice.objects.filter(client__firm=firm, status='paid', paid_date__gte=year_start):
        st = inv.service_type
        if st not in rev_by_service:
            rev_by_service[st] = 0
        rev_by_service[st] += float(inv.total_amount)
    service_revenue = [{'name': k.replace('_', ' ').title(), 'amount': v} for k, v in sorted(rev_by_service.items(), key=lambda x: x[1], reverse=True)]

    # ── Revenue trend (12 months) ───────────────────────────────────
    revenue_trend = []
    for i in range(11, -1, -1):
        d = today - timedelta(days=30 * i)
        ms = d.replace(day=1)
        me = (ms.replace(month=ms.month + 1, day=1) if ms.month < 12 else ms.replace(year=ms.year + 1, month=1, day=1))
        amt = Invoice.objects.filter(client__firm=firm, status='paid', paid_date__gte=ms, paid_date__lt=me).aggregate(t=Sum('total_amount'))['t'] or 0
        revenue_trend.append({'month': ms.strftime('%b %y'), 'amount': float(amt)})

    # ── Compliance metrics ──────────────────────────────────────────
    tasks = ComplianceTask.objects.filter(client__firm=firm)
    total_tasks = tasks.count()
    overdue_count = tasks.filter(status='overdue').count()
    completed_count = tasks.filter(status='completed').count()
    compliance_rate = int((completed_count / max(total_tasks, 1)) * 100)

    # By jurisdiction
    by_jurisdiction = CorporateProfile.objects.filter(client__firm=firm).values('jurisdiction').annotate(count=Count('id')).order_by('-count')

    # ── Staff metrics ──────────────────────────────────────────────
    time_entries = TimeEntry.objects.filter(client__firm=firm, date__gte=year_start)
    total_billable_hours = time_entries.aggregate(t=Sum('hours'))['t'] or 0
    total_billed = time_entries.filter(billing_status='billed').aggregate(t=Sum('amount'))['t'] or 0
    total_unbilled = time_entries.filter(billing_status='unbilled').aggregate(t=Sum('amount'))['t'] or 0

    # ── Incorporation metrics ───────────────────────────────────────
    incorp_projects = IncorporationProject.objects.filter(firm=firm)
    incorp_ytd = incorp_projects.filter(created_at__gte=year_start).count()
    incorp_completed = incorp_projects.filter(status='complete').count()
    avg_incorp_days = incorp_projects.filter(completed_at__isnull=False).aggregate(
        avg=Avg(F('completed_at') - F('created_at'))
    )['avg'] or timedelta(0)

    # ── Client metrics ──────────────────────────────────────────────
    new_clients_month = clients.filter(created_at__gte=month_start).count()
    new_clients_year = clients.filter(created_at__gte=year_start).count()
    active_clients = clients.filter(status__in=['in_progress', 'in_review']).count()

    # ── KPIs ────────────────────────────────────────────────────────
    kpis = KPI.objects.filter(firm=firm, is_active=True).order_by('sort_order')

    # ── Benchmarking ────────────────────────────────────────────────
    user_profile = getattr(request.user, 'userprofile', None)
    firm_size = 'small'  # default
    firm_type = 'accounting' if user_profile and user_profile.role == 'accountant' else 'law'
    if clients.count() > 200:
        firm_size = 'large'
    elif clients.count() > 50:
        firm_size = 'medium'
    elif clients.count() <= 1:
        firm_size = 'solo'

    benchmarks = IndustryBenchmark.objects.filter(
        firm_size=firm_size, firm_type=firm_type
    ).first()

    # ── Snapshot (generate if none today) ───────────────────────────
    if not FirmAnalyticsSnapshot.objects.filter(firm=firm, snapshot_date=today).exists():
        _create_snapshot(firm, today, clients, total_revenue_ytd, mrr, compliance_rate, collection_rate, total_billable_hours, active_clients.count())

    # Get previous period for comparison
    prev_month = today.replace(day=1) - timedelta(days=1)
    prev_snapshot = FirmAnalyticsSnapshot.objects.filter(
        firm=firm, snapshot_date__lte=prev_month
    ).order_by('-snapshot_date').first()

    revenue_change = 0
    if prev_snapshot and float(prev_snapshot.total_revenue) > 0:
        revenue_change = int(((float(total_revenue_ytd) - float(prev_snapshot.total_revenue)) / float(prev_snapshot.total_revenue)) * 100)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_kpi':
            KPI.objects.create(
                firm=firm, name=request.POST.get('kpi_name', ''),
                category=request.POST.get('kpi_category', 'custom'),
                target_value=float(request.POST.get('kpi_target', 0)),
                unit=request.POST.get('kpi_unit', '$'),
                period=request.POST.get('kpi_period', 'monthly'),
            )
            messages.success(request, 'KPI added.')
        return redirect('analytics_dashboard')

    return render(request, 'clients/analytics_dashboard.html', {
        'firm': firm, 'today': today,
        'total_revenue_ytd': float(total_revenue_ytd),
        'total_revenue_month': float(total_revenue_month),
        'outstanding': float(outstanding), 'overdue': float(overdue),
        'mrr': mrr, 'avg_rev_per_client': avg_rev_per_client,
        'collection_rate': collection_rate,
        'service_revenue': service_revenue, 'revenue_trend': revenue_trend,
        'compliance_rate': compliance_rate, 'overdue_count': overdue_count,
        'total_tasks': total_tasks, 'completed_count': completed_count,
        'by_jurisdiction': by_jurisdiction,
        'total_billable_hours': float(total_billable_hours),
        'total_billed': float(total_billed or 0),
        'total_unbilled': float(total_unbilled or 0),
        'incorp_ytd': incorp_ytd, 'incorp_completed': incorp_completed,
        'new_clients_month': new_clients_month, 'new_clients_year': new_clients_year,
        'active_clients': active_clients, 'total_clients': clients.count(),
        'kpis': kpis, 'benchmarks': benchmarks,
        'prev_snapshot': prev_snapshot, 'revenue_change': revenue_change,
    })


def _create_snapshot(firm, today, clients, revenue, mrr, compliance_rate, collection_rate, hours, active_count):
    """Create a daily snapshot of firm metrics."""
    return FirmAnalyticsSnapshot.objects.create(
        firm=firm, period='daily', snapshot_date=today,
        total_clients=clients.count(), active_clients=active_count,
        total_entities=CorporateProfile.objects.filter(client__firm=firm).count(),
        entities_by_jurisdiction=dict(CorporateProfile.objects.filter(client__firm=firm).values_list('jurisdiction').annotate(c=Count('id'))),
        total_revenue=revenue, recurring_revenue=mrr * 12,
        subscription_mrr=mrr,
        average_revenue_per_client=float(revenue) / max(clients.count(), 1),
        revenue_by_service={},
        total_compliance_tasks=ComplianceTask.objects.filter(client__firm=firm).count(),
        overdue_tasks=ComplianceTask.objects.filter(client__firm=firm, status='overdue').count(),
        completed_tasks=ComplianceTask.objects.filter(client__firm=firm, status='completed').count(),
        average_compliance_score=compliance_rate,
        total_invoiced=float(Invoice.objects.filter(client__firm=firm, invoice_date__gte=today.replace(month=1, day=1)).aggregate(t=Sum('total_amount'))['t'] or 0),
        total_collected=float(revenue),
        outstanding_amount=float(Invoice.objects.filter(client__firm=firm, status__in=['sent','overdue']).aggregate(t=Sum('total_amount'))['t'] or 0),
        collection_rate=collection_rate,
        total_staff=1, total_billable_hours=hours, total_billed_amount=0, utilization_rate=0,
    )
