"""Automation Dashboard — overview of all automated jobs and their status."""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta

from ._helpers import _get_firm


@login_required
def automation_dashboard(request):
    """Automation overview: scheduled jobs, workflow runs, bookkeeping & T2 status."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    from ..models import (
        SchedulerJobLog, Workflow, WorkflowRun, BookkeepingTask,
        T2Return, CorporateProfile, ComplianceTask,
    )

    today = timezone.now().date()

    # ── Scheduled Jobs: latest runs ──────────────────────────────
    job_ids = [
        'automated_reminders', 'mark_overdue_tasks', 'weekly_compliance_digest',
        'subscription_renewals', 'collections_reminders',
        't2_deadline_reminders', 'generate_bookkeeping_tasks', 'gst_hst_reminder',
        'tax_installment_reminder', 'bookkeeping_reconciliation',
        'incorporation_anniversary', 'auto_create_t2_returns',
    ]

    jobs = []
    for jid in job_ids:
        last = SchedulerJobLog.objects.filter(job_id=jid).order_by('-started_at').first()
        jobs.append({
            'job_id': jid,
            'name': last.job_name if last else jid.replace('_', ' ').title(),
            'last_run': last.started_at if last else None,
            'last_status': last.status if last else 'never',
            'last_duration_ms': last.duration_ms if last else 0,
            'last_error': last.error_message if last and last.status == 'failed' else '',
            'records': last.records_affected if last else 0,
        })

    # ── Active Workflows ────────────────────────────────────────
    active_workflows = Workflow.objects.filter(firm=firm, status='active')
    recent_runs = WorkflowRun.objects.filter(
        workflow__firm=firm
    ).select_related('workflow').order_by('-started_at')[:30]

    # ── Bookkeeping Status ──────────────────────────────────────
    bk_pending = BookkeepingTask.objects.filter(
        client__firm=firm,
        status__in=['not_started', 'in_progress'],
    ).count()
    bk_total = BookkeepingTask.objects.filter(client__firm=firm).count()

    current_month = today.strftime('%B')
    bk_this_month = BookkeepingTask.objects.filter(
        client__firm=firm, month=current_month, year=today.year,
    )

    # ── T2 Status ───────────────────────────────────────────────
    t2_returns = T2Return.objects.filter(firm=firm)
    t2_total = t2_returns.count()
    t2_filed = t2_returns.filter(status__in=['filed', 'accepted']).count()
    t2_not_started = t2_returns.filter(status='not_started').count()
    t2_in_progress = t2_returns.filter(
        status__in=['preparing', 'review', 'client_approval', 'ready_to_file']
    ).count()

    # ── Upcoming Deadlines ──────────────────────────────────────
    upcoming_deadlines = []
    # T2 deadlines in next 60 days
    entities_with_fye = CorporateProfile.objects.filter(
        client__firm=firm, fiscal_year_end__isnull=False
    ).select_related('client')
    for cp in entities_with_fye:
        try:
            fye_this_year = cp.fiscal_year_end.replace(year=today.year)
        except ValueError:
            continue
        t2_deadline = fye_this_year + timedelta(days=180)  # approximate 6 months
        days_left = (t2_deadline - today).days
        if 0 <= days_left <= 60:
            upcoming_deadlines.append({
                'client_name': cp.client.name,
                'client_id': cp.client.id,
                'type': 'T2 Filing',
                'deadline': t2_deadline,
                'days_left': days_left,
            })

    # Compliance deadlines
    urgent_tasks = ComplianceTask.objects.filter(
        client__firm=firm,
        status__in=['pending', 'overdue'],
        due_date__lte=today + timedelta(days=30),
    ).select_related('client').order_by('due_date')[:20]
    for task in urgent_tasks:
        upcoming_deadlines.append({
            'client_name': task.client.name,
            'client_id': task.client.id,
            'type': task.title,
            'deadline': task.due_date,
            'days_left': (task.due_date - today).days,
            'status': task.status,
        })

    upcoming_deadlines.sort(key=lambda d: d['days_left'])
    upcoming_deadlines = upcoming_deadlines[:30]

    # ── Job Schedule Reference ──────────────────────────────────
    job_schedule = [
        {'name': 'Automated Client Reminders', 'schedule': 'Daily 9:00 AM', 'description': 'Onboarding doc reminders at days 2, 5, 7'},
        {'name': 'Mark Overdue Tasks', 'schedule': 'Daily 12:05 AM', 'description': 'Auto-marks overdue compliance tasks, fires webhooks'},
        {'name': 'Weekly Compliance Digest', 'schedule': 'Monday 8:00 AM', 'description': 'Emails each firm a weekly compliance summary'},
        {'name': 'Subscription Renewals', 'schedule': 'Daily 2:00 AM', 'description': 'Auto-renews subscriptions, generates invoices'},
        {'name': 'Collections Reminders', 'schedule': 'Daily 8:30 AM', 'description': 'Sends payment reminders for overdue invoices'},
        {'name': 'T2 Deadline Reminders', 'schedule': 'Daily 9:15 AM', 'description': 'T2 filing reminders at 60/30/14/7 days'},
        {'name': 'Monthly Bookkeeping Tasks', 'schedule': '1st of month, 6:00 AM', 'description': 'Auto-creates monthly bookkeeping tasks'},
        {'name': 'GST/HST Reminders', 'schedule': '1st of month, 8:00 AM', 'description': 'Reminds firms about pending GST/HST filings'},
        {'name': 'Tax Installment Reminders', 'schedule': '15th of month, 8:00 AM', 'description': 'Monthly/quarterly tax installment reminders'},
        {'name': 'Bookkeeping Reconciliation', 'schedule': 'Monday 7:00 AM', 'description': 'Reminds about stale bookkeeping tasks'},
        {'name': 'Anniversary Reminders', 'schedule': 'Daily 8:45 AM', 'description': 'Annual return reminders based on incorporation date'},
        {'name': 'Auto-Create T2 Returns', 'schedule': 'Daily 3:00 AM', 'description': 'Creates T2 returns after fiscal year end'},
    ]

    return render(request, 'clients/automation_dashboard.html', {
        'firm': firm,
        'jobs': jobs,
        'job_schedule': job_schedule,
        'active_workflows': active_workflows,
        'recent_runs': recent_runs,
        'bk_pending': bk_pending,
        'bk_total': bk_total,
        'bk_this_month': bk_this_month,
        't2_total': t2_total,
        't2_filed': t2_filed,
        't2_not_started': t2_not_started,
        't2_in_progress': t2_in_progress,
        'upcoming_deadlines': upcoming_deadlines,
    })
