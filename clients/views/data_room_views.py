"""Due Diligence Data Room views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import date, timedelta

from ..models import (
    Client, DataRoom, DataRoomDocument, DataRoomAccess, DataRoomInvite,
    SubscriptionInvoice, EntitySubscription, log_activity,
)
from ._helpers import _get_firm


@login_required
def data_room_list(request):
    """List all data rooms for the firm."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    rooms = DataRoom.objects.filter(firm=firm).select_related('client').order_by('-created_at')
    active = [r for r in rooms if r.is_active]

    return render(request, 'clients/data_room_list.html', {
        'firm': firm, 'rooms': rooms, 'active': active,
    })


@login_required
def data_room_create(request, client_id=None):
    """Create a new data room."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)
    else:
        client = None

    clients = Client.objects.filter(firm=firm)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        cid = request.POST.get('client_id', client_id)
        access_level = request.POST.get('access_level', 'restricted')
        require_nda = request.POST.get('require_nda') == '1'
        watermark_text = request.POST.get('watermark_text', '').strip()
        expires_in_days = int(request.POST.get('expires_in_days', 90))
        create_subscription = request.POST.get('create_subscription') == '1'

        client = get_object_or_404(Client, id=cid, firm=firm)

        room = DataRoom.objects.create(
            firm=firm, client=client, created_by=request.user,
            name=name, description=description,
            access_level=access_level, require_nda=require_nda,
            watermark_text=watermark_text or f'CONFIDENTIAL — {client.name}',
            status='active', opens_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=expires_in_days),
            auto_archive_days=expires_in_days,
        )

        # Optionally create a subscription for billing
        if create_subscription:
            from ..models import SubscriptionPlan
            plan = SubscriptionPlan.objects.filter(name__icontains='data room').first()
            if plan:
                sub = EntitySubscription.objects.create(
                    client=client, plan=plan, firm=firm,
                    status='active', billing_cycle='monthly',
                    current_period_start=date.today(),
                    current_period_end=date.today() + timedelta(days=30),
                    next_billing_date=date.today() + timedelta(days=30),
                )
                room.is_paid = True
                room.save()

        log_activity(client, f'Data room created: {name}', request.user)
        messages.success(request, f'Data room "{name}" created!')
        return redirect('data_room_detail', room_id=room.id)

    return render(request, 'clients/data_room_create.html', {
        'firm': firm, 'client': client, 'clients': clients,
    })


@login_required
def data_room_detail(request, room_id):
    """Manage a data room — upload docs, invite viewers, track activity."""
    firm = _get_firm(request.user)
    room = get_object_or_404(DataRoom, id=room_id, firm=firm)
    documents = room.documents.all()
    invitations = room.invites.all()
    access_logs = room.access_logs.order_by('-last_accessed')[:50]

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'upload_document' and request.FILES.get('file'):
            uploaded = request.FILES['file']
            doc = DataRoomDocument.objects.create(
                room=room,
                name=request.POST.get('name', uploaded.name),
                description=request.POST.get('description', ''),
                file=uploaded,
                category=request.POST.get('category', 'corporate'),
                file_size=uploaded.size,
                is_confidential=request.POST.get('is_confidential') == '1',
            )
            room.total_documents = documents.count() + 1
            room.save()
            log_activity(room.client, f'Document uploaded to data room: {doc.name}', request.user)

        elif action == 'invite':
            emails = [e.strip() for e in request.POST.get('emails', '').split(',') if e.strip()]
            message = request.POST.get('message', '').strip()
            for email in emails:
                invite = DataRoomInvite.objects.create(
                    room=room, email=email, inviter=request.user, message=message,
                    expires_at=timezone.now() + timedelta(days=30),
                )
                # Send email
                access_url = f"{getattr(settings, 'SITE_URL', '')}/dataroom/{room.access_code}/?token={invite.access_token}"
                send_mail(
                    subject=f'Data Room Invitation: {room.name}',
                    message=f'You have been invited to access the data room "{room.name}".\n\n{message}\n\nAccess link: {access_url}\n\nThis link expires in 30 days.',
                    from_email='support@mortacc.com',
                    recipient_list=[email],
                    fail_silently=True,
                )
                invite.is_sent = True
                invite.save()
            messages.success(request, f'Invited {len(emails)} viewer(s).')

        elif action == 'close':
            room.status = 'archived'
            room.save()
            messages.success(request, 'Data room archived.')

        elif action == 'extend':
            days = int(request.POST.get('extend_days', 30))
            if room.expires_at:
                room.expires_at = room.expires_at + timedelta(days=days)
            else:
                room.expires_at = timezone.now() + timedelta(days=days)
            room.save()
            messages.success(request, f'Data room extended by {days} days.')

        return redirect('data_room_detail', room_id=room.id)

    return render(request, 'clients/data_room_detail.html', {
        'firm': firm, 'room': room, 'documents': documents,
        'invitations': invitations, 'access_logs': access_logs,
    })


def data_room_access(request, access_code):
    """Public access to a data room (no login required if access is 'link' or 'public')."""
    room = get_object_or_404(DataRoom, access_code=access_code)

    if not room.is_active:
        return HttpResponse('This data room has expired or is no longer active.', status=410)

    token = request.GET.get('token')
    invite = None
    if token:
        invite = DataRoomInvite.objects.filter(access_token=token, room=room).first()
        if invite and not invite.is_accepted:
            invite.is_accepted = True
            invite.accepted_at = timezone.now()
            invite.save()

    # Track access
    viewer_email = request.GET.get('email', '') or (invite.email if invite else '')
    access = DataRoomAccess.objects.create(
        room=room,
        viewer_email=viewer_email,
        ip_address=request.META.get('REMOTE_ADDR', ''),
        nda_accepted=request.POST.get('nda_accepted') == '1',
    )

    if room.require_nda and not access.nda_accepted:
        return render(request, 'clients/data_room_nda.html', {
            'room': room, 'access': access,
        })

    documents = room.documents.all()
    access.total_views = 1
    access.save()
    room.total_views += 1
    room.save()

    return render(request, 'clients/data_room_view.html', {
        'room': room, 'documents': documents, 'access': access,
    })
