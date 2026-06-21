from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse
from django_ratelimit.decorators import ratelimit
from django.utils import timezone
from datetime import timedelta
import secrets

from ..models import Firm, UserProfile, StaffInvite, PlatformAgreement
from ..emails import send_welcome_email, send_agreement_confirmation, send_staff_invite
from ._helpers import _get_firm, require_permission


@ratelimit(key='ip', rate='20/h', block=True)
def accountant_signup_view(request):
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        return HttpResponse("Too many signup attempts. Please try again later.", status=429)

    if request.user.is_authenticated:
        return redirect("dashboard")

    error_message = ""
    selected_bundle = "growth"
    billing_cycle = "monthly"
    payment_method = "card"

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        firm_name = request.POST.get("firm_name", "").strip()
        firm_code = request.POST.get("firm_code", "").strip().upper()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_pw = request.POST.get("confirm_password", "")
        selected_bundle = request.POST.get("bundle", "growth")
        billing_cycle = request.POST.get("billing_cycle", "monthly")
        payment_method = request.POST.get("payment_method", "card")

        if not all([full_name, firm_name, firm_code, email, password]):
            error_message = "All fields are required."
        elif len(firm_code) != 3 or not firm_code.isalpha():
            error_message = "Firm code must be exactly 3 letters."
        elif password != confirm_pw:
            error_message = "Passwords do not match."
        elif len(password) < 8:
            error_message = "Password must be at least 8 characters."
        elif User.objects.filter(username=email).exists():
            error_message = "An account with this email already exists."
        elif Firm.objects.filter(code=firm_code).exists():
            error_message = f"Firm code '{firm_code}' is already taken."
        else:
            from ..stripe_views import create_checkout_session
            bundle = request.POST.get("bundle", "growth")
            billing_cycle = request.POST.get("billing_cycle", "monthly")
            pending_data = {
                "full_name": full_name,
                "firm_name": firm_name,
                "firm_code": firm_code,
                "email": email,
                "password": password,
                "billing_cycle": billing_cycle,
                "bundle": bundle,
            }
            session = create_checkout_session(request, bundle, billing_cycle, pending_data)
            if session:
                request.session["pending_password"] = password
                request.session["pending_email"] = email
                return redirect(session.url)
            error_message = "Payment setup failed. Please try again."

    return render(request, "clients/accountant_signup.html", {
        "error_message": error_message,
        "selected_bundle": selected_bundle,
        "billing_cycle": billing_cycle,
        "payment_method": payment_method,
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    error_message = ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user:
            # Check if 2FA is enabled
            try:
                if user.totp_device and user.totp_device.is_setup:
                    request.session['2fa_user_id'] = user.id
                    return redirect('verify_2fa')
            except Exception:
                pass
            login(request, user)
            return redirect("dashboard")
        error_message = "Invalid username or password."

    return render(request, "clients/login.html", {"error_message": error_message})


@login_required
def logout_view(request):
    logout(request)
    return redirect("choose_login")


def choose_login_view(request):
    return render(request, "clients/choose_login.html")


@login_required
def sign_platform_agreement(request):
    profile = getattr(request.user, 'userprofile', None)
    if hasattr(request.user, 'platform_agreement'):
        return redirect('dashboard')

    firm_name = profile.firm.name if profile and profile.firm else ''
    prefill_name = request.user.get_full_name() or ''
    error = ''

    if request.method == 'POST':
        signed_name = request.POST.get('signed_name', '').strip()
        if not signed_name:
            error = 'Please type your full name to sign.'
        else:
            ip = (
                request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                or request.META.get('REMOTE_ADDR')
            )
            PlatformAgreement.objects.create(
                user=request.user,
                firm=profile.firm if profile else None,
                signed_name=signed_name,
                signed_email=request.user.email,
                ip_address=ip or None,
                agreement_version='v1',
            )
            try:
                pa = request.user.platform_agreement
                send_agreement_confirmation(
                    request.user,
                    profile.firm.name if profile and profile.firm else '',
                    signed_name,
                    pa.signed_at,
                )
            except Exception:
                pass
            return redirect('dashboard')

    return render(request, 'clients/platform_agreement.html', {
        'firm_name': firm_name,
        'prefill_name': prefill_name,
        'error': error,
    })


# ── Staff Management ────────────────────────────────────────────────────────

def _get_staff(firm):
    if not firm:
        return UserProfile.objects.none()
    return UserProfile.objects.filter(firm=firm).select_related('user').order_by('role', 'user__first_name')


@login_required
@require_permission('staff', 'create')
def staff_invite_view(request):
    firm = _get_firm(request.user)
    if not firm:
        return redirect('dashboard')

    profile = getattr(request.user, 'userprofile', None)
    if not profile or profile.role not in ('admin', 'accountant'):
        return redirect('settings')

    error = ''
    success = ''

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role', 'staff')

        if not email:
            error = 'Email is required.'
        elif User.objects.filter(username=email).exists():
            error = 'A user with that email already has a Mortacc account.'
        elif StaffInvite.objects.filter(firm=firm, email=email, accepted=False).exists():
            error = 'An invitation has already been sent to that email.'
        else:
            token = secrets.token_urlsafe(40)
            invite = StaffInvite.objects.create(
                firm=firm,
                invited_by=request.user,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
                token=token,
                expires_at=timezone.now() + timedelta(days=7),
            )
            try:
                send_staff_invite(invite)
                success = f'Invitation sent to {email}.'
            except Exception:
                success = f'Invite created but email failed — share this link manually: /staff/accept/{token}/'

        return render(request, 'clients/settings.html', {
            'firm': firm,
            'success_message': success,
            'error_message': error,
            'staff_members': _get_staff(firm),
            'pending_invites': StaffInvite.objects.filter(firm=firm, accepted=False),
        })

    return redirect('settings')


@login_required
@require_permission('staff', 'delete')
def staff_remove_view(request, user_id):
    firm = _get_firm(request.user)
    profile = getattr(request.user, 'userprofile', None)
    if not firm or not profile or profile.role not in ('admin', 'accountant'):
        return redirect('settings')

    if request.method == 'POST':
        try:
            target = UserProfile.objects.get(user_id=user_id, firm=firm)
            if target.user != request.user:
                target.firm = None
                target.save()
        except UserProfile.DoesNotExist:
            pass

    return redirect('settings')


@login_required
def staff_cancel_invite_view(request, invite_id):
    firm = _get_firm(request.user)
    profile = getattr(request.user, 'userprofile', None)
    if not firm or not profile or profile.role not in ('admin', 'accountant'):
        return redirect('settings')

    if request.method == 'POST':
        StaffInvite.objects.filter(id=invite_id, firm=firm, accepted=False).delete()

    return redirect('settings')


def staff_accept_view(request, token):
    try:
        invite = StaffInvite.objects.get(token=token, accepted=False)
    except StaffInvite.DoesNotExist:
        return render(request, 'clients/staff_accept.html', {'error': 'This invitation is invalid or has already been used.'})

    if invite.is_expired():
        return render(request, 'clients/staff_accept.html', {'error': 'This invitation has expired. Ask your firm admin to send a new one.'})

    error = ''
    if request.method == 'POST':
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')

        if len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif password != confirm:
            error = 'Passwords do not match.'
        else:
            user = User.objects.create_user(
                username=invite.email,
                email=invite.email,
                password=password,
                first_name=invite.first_name,
                last_name=invite.last_name,
            )
            profile = user.userprofile
            profile.firm = invite.firm
            profile.role = invite.role
            profile.subscription_active = True
            profile.save()

            invite.accepted = True
            invite.save()

            from django.contrib.auth import login as auth_login
            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('dashboard')

    return render(request, 'clients/staff_accept.html', {
        'invite': invite,
        'error': error,
    })


def demo_view(request):
    """Auto-provisions a demo firm with comprehensive sample data and logs the user in."""
    import secrets
    import traceback
    import logging
    logger = logging.getLogger('clients')
    from ..models import (
        Firm, UserProfile, PlatformAgreement,
        seed_system_roles, UserRoleAssignment, Role,
    )

    suffix = secrets.token_hex(3)
    demo_email = f"demo_{suffix}@mortacc.demo"
    demo_password = "Demo1234!"

    try:
        # Create firm and user
        firm = Firm.objects.create(
            name=f"Demo Firm {suffix}",
            code=suffix[:3].upper(),
        )
        user = User.objects.create_user(
            username=demo_email, email=demo_email,
            password=demo_password, first_name="Demo", last_name="User",
        )
        profile = user.userprofile
        profile.firm = firm
        profile.role = "accountant"
        profile.plan = "professional"
        profile.subscription_active = True
        profile.save()

        # Platform agreement + RBAC
        PlatformAgreement.objects.create(
            user=user, firm=firm,
            signed_name="Demo User", signed_email=demo_email,
        )
        seed_system_roles(firm)
        partner_role = Role.objects.get(firm=firm, name='Partner')
        UserRoleAssignment.objects.create(user=user, firm=firm, role=partner_role)

        # Seed comprehensive demo data
        clients = []
        try:
            from ..utils.demo_seeder import seed_demo_data
            clients = seed_demo_data(user, firm)
            logger.info(f"Demo seeded: {len(clients)} entities for firm {firm.code}")
        except Exception as seed_error:
            logger.error(f"Demo seeder failed: {traceback.format_exc()}")
            # Fall back to basic entity creation so demo still works
            try:
                from datetime import date as _date, timedelta as _td
                from ..models import Client, CorporateProfile, Director, Shareholder
                _today = _date.today()
                _entities = [
                    {"name": "Maple Tech Holdings Inc.", "jurisdiction": "federal", "inc_date": _today - _td(days=730), "bn": "123456789"},
                    {"name": "Great Lakes Consulting Ltd.", "jurisdiction": "ontario", "inc_date": _today - _td(days=365), "bn": "987654321"},
                    {"name": "Pacific Ventures Corp.", "jurisdiction": "bc", "inc_date": _today - _td(days=180), "bn": "456789123"},
                ]
                for e in _entities:
                    c = Client.objects.create(firm=firm, name=e["name"], email=f"info@{e['name'].lower().replace(' ', '')[:20]}.com", business_type="Technology", client_type="business", status="in_progress")
                    corp = CorporateProfile.objects.create(client=c, jurisdiction=e["jurisdiction"], incorporation_date=e["inc_date"], business_number=e["bn"], registered_address="123 Demo Street, Toronto, ON M5V 2T6", fiscal_year_end=_date(_today.year, 12, 31))
                    Director.objects.create(client=c, full_name="John Smith", appointment_date=e["inc_date"])
                    Director.objects.create(client=c, full_name="Jane Doe", appointment_date=e["inc_date"])
                    Shareholder.objects.create(client=c, full_name="John Smith", share_class="Common", num_shares=100)
                    Shareholder.objects.create(client=c, full_name="Jane Doe", share_class="Common", num_shares=40)
                    try:
                        from ..models.compliance import _create_compliance_tasks
                        _create_compliance_tasks(corp)
                    except Exception:
                        pass
                    clients.append(c)
                logger.info(f"Demo fallback: created {len(clients)} basic entities")
            except Exception as fallback_error:
                logger.error(f"Demo fallback also failed: {traceback.format_exc()}")
                raise

        # Log in
        from django.contrib.auth import login as auth_login
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        from django.contrib import messages
        messages.success(
            request,
            f"🎓 Welcome to your Mortacc demo! Pre-loaded with {len(clients)} sample "
            "entities with full corporate data: directors, shareholders, cap tables, "
            "compliance calendar, invoices, bookkeeping, KYC records, AI extractions, "
            "and more. Explore the Getting Started guide for a tour."
        )
        return redirect('dashboard')

    except Exception:
        # If anything fails, log and redirect to signup
        logger.error(f"Demo provisioning failed: {traceback.format_exc()}")
        from django.contrib import messages
        messages.error(
            request,
            "Sorry, demo provisioning failed. Please sign up for a free trial instead."
        )
        return redirect('accountant_signup')
