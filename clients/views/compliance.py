from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from collections import defaultdict

from ..models import Client, ComplianceTask, UserProfile, CustomTaskStatus, log_activity, trigger_webhook
from ..emails import send_missing_docs_reminder
from ._helpers import _get_firm, _get_missing_items


@login_required
def compliance_dashboard_view(request):
    try:
        firm = request.user.userprofile.firm
    except UserProfile.DoesNotExist:
        return redirect('login')

    today = timezone.now().date()
    in_30 = today + timezone.timedelta(days=30)

    clients = Client.objects.filter(firm=firm)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'complete_task':
            task_id = request.POST.get('task_id')
            task = ComplianceTask.objects.filter(id=task_id, client__firm=firm).first()
            if task:
                task.status = 'completed'
                task.completed_at = timezone.now()
                task.save()
                trigger_webhook('task.completed', firm, {
                    'id': task.id, 'task_name': task.task_name,
                    'client_id': task.client_id, 'client_name': task.client.name,
                    'completed_at': str(task.completed_at),
                })
                # Fire workflow trigger
                from ..workflow_triggers import trigger_workflows
                trigger_workflows('compliance_task_completed', firm.id, {
                    'client_id': task.client_id, 'task_id': task.id,
                    'task_name': task.task_name,
                })
            return redirect('compliance_dashboard')

        elif action == 'add_task':
            client_id = request.POST.get('client_id')
            task_type = request.POST.get('task_type', 'other')
            title = request.POST.get('title', '').strip()
            due_date = request.POST.get('due_date')
            description = request.POST.get('description', '').strip()
            client = Client.objects.filter(id=client_id, firm=firm).first()
            if client and title and due_date:
                ComplianceTask.objects.create(
                    client=client, task_type=task_type, title=title,
                    due_date=due_date, description=description, auto_generated=False,
                )
            return redirect('compliance_dashboard')

        elif action == 'add_custom_status':
            label = request.POST.get('label', '').strip()
            if label and firm and not CustomTaskStatus.objects.filter(firm=firm, label__iexact=label).exists():
                CustomTaskStatus.objects.create(
                    firm=firm, label=label,
                    color=request.POST.get('color', 'blue'),
                    sort_order=CustomTaskStatus.objects.filter(firm=firm).count(),
                )
            return redirect('compliance_dashboard')

        elif action == 'delete_custom_status':
            CustomTaskStatus.objects.filter(id=request.POST.get('status_id'), firm=firm).delete()
            return redirect('compliance_dashboard')

        elif action == 'set_custom_status':
            task = ComplianceTask.objects.filter(id=request.POST.get('task_id'), client__firm=firm).first()
            if task:
                status_id = request.POST.get('custom_status_id')
                task.custom_status = CustomTaskStatus.objects.filter(id=status_id, firm=firm).first() if status_id else None
                task.save()
            return redirect('compliance_dashboard')

        elif action == 'bulk_action':
            task_ids = request.POST.getlist('task_ids')
            bulk_action = request.POST.get('bulk_action')
            count = 0
            if task_ids and bulk_action:
                tasks = ComplianceTask.objects.filter(id__in=task_ids, client__firm=firm)
                if bulk_action == 'complete':
                    count = tasks.update(status='completed', completed_at=timezone.now())
                elif bulk_action == 'waive':
                    count = tasks.update(status='waived')
                elif bulk_action == 'reopen':
                    count = tasks.filter(status__in=['completed', 'waived']).update(status='pending', completed_at=None)
                if count:
                    log_activity(request.user, 'status', 'ComplianceTask', None,
                                f'{count} tasks', f'Bulk {bulk_action}d {count} compliance tasks', firm=firm)
            return redirect('compliance_dashboard')

    all_tasks = ComplianceTask.objects.filter(
        client__firm=firm
    ).select_related('client', 'custom_status').order_by('due_date')

    for task in all_tasks:
        task.due_soon = (
            not task.is_overdue
            and task.status not in ('completed', 'waived')
            and task.due_date <= in_30
        )

    overdue_count = sum(1 for t in all_tasks if t.is_overdue or t.status == 'overdue')
    due_this_month = sum(1 for t in all_tasks if t.due_soon)
    pending_count = sum(1 for t in all_tasks if t.status == 'pending' and not t.is_overdue)
    completed_count = sum(1 for t in all_tasks if t.status == 'completed')
    total_count = all_tasks.count()

    tasks_by_month = defaultdict(list)
    for task in all_tasks:
        month_key = task.due_date.strftime('%B %Y')
        tasks_by_month[month_key].append(task)

    return render(request, 'clients/compliance_dashboard.html', {
        'firm': firm, 'tasks': all_tasks,
        'tasks_by_month': dict(tasks_by_month), 'clients': clients,
        'overdue_count': overdue_count, 'due_this_month': due_this_month,
        'pending_count': pending_count, 'completed_count': completed_count,
        'total_count': total_count, 'today': today,
        'custom_statuses': CustomTaskStatus.objects.filter(firm=firm) if firm else CustomTaskStatus.objects.none(),
    })


@login_required
def reminders_view(request):
    firm = _get_firm(request.user)
    today = timezone.now().date()
    sent_message = ''

    if request.method == 'POST':
        action = request.POST.get('action')
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, id=client_id, firm=firm)

        if action == 'send_docs_reminder':
            missing = _get_missing_items(client)
            if missing:
                send_missing_docs_reminder(client, missing)
                sent_message = f'Document reminder sent to {client.name}.'
        elif action == 'send_reminder':
            missing = _get_missing_items(client)
            send_missing_docs_reminder(client, missing or ['compliance deadline'])
            sent_message = f'Reminder sent to {client.name}.'

    clients = Client.objects.filter(firm=firm).prefetch_related('compliance_tasks') if firm else Client.objects.none()

    ComplianceTask.objects.filter(
        client__firm=firm, status='pending', due_date__lt=today,
    ).update(status='overdue')

    overdue_tasks = []
    upcoming_tasks = []
    thirty_days = today + timezone.timedelta(days=30)

    for client in clients:
        all_tasks = sorted(client.compliance_tasks.all(), key=lambda t: t.due_date)
        for task in all_tasks:
            if task.status == 'overdue':
                overdue_tasks.append({
                    'client': client, 'task': task,
                    'days_overdue': (today - task.due_date).days,
                })
            elif task.status == 'pending' and today <= task.due_date <= thirty_days:
                upcoming_tasks.append({
                    'client': client, 'task': task,
                    'days_left': (task.due_date - today).days,
                })

    missing_docs_clients = []
    for client in clients:
        if client.status in ('not_started', 'in_progress'):
            missing = _get_missing_items(client)
            if missing:
                missing_docs_clients.append({'client': client, 'missing': missing})

    week_count = sum(1 for t in upcoming_tasks if t['days_left'] <= 7)
    month_count = len(upcoming_tasks)

    return render(request, 'clients/reminders.html', {
        'overdue_tasks': overdue_tasks, 'upcoming_tasks': upcoming_tasks,
        'missing_docs_clients': missing_docs_clients,
        'overdue_count': len(overdue_tasks), 'week_count': week_count,
        'month_count': month_count, 'missing_docs_count': len(missing_docs_clients),
        'sent_message': sent_message,
    })
