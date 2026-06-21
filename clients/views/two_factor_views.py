"""Two-factor authentication setup and verification."""
import io, base64
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
try:
    import qrcode
except ImportError:
    qrcode = None

from ..models.two_factor import TOTPDevice


@login_required
def setup_2fa(request):
    """Set up TOTP-based 2FA for the current user."""
    device, created = TOTPDevice.objects.get_or_create(user=request.user)
    if created:
        device.generate_secret()

    qr_data = None
    if not device.is_setup:
        uri = device.get_provisioning_uri(request.user.email)
        if qrcode:
            img = qrcode.make(uri)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            qr_data = base64.b64encode(buf.getvalue()).decode()

    if request.method == 'POST':
        if 'verify_setup' in request.POST:
            token = request.POST.get('token', '').strip()
            if device.verify_token(token):
                device.is_setup = True
                codes = device.generate_backup_codes()
                messages.success(request, '2FA enabled successfully! Save your backup codes.')
                return render(request, 'clients/setup_2fa.html', {
                    'device': device, 'qr_data': qr_data, 'setup_complete': True,
                    'backup_codes': codes,
                })
            messages.error(request, 'Invalid code. Try again.')
        elif 'disable_2fa' in request.POST:
            device.delete()
            messages.success(request, '2FA disabled.')
            return redirect('settings')

    return render(request, 'clients/setup_2fa.html', {
        'device': device, 'qr_data': qr_data,
    })


def verify_2fa(request):
    """Interstitial page after password login — requires TOTP code."""
    user_id = request.session.get('2fa_user_id')
    if not user_id:
        return redirect('login')

    from django.contrib.auth.models import User
    from django.contrib.auth import login

    error = ''
    try:
        user = User.objects.get(id=user_id)
        device = user.totp_device
    except (User.DoesNotExist, TOTPDevice.DoesNotExist):
        return redirect('login')

    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        if device.verify_token(token):
            device.last_used_at = __import__('django.utils.timezone', fromlist=['timezone']).timezone.now()
            device.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            request.session.pop('2fa_user_id', None)
            request.session['2fa_verified'] = True
            return redirect('dashboard')
        elif device.consume_backup_code(token):
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            request.session.pop('2fa_user_id', None)
            request.session['2fa_verified'] = True
            return redirect('dashboard')
        error = 'Invalid verification code.'

    return render(request, 'clients/verify_2fa.html', {'error': error})
