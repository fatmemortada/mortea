"""E-signature workflow views."""
import secrets
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from datetime import timedelta

from ..models import Client, OnboardingDocument, SignatureRequest, log_activity
from ._helpers import _get_firm


@login_required
def request_signature(request, document_id):
    """Accountant requests a signature on a document."""
    firm = _get_firm(request.user)
    document = get_object_or_404(OnboardingDocument, id=document_id, client__firm=firm)
    client = document.client
    success = False
    error = ""

    if request.method == "POST":
        signer_name = request.POST.get("signer_name", "").strip()
        signer_email = request.POST.get("signer_email", "").strip()
        message = request.POST.get("message", "").strip()

        if not signer_name or not signer_email:
            error = "Signer name and email are required."
        else:
            token = secrets.token_urlsafe(32)
            expires = timezone.now() + timedelta(days=7)

            sig_request = SignatureRequest.objects.create(
                document=document, client=client,
                requested_by=request.user,
                signer_name=signer_name, signer_email=signer_email,
                message=message, token=token, expires_at=expires,
            )

            site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
            sign_url = f"{site_url}/sign/{token}/"

            send_mail(
                subject=f"Signature requested — {document.document_name}",
                message=(
                    f"Hello {signer_name},\n\n"
                    f"{request.user.get_full_name() or request.user.email} has requested your signature "
                    f"on the document: {document.document_name}\n\n"
                    f"{message}\n\n" if message else ""
                    f"Click here to review and sign:\n{sign_url}\n\n"
                    f"This link expires in 7 days.\n\n"
                    f"— Mortacc"
                ),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mortacc.com'),
                recipient_list=[signer_email],
                fail_silently=True,
            )

            log_activity(request.user, 'sign', 'Document', document.id, document.document_name,
                        f'Requested signature from {signer_name} on {document.document_name}', firm=firm)
            success = True

    return render(request, 'clients/signature_request.html', {
        'document': document, 'client': client,
        'success': success, 'error': error,
    })


def sign_document(request, token):
    """Public signing page — recipient reviews and signs by typing their name."""
    sig_request = get_object_or_404(SignatureRequest, token=token)
    error = ""

    if sig_request.status == 'signed':
        return render(request, 'clients/sign_document.html', {
            'sig_request': sig_request, 'already_signed': True, 'error': '',
        })

    if sig_request.is_expired():
        sig_request.status = 'expired'
        sig_request.save()
        return render(request, 'clients/sign_document.html', {
            'sig_request': sig_request, 'expired': True, 'error': '',
        })

    if request.method == 'POST':
        signed_name = request.POST.get('signed_name', '').strip()
        if not signed_name:
            error = "Please type your full name to sign."
        else:
            sig_request.signed_name = signed_name
            sig_request.signed_ip = (
                request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                or request.META.get('REMOTE_ADDR', '')
            )
            sig_request.signed_at = timezone.now()
            sig_request.status = 'signed'
            sig_request.save()

            # Notify the requester
            if sig_request.requested_by:
                site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
                send_mail(
                    subject=f"Document signed — {sig_request.document.document_name}",
                    message=(
                        f"Hello,\n\n"
                        f"{signed_name} has signed {sig_request.document.document_name}.\n\n"
                        f"View document: {site_url}/clients/{sig_request.client.id}/\n\n"
                        f"— Mortacc"
                    ),
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mortacc.com'),
                    recipient_list=[sig_request.requested_by.email],
                    fail_silently=True,
                )

            log_activity(
                sig_request.requested_by, 'sign', 'Document',
                sig_request.document.id, sig_request.document.document_name,
                f'{signed_name} signed {sig_request.document.document_name}',
                firm=sig_request.client.firm,
            )

            return render(request, 'clients/sign_document.html', {
                'sig_request': sig_request, 'signed': True, 'error': '',
            })

    return render(request, 'clients/sign_document.html', {
        'sig_request': sig_request, 'error': error,
    })
