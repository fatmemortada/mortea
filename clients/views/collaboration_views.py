"""
Enhanced Cross-Firm Collaboration views.

Lawyer ↔ Accountant share entity records securely.
Granular permissions, shared compliance calendar, activity feeds.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from datetime import date, timedelta

from ..models import (
    Client, Firm, SharedMatter, SharedDocument, CollaborationTask, Approval,
    ComplianceTask, Document, log_activity,
)
from ._helpers import _get_firm


@login_required
def collaboration_hub(request):
    """Main collaboration hub showing shared matters and activity."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    # Matters where my firm is involved
    my_matters = SharedMatter.objects.filter(
        models.Q(collaborators=request.user) | models.Q(created_by=request.user)
    ).distinct().select_related('client').prefetch_related('collaborators').order_by('-created_at')

    # Pending approvals
    pending_approvals = Approval.objects.filter(
        models.Q(requested_by=request.user) | models.Q(approver=request.user),
        status='pending',
    ).select_related('matter__client').order_by('-created_at')

    # Shared compliance — matters with upcoming deadlines
    shared_compliance = ComplianceTask.objects.filter(
        client__shared_matters__in=my_matters,
        status__in=['pending', 'overdue'],
    ).select_related('client').order_by('due_date')[:20]

    # Find firms to collaborate with
    all_firms = Firm.objects.exclude(id=firm.id) if firm else []

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_matter':
            client_id = request.POST.get('client_id')
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            collaborator_emails = [e.strip() for e in request.POST.get('collaborator_emails', '').split(',') if e.strip()]
            share_compliance = request.POST.get('share_compliance') == '1'
            share_documents = request.POST.get('share_documents') == '1'

            client = get_object_or_404(Client, id=client_id, firm=firm)

            matter = SharedMatter.objects.create(
                client=client, title=title, description=description,
                created_by=request.user,
            )

            # Add collaborators by email
            for email in collaborator_emails:
                user = User.objects.filter(email=email).first()
                if user and user != request.user:
                    matter.collaborators.add(user)
                    # Send notification
                    send_mail(
                        subject=f'Collaboration Invitation: {client.name}',
                        message=f'{request.user.get_full_name() or request.user.email} has invited you to collaborate on:\n\n{client.name} — {title}\n\nAccess: {getattr(settings, "SITE_URL", "")}/collaboration/\n\nShared by Mortacc',
                        from_email='support@mortacc.com',
                        recipient_list=[email],
                        fail_silently=True,
                    )

            if share_compliance:
                matter.metadata = {'share_compliance': True}
            if share_documents:
                matter.metadata = {**(matter.metadata or {}), 'share_documents': True}
            matter.save()

            log_activity(client, f'Shared matter created: {title} with {len(collaborator_emails)} collaborator(s)', request.user)
            messages.success(request, f'Matter shared with {len(collaborator_emails)} collaborator(s)!')
            return redirect('collaboration_hub')

        elif action == 'add_document':
            matter_id = request.POST.get('matter_id')
            matter = get_object_or_404(SharedMatter, id=matter_id)
            if request.FILES.get('file'):
                uploaded = request.FILES['file']
                SharedDocument.objects.create(
                    matter=matter, name=uploaded.name, file=uploaded,
                    uploaded_by=request.user,
                )
                messages.success(request, 'Document shared.')

        elif action == 'create_approval':
            matter_id = request.POST.get('matter_id')
            matter = get_object_or_404(SharedMatter, id=matter_id)
            approver_email = request.POST.get('approver_email', '').strip()
            title = request.POST.get('approval_title', '').strip()
            description = request.POST.get('approval_description', '').strip()

            approver = User.objects.filter(email=approver_email).first()
            if approver and title:
                Approval.objects.create(
                    matter=matter, title=title, description=description,
                    requested_by=request.user, approver=approver,
                )
                send_mail(
                    subject=f'Approval Request: {title}',
                    message=f'{request.user.email} requests your approval for:\n\n{matter.client.name} — {title}\n\n{description}',
                    from_email='support@mortacc.com',
                    recipient_list=[approver_email],
                    fail_silently=True,
                )
                messages.success(request, 'Approval request sent.')

        elif action == 'approve':
            approval_id = request.POST.get('approval_id')
            approval = get_object_or_404(Approval, id=approval_id, approver=request.user)
            approval.status = 'approved'
            approval.approved_at = timezone.now()
            approval.comments = request.POST.get('comments', '')
            approval.save()
            log_activity(approval.matter.client, f'Approval granted: {approval.title}', request.user)

        elif action == 'reject':
            approval_id = request.POST.get('approval_id')
            approval = get_object_or_404(Approval, id=approval_id, approver=request.user)
            approval.status = 'rejected'
            approval.comments = request.POST.get('comments', '')
            approval.save()

        elif action == 'create_task':
            matter_id = request.POST.get('matter_id')
            matter = get_object_or_404(SharedMatter, id=matter_id)
            title = request.POST.get('task_title', '').strip()
            due_date_str = request.POST.get('task_due_date', '')
            assigned_email = request.POST.get('task_assigned', '').strip()

            if title:
                assigned = User.objects.filter(email=assigned_email).first()
                CollaborationTask.objects.create(
                    matter=matter, title=title,
                    description=request.POST.get('task_description', '').strip(),
                    assigned_to=assigned,
                    due_date=due_date_str or None,
                )
                messages.success(request, 'Task created.')

        elif action == 'complete_task':
            task_id = request.POST.get('task_id')
            task = get_object_or_404(CollaborationTask, id=task_id)
            task.status = 'completed'
            task.completed_at = timezone.now()
            task.completed_by = request.user
            task.save()

        return redirect('collaboration_hub')

    pending_tasks = CollaborationTask.objects.filter(
        models.Q(assigned_to=request.user) | models.Q(matter__created_by=request.user),
        status='pending',
    ).select_related('matter__client').order_by('due_date')

    return render(request, 'clients/collaboration_hub.html', {
        'firm': firm, 'my_matters': my_matters,
        'pending_approvals': pending_approvals,
        'shared_compliance': shared_compliance,
        'all_firms': all_firms,
        'pending_tasks': pending_tasks,
        'today': date.today(),
    })


@login_required
def collaboration_matter_detail(request, matter_id):
    """View details of a shared matter."""
    firm = _get_firm(request.user)
    matter = get_object_or_404(SharedMatter, id=matter_id)
    # Verify access
    if request.user != matter.created_by and request.user not in matter.collaborators.all():
        messages.error(request, 'You do not have access to this matter.')
        return redirect('collaboration_hub')

    documents = matter.documents.all()
    tasks = matter.tasks.all()
    approvals = matter.approvals.all()

    # Get shared compliance
    shared_compliance = []
    if getattr(matter, 'metadata', {}).get('share_compliance'):
        shared_compliance = ComplianceTask.objects.filter(
            client=matter.client,
            status__in=['pending', 'overdue'],
        ).order_by('due_date')

    # Get shared documents from the client
    shared_docs = []
    if getattr(matter, 'metadata', {}).get('share_documents'):
        shared_docs = Document.objects.filter(
            client=matter.client, is_client_visible=True,
        )

    return render(request, 'clients/collaboration_matter.html', {
        'firm': firm, 'matter': matter, 'documents': documents,
        'tasks': tasks, 'approvals': approvals,
        'shared_compliance': shared_compliance, 'shared_docs': shared_docs,
    })
