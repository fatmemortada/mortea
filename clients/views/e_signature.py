"""
E-Signature Views — OneSpan-like document signing workflow.

Envelope management, signing ceremony, audit trail, certificate.
"""
import secrets
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse
from datetime import timedelta

from ..models import (
    Client, ESignatureEnvelope, ESignatureSigner, ESignatureEvent,
    Document, log_activity,
)
from ._helpers import _get_firm


# ═══════════════════════════════════════════════════════════════════════
# FIRM-SIDE VIEWS
# ═══════════════════════════════════════════════════════════════════════

@login_required
def signature_dashboard(request):
    """Main e-signature dashboard — list all envelopes."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    envelopes = ESignatureEnvelope.objects.filter(firm=firm).select_related('client').prefetch_related('signers').order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        envelopes = envelopes.filter(status=status_filter)

    # Stats
    total = envelopes.count()
    completed = envelopes.filter(status='completed').count()
    pending = envelopes.filter(status__in=['sent', 'viewed', 'partially_signed']).count()
    drafts = envelopes.filter(status='draft').count()

    return render(request, 'clients/e_signature_dashboard.html', {
        'firm': firm, 'envelopes': envelopes,
        'total': total, 'completed': completed, 'pending': pending, 'drafts': drafts,
        'status_filter': status_filter,
    })


@login_required
def signature_envelope_create(request):
    """Create a new signature envelope — upload document and add signers."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    clients = Client.objects.filter(firm=firm)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        message = request.POST.get('message', '').strip()
        signing_order = request.POST.get('signing_order', 'sequential')
        client_id = request.POST.get('client_id') or None
        document_file = request.FILES.get('document_file')

        if not title:
            messages.error(request, 'Please provide a title for this signature package.')
            return redirect('signature_envelope_create')

        if not document_file:
            messages.error(request, 'Please upload a document to be signed.')
            return redirect('signature_envelope_create')

        client = Client.objects.filter(id=client_id, firm=firm).first() if client_id else None

        envelope = ESignatureEnvelope.objects.create(
            firm=firm, client=client, created_by=request.user,
            title=title, message=message,
            document_file=document_file,
            document_name=document_file.name,
            signing_order=signing_order,
            status='draft',
            expires_at=timezone.now() + timedelta(days=30),
        )

        # Log creation
        ESignatureEvent.objects.create(
            envelope=envelope, event_type='created',
            description=f'Envelope created by {request.user.get_full_name() or request.user.email}',
        )

        # Add signers from form
        signer_names = request.POST.getlist('signer_name')
        signer_emails = request.POST.getlist('signer_email')
        for i, (name, email) in enumerate(zip(signer_names, signer_emails)):
            name = name.strip()
            email = email.strip()
            if name and email:
                ESignatureSigner.objects.create(
                    envelope=envelope, name=name, email=email,
                    order=i, token=secrets.token_urlsafe(32),
                    status='pending',
                )

        if not envelope.signers.exists():
            messages.error(request, 'Please add at least one signer.')
            envelope.delete()
            return redirect('signature_envelope_create')

        log_activity(request.user, 'create', 'ESignatureEnvelope', envelope.id, envelope.title,
                     f'Created signature envelope: {envelope.title} ({envelope.signers_count} signers)', firm=firm)

        messages.success(request, f'Envelope created with {envelope.signers_count} signers. Review and send when ready.')
        return redirect('signature_envelope_detail', envelope_id=envelope.id)

    return render(request, 'clients/e_signature_create.html', {
        'firm': firm, 'clients': clients,
    })


@login_required
def signature_envelope_detail(request, envelope_id):
    """View an envelope — status, signers, audit trail, actions."""
    firm = _get_firm(request.user)
    envelope = get_object_or_404(ESignatureEnvelope, id=envelope_id, firm=firm)
    signers = envelope.signers.all()
    events = envelope.events.all()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'send':
            _send_envelope(envelope, request)
            messages.success(request, f'Envelope sent to {envelope.signers_count} signers!')
        elif action == 'void':
            envelope.status = 'voided'
            envelope.save()
            ESignatureEvent.objects.create(
                envelope=envelope, event_type='voided',
                description=f'Voided by {request.user.get_full_name() or request.user.email}',
            )
            messages.success(request, 'Envelope voided.')
        elif action == 'remind':
            _send_reminders(envelope, request)
            messages.success(request, 'Reminders sent to pending signers.')

        return redirect('signature_envelope_detail', envelope_id=envelope.id)

    return render(request, 'clients/e_signature_detail.html', {
        'firm': firm, 'envelope': envelope, 'signers': signers, 'events': events,
    })


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC SIGNING CEREMONY
# ═══════════════════════════════════════════════════════════════════════

def signing_ceremony(request, token):
    """Public signing page — the actual signing experience for recipients."""
    signer = get_object_or_404(ESignatureSigner, token=token)
    envelope = signer.envelope
    error = ""

    # Handle different states
    if signer.status == 'signed':
        return render(request, 'clients/e_signature_signing.html', {
            'signer': signer, 'envelope': envelope, 'already_signed': True,
        })

    if signer.status == 'declined':
        return render(request, 'clients/e_signature_signing.html', {
            'signer': signer, 'envelope': envelope, 'declined': True,
        })

    if envelope.status == 'voided':
        return render(request, 'clients/e_signature_signing.html', {
            'signer': signer, 'envelope': envelope, 'voided': True,
        })

    if envelope.status == 'expired' or signer.is_expired():
        if signer.status != 'expired':
            signer.status = 'expired'; signer.save()
            envelope.update_status()
        return render(request, 'clients/e_signature_signing.html', {
            'signer': signer, 'envelope': envelope, 'expired': True,
        })

    # Check signing order
    if envelope.signing_order == 'sequential':
        previous_signers = envelope.signers.filter(order__lt=signer.order).exclude(status='signed')
        if previous_signers.exists():
            return render(request, 'clients/e_signature_signing.html', {
                'signer': signer, 'envelope': envelope, 'waiting_for_others': True,
            })

    # Mark as viewed
    if signer.status in ('pending', 'sent'):
        signer.status = 'viewed'
        signer.viewed_at = timezone.now()
        signer.save()
        envelope.update_status()
        ip = _get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')[:500]
        ESignatureEvent.objects.create(
            envelope=envelope, signer=signer, event_type='viewed',
            description=f'{signer.name} viewed the document',
            ip_address=ip, user_agent=ua,
        )

    if request.method == 'POST':
        action = request.POST.get('action', 'sign')

        if action == 'decline':
            reason = request.POST.get('decline_reason', '').strip()
            signer.status = 'declined'
            signer.decline_reason = reason
            signer.save()
            envelope.update_status()
            ip = _get_client_ip(request)
            ESignatureEvent.objects.create(
                envelope=envelope, signer=signer, event_type='declined',
                description=f'{signer.name} declined to sign. Reason: {reason}',
                ip_address=ip,
            )
            _notify_firm(envelope, f'{signer.name} declined to sign {envelope.title}')
            return render(request, 'clients/e_signature_signing.html', {
                'signer': signer, 'envelope': envelope, 'declined': True,
            })

        elif action == 'sign':
            signed_name = request.POST.get('signed_name', '').strip()
            if not signed_name:
                error = "Please type your full name to apply your electronic signature."
            else:
                ip = _get_client_ip(request)
                ua = request.META.get('HTTP_USER_AGENT', '')[:500]
                signer.status = 'signed'
                signer.signed_name = signed_name
                signer.signed_ip = ip
                signer.user_agent = ua
                signer.signed_at = timezone.now()
                signer.save()
                envelope.update_status()

                ESignatureEvent.objects.create(
                    envelope=envelope, signer=signer, event_type='signed',
                    description=f'{signer.name} signed as "{signed_name}"',
                    ip_address=ip, user_agent=ua,
                )

                _notify_firm(envelope, f'{signed_name} has signed {envelope.title}')

                # If envelope completed, notify everyone
                if envelope.status == 'completed':
                    ESignatureEvent.objects.create(
                        envelope=envelope, event_type='completed',
                        description='All signers have completed. Envelope is fully signed.',
                    )
                    _notify_all_signers(envelope)
                    # Fire workflow trigger
                    from ..workflow_triggers import trigger_workflows
                    trigger_workflows('document_signed', envelope.firm_id, {
                        'client_id': envelope.client_id,
                        'envelope_id': envelope.id,
                        'document_title': envelope.title,
                    })

                # If sequential, notify next signer
                if envelope.signing_order == 'sequential' and envelope.status == 'partially_signed':
                    next_signer = envelope.signers.filter(status='pending').order_by('order').first()
                    if next_signer:
                        _send_signer_email(next_signer, envelope, request)

                return render(request, 'clients/e_signature_signing.html', {
                    'signer': signer, 'envelope': envelope, 'signed': True,
                })

    return render(request, 'clients/e_signature_signing.html', {
        'signer': signer, 'envelope': envelope, 'error': error,
    })


# ═══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def _send_envelope(envelope, request):
    """Send the envelope to all signers."""
    envelope.status = 'sent'
    envelope.save()
    site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')

    for signer in envelope.signers.all():
        signer.status = 'sent'
        signer.save()
        _send_signer_email(signer, envelope, request)
        ESignatureEvent.objects.create(
            envelope=envelope, signer=signer, event_type='sent',
            description=f'Sent to {signer.name} <{signer.email}>',
        )

    ESignatureEvent.objects.create(
        envelope=envelope, event_type='sent',
        description=f'Envelope sent to {envelope.signers_count} signers',
    )


def _send_signer_email(signer, envelope, request):
    """Send signing link email to one signer."""
    site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
    sign_url = f"{site_url}/signing/{signer.token}/"
    sender_name = request.user.get_full_name() or request.user.email if hasattr(request, 'user') else 'Mortacc'

    send_mail(
        subject=f"Signature Request — {envelope.title}",
        message=(
            f"Hello {signer.name},\n\n"
            f"{sender_name} has requested your signature on:\n"
            f"{envelope.title}\n\n"
            f"{envelope.message}\n\n" if envelope.message else ""
            f"📄 Document: {envelope.document_name}\n\n"
            f"Click here to review and sign:\n{sign_url}\n\n"
            f"This link is unique to you and expires on {envelope.expires_at.strftime('%B %d, %Y') if envelope.expires_at else 'N/A'}.\n\n"
            f"Do not share this link. Your electronic signature is legally binding.\n\n"
            f"— Mortacc E-Signature"
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mortacc.com'),
        recipient_list=[signer.email],
        fail_silently=True,
    )


def _send_reminders(envelope, request):
    """Send reminders to all pending signers."""
    for signer in envelope.signers.filter(status__in=['sent', 'viewed', 'pending']):
        signer.reminder_sent_at = timezone.now()
        signer.save()
        _send_signer_email(signer, envelope, request)
        ESignatureEvent.objects.create(
            envelope=envelope, signer=signer, event_type='reminded',
            description=f'Reminder sent to {signer.name}',
        )


def _notify_firm(envelope, message_text):
    """Notify the envelope creator about an event."""
    if envelope.created_by:
        site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
        send_mail(
            subject=f"E-Signature Update — {envelope.title}",
            message=(
                f"{message_text}\n\n"
                f"View envelope: {site_url}/e-signatures/{envelope.id}/\n\n"
                f"— Mortacc E-Signature"
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mortacc.com'),
            recipient_list=[envelope.created_by.email],
            fail_silently=True,
        )


def _notify_all_signers(envelope):
    """Notify all signers that the envelope is complete."""
    site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
    for signer in envelope.signers.all():
        send_mail(
            subject=f"Document Fully Signed — {envelope.title}",
            message=(
                f"Hello {signer.name},\n\n"
                f"All parties have signed {envelope.title}.\n\n"
                f"The signed document is available from the sender.\n\n"
                f"— Mortacc E-Signature"
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mortacc.com'),
            recipient_list=[signer.email],
            fail_silently=True,
        )


def _get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')
