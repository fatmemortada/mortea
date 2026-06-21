import csv
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone

from ..models import Client, ComplianceTask, Invoice, ActivityLog, log_activity
from ._helpers import _get_firm, _csv_response


@login_required
def export_clients_csv(request):
    firm = _get_firm(request.user)
    clients = Client.objects.filter(firm=firm).select_related('corporate_profile').order_by('name') if firm else Client.objects.none()

    response = _csv_response('mortacc_clients')
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Phone', 'Business Type', 'Client Type', 'Status', 'Language',
                      'Jurisdiction', 'Incorporation Date', 'Business Number', 'HST Number',
                      'Directors', 'Shareholders', 'Client Token', 'Created'])

    for c in clients:
        corp = getattr(c, 'corporate_profile', None)
        writer.writerow([
            c.name, c.email, c.phone, c.business_type, c.client_type, c.get_status_display(), c.get_language_display(),
            corp.get_jurisdiction_display() if corp and corp.jurisdiction else '',
            corp.incorporation_date if corp else '',
            corp.business_number if corp else '',
            corp.hst_number if corp else '',
            c.directors.count(), c.shareholders.count(),
            c.client_token or '', c.created_at.strftime('%Y-%m-%d') if c.created_at else '',
        ])

    log_activity(request.user, 'export', 'Client', None, f'{clients.count()} clients',
                f'Exported {clients.count()} clients to CSV', firm=firm)
    return response


@login_required
def export_compliance_csv(request):
    firm = _get_firm(request.user)
    tasks = ComplianceTask.objects.filter(client__firm=firm).select_related('client').order_by('due_date') if firm else ComplianceTask.objects.none()

    response = _csv_response('mortacc_compliance')
    writer = csv.writer(response)
    writer.writerow(['Client', 'Task Title', 'Task Type', 'Status', 'Due Date', 'Completed', 'Auto Generated', 'Notes'])

    for t in tasks:
        writer.writerow([
            t.client.name, t.title, t.get_task_type_display(), t.get_status_display(),
            t.due_date, t.completed_at.strftime('%Y-%m-%d') if t.completed_at else '',
            'Yes' if t.auto_generated else 'No', t.notes,
        ])

    log_activity(request.user, 'export', 'ComplianceTask', None, f'{tasks.count()} tasks',
                f'Exported {tasks.count()} compliance tasks to CSV', firm=firm)
    return response


@login_required
def export_invoices_csv(request):
    firm = _get_firm(request.user)
    invoices = Invoice.objects.filter(client__firm=firm).select_related('client').order_by('-invoice_date') if firm else Invoice.objects.none()

    response = _csv_response('mortacc_invoices')
    writer = csv.writer(response)
    writer.writerow(['Invoice #', 'Client', 'Service Type', 'Description', 'Amount', 'Status', 'Invoice Date', 'Due Date', 'Paid Date', 'Notes'])

    for inv in invoices:
        writer.writerow([
            inv.invoice_number, inv.client.name, inv.get_service_type_display(), inv.description,
            str(inv.amount), inv.get_status_display(),
            inv.invoice_date, inv.due_date or '', inv.paid_date or '', inv.notes,
        ])

    log_activity(request.user, 'export', 'Invoice', None, f'{invoices.count()} invoices',
                f'Exported {invoices.count()} invoices to CSV', firm=firm)
    return response


@login_required
def activity_log_view(request):
    firm = _get_firm(request.user)
    if not firm:
        return redirect('dashboard')

    from django.core.paginator import Paginator

    action_filter = request.GET.get('action', '')
    target_filter = request.GET.get('target', '')
    user_filter = request.GET.get('user', '')
    page = request.GET.get('page', '1')

    # Build filtered queryset BEFORE slicing (fixes unbounded query 500 error)
    logs = ActivityLog.objects.filter(firm=firm).select_related('user').order_by('-created_at')

    if action_filter:
        logs = logs.filter(action=action_filter)
    if target_filter:
        logs = logs.filter(target_type=target_filter)
    if user_filter:
        logs = logs.filter(user__username__icontains=user_filter)

    # Paginate: 50 per page
    paginator = Paginator(logs, 50)
    try:
        page_obj = paginator.page(int(page))
    except Exception:
        page_obj = paginator.page(1)

    all_actions = ActivityLog.objects.filter(firm=firm).values_list('action', flat=True).distinct()
    all_targets = ActivityLog.objects.filter(firm=firm).values_list('target_type', flat=True).distinct()

    return render(request, 'clients/activity_log.html', {
        'logs': page_obj, 'firm': firm,
        'all_actions': sorted(set(all_actions)),
        'all_targets': sorted(set(t for t in all_targets if t)),
        'action_filter': action_filter, 'target_filter': target_filter,
        'user_filter': user_filter,
    })
