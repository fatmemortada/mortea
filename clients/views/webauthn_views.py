"""FaceID / WebAuthn biometric login views."""
import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import login, authenticate
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from ..models import WebAuthnCredential, BiometricSession, log_activity
from ..utils.webauthn_service import (
    create_registration_options, verify_registration,
    create_authentication_options, verify_authentication,
)


@login_required
def webauthn_settings(request):
    """Manage biometric credentials in user settings."""
    credentials = WebAuthnCredential.objects.filter(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'remove_credential':
            cred_id = request.POST.get('credential_id')
            WebAuthnCredential.objects.filter(
                user=request.user, credential_id=cred_id
            ).delete()
            messages.success(request, 'Biometric credential removed.')
            return redirect('webauthn_settings')

    return render(request, 'clients/webauthn_settings.html', {
        'credentials': credentials,
        'has_biometrics': credentials.exists(),
    })


@login_required
def webauthn_register_begin(request):
    """Begin WebAuthn credential registration — returns creation options."""
    existing = WebAuthnCredential.objects.filter(user=request.user)
    options = create_registration_options(request.user, existing)
    request.session['webauthn_registration_challenge'] = options['challenge']
    return JsonResponse(options)


@login_required
def webauthn_register_complete(request):
    """Complete WebAuthn credential registration — verify attestation."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    try:
        data = json.loads(request.body)
        success, credential, error = verify_registration(request.user, data)

        if success:
            # Record biometric session
            BiometricSession.objects.create(
                user=request.user, credential=credential, success=True,
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                device_info={'type': credential.device_type, 'name': credential.device_name},
            )
            log_activity(None, f'Biometric credential registered: {credential.device_name}', request.user)
            return JsonResponse({
                'success': True,
                'device_name': credential.device_name,
                'message': f'{credential.device_name} registered successfully!',
            })
        else:
            BiometricSession.objects.create(
                user=request.user, success=False,
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            return JsonResponse({'success': False, 'error': error}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def webauthn_auth_begin(request):
    """Begin WebAuthn authentication (biometric login)."""
    # User must be identified first (email input on login page)
    email = request.GET.get('email') or request.session.get('pending_biometric_email')
    if not email:
        return JsonResponse({'error': 'Email required'}, status=400)

    from django.contrib.auth.models import User
    user = User.objects.filter(email=email).first()
    if not user:
        return JsonResponse({'error': 'User not found'}, status=404)

    credentials = WebAuthnCredential.objects.filter(user=user)
    if not credentials.exists():
        return JsonResponse({'error': 'No biometric credentials registered'}, status=404)

    options = create_authentication_options(user, credentials)
    request.session['webauthn_auth_challenge'] = options['challenge']
    request.session['pending_biometric_user_id'] = user.id
    return JsonResponse(options)


def webauthn_auth_complete(request):
    """Complete WebAuthn authentication — verify assertion and log in."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    try:
        data = json.loads(request.body)
        user_id = request.session.get('pending_biometric_user_id')
        if not user_id:
            return JsonResponse({'error': 'No pending authentication'}, status=400)

        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)

        success, credential, error = verify_authentication(user, data)

        if success:
            # Log the user in
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            # Record session
            BiometricSession.objects.create(
                user=user, credential=credential, success=True,
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                device_info={'type': credential.device_type if credential else 'unknown',
                             'name': credential.device_name if credential else 'Unknown'},
            )

            # Clean up session
            request.session.pop('pending_biometric_user_id', None)
            request.session.pop('pending_biometric_email', None)

            log_activity(None, f'Biometric login: {credential.device_name if credential else "Unknown"}', user)
            return JsonResponse({
                'success': True,
                'redirect': '/dashboard/',
                'message': 'Logged in with biometrics!',
            })
        else:
            BiometricSession.objects.create(
                user=user, success=False,
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            return JsonResponse({'success': False, 'error': error}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def webauthn_session_history(request):
    """View biometric authentication history."""
    sessions = BiometricSession.objects.filter(
        user=request.user
    ).select_related('credential').order_by('-created_at')[:50]

    return render(request, 'clients/webauthn_history.html', {
        'sessions': sessions,
    })
