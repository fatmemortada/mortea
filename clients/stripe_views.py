import stripe
import os
from django.conf import settings
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Firm, UserProfile

import logging as _logging
_stripe_key = os.environ.get('STRIPE_SECRET_KEY', '')
if not _stripe_key:
    _logging.getLogger(__name__).warning(
        'STRIPE_SECRET_KEY is not set — Stripe payments will not work.'
    )
stripe.api_key = _stripe_key

# ── Price ID map ──────────────────────────────────────────────────────────────
PRICE_IDS = {
    'starter': {
        'monthly': os.environ.get('STRIPE_PRICE_STARTER_MONTHLY', ''),
        'yearly':  os.environ.get('STRIPE_PRICE_STARTER_ANNUAL', ''),
    },
    'growth': {
        'monthly': os.environ.get('STRIPE_PRICE_GROWTH_MONTHLY', ''),
        'yearly':  os.environ.get('STRIPE_PRICE_GROWTH_ANNUAL', ''),
    },
    'pro': {
        'monthly': os.environ.get('STRIPE_PRICE_PRO_MONTHLY', ''),
        'yearly':  os.environ.get('STRIPE_PRICE_PRO_ANNUAL', ''),
    },
    'professional': {
        'monthly': os.environ.get('STRIPE_PRICE_PROFESSIONAL_MONTHLY', os.environ.get('STRIPE_PRICE_PRO_MONTHLY', '')),
        'yearly':  os.environ.get('STRIPE_PRICE_PROFESSIONAL_ANNUAL', os.environ.get('STRIPE_PRICE_PRO_ANNUAL', '')),
    },
    'corporate': {
        'monthly': os.environ.get('STRIPE_PRICE_CORPORATE_MONTHLY', ''),
        'yearly':  os.environ.get('STRIPE_PRICE_CORPORATE_ANNUAL', ''),
    },
    'corporatepro': {
        'monthly': os.environ.get('STRIPE_PRICE_CORPORATEPRO_MONTHLY', ''),
        'yearly':  os.environ.get('STRIPE_PRICE_CORPORATEPRO_ANNUAL', ''),
    },
}

# Canonical mapping: legacy bundle keys → canonical plan names
# Used by signup_success and upgrade_plan — single source of truth.
BUNDLE_TO_PLAN = {
    'starter':      'starter',
    'growth':       'growth',
    'pro':          'professional',
    'professional': 'professional',
    'corporatepro': 'enterprise',
    'enterprise':   'enterprise',
}

# Human-readable plan names for emails
PLAN_DISPLAY_NAMES = {
    'starter':      'Starter',
    'growth':       'Growth',
    'professional': 'Professional',
    'enterprise':   'Enterprise',
}


# ─────────────────────────────────────────────
# CREATE CHECKOUT SESSION
# ─────────────────────────────────────────────

def create_checkout_session(request, bundle, billing_cycle, pending_data):
    """
    Creates a Stripe Checkout session with 3-day free trial.
    bundle: 'starter' | 'growth' | 'pro'
    billing_cycle: 'monthly' | 'yearly'
    """
    plan_prices = PRICE_IDS.get(bundle, PRICE_IDS['growth'])
    price_id    = plan_prices.get(billing_cycle, plan_prices['monthly'])

    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price':    price_id,
                'quantity': 1,
            }],
            subscription_data={
                'trial_period_days': 3,
            },
            success_url=f"{site_url}/signup/success/?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{site_url}/signup/",
            metadata={
                'full_name':     pending_data.get('full_name', ''),
                'firm_name':     pending_data.get('firm_name', ''),
                'firm_code':     pending_data.get('firm_code', ''),
                'email':         pending_data.get('email', ''),
                'bundle':        bundle,
                'billing_cycle': billing_cycle,
            },
            customer_email=pending_data.get('email', ''),
        )
        return session
    except stripe.error.StripeError as e:
        import logging
        _logging.getLogger(__name__).error(f"Stripe error: {e}")
        return None


# ─────────────────────────────────────────────
# SIGNUP SUCCESS
# ─────────────────────────────────────────────

def signup_success(request):
    from django.contrib.auth import login
    from django.contrib.auth.models import User

    session_id = request.GET.get('session_id')
    if not session_id:
        return redirect('accountant_signup')

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        meta    = session.metadata or {}
        if hasattr(meta, '_data'):
            meta = meta._data

        full_name     = meta.get('full_name', '')
        firm_name     = meta.get('firm_name', '')
        firm_code     = meta.get('firm_code', '').upper()
        email         = meta.get('email', '')
        bundle        = meta.get('bundle', 'growth')
        billing_cycle = meta.get('billing_cycle', 'monthly')
        # Get password from session
        password = request.session.get('pending_password', '')
        # If session expired, generate a temp password and email it to user
        if not password:
            import secrets
            password = secrets.token_urlsafe(12)
            send_temp_password = True
        else:
            send_temp_password = False

        # Already created — just log in
        user = User.objects.filter(username=email).first()
        if user:
            login(
                    request,
                    user,
                    backend='django.contrib.auth.backends.ModelBackend'
            )
            return redirect('dashboard')

        # Firm code conflict
        if Firm.objects.filter(code=firm_code).exists():
            return redirect('accountant_signup')

        # Create firm and user
        firm, created = Firm.objects.get_or_create(
            name=firm_name,
            defaults={"code": firm_code},
        )

        parts = full_name.split()
        user  = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=parts[0] if parts else '',
            last_name=' '.join(parts[1:]) if len(parts) > 1 else '',
        )

        profile = user.userprofile
        profile.firm                   = firm
        profile.role                   = 'accountant'
        profile.stripe_customer_id     = session.customer
        profile.stripe_subscription_id = session.subscription
        profile.subscription_active    = True
        profile.billing_cycle          = billing_cycle
        profile.plan                   = BUNDLE_TO_PLAN.get(bundle, 'starter')
        profile.save()

        # Send temp password email if session expired
        if send_temp_password:
            from django.core.mail import send_mail
            msg = f"Hi {full_name},\n\nYour Mortacc account has been created.\n\nEmail: {email}\nTemporary password: {password}\n\nPlease login at https://mortacc.com/login/ and change your password in Settings.\n\nMortacc Team"
            send_mail(
                subject='Welcome to Mortacc - Your login details',
                message=msg,
                from_email='support@mortacc.com',
                recipient_list=[email],
                fail_silently=True,
            )

        login(
        request,
        user,
        backend="django.contrib.auth.backends.ModelBackend"
        )
        # Send welcome email
        try:
            from .emails import send_welcome_email
            canonical_plan = BUNDLE_TO_PLAN.get(bundle, 'starter')
            display_name = PLAN_DISPLAY_NAMES.get(canonical_plan, 'Professional')
            send_welcome_email(user, firm_name, display_name)
        except Exception:
            pass
        return redirect('sign_platform_agreement')

    except Exception as e:
        import logging, traceback
        _logging.getLogger(__name__).error(f"Signup success error: {e}")
        _logging.getLogger(__name__).error(traceback.format_exc())
        return redirect('accountant_signup')


# ─────────────────────────────────────────────
# STRIPE WEBHOOK
# ─────────────────────────────────────────────

@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload        = request.body
    sig_header     = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    logger = __logging.getLogger('clients')

    if not webhook_secret:
        logger.critical(
            'STRIPE_WEBHOOK_SECRET is not set — webhook signature verification is DISABLED. '
            'Set it immediately via: fly secrets set STRIPE_WEBHOOK_SECRET=your-webhook-secret'
        )

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            import json
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except stripe.error.SignatureVerificationError:
        logger.error('Stripe webhook signature verification failed')
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f'Stripe webhook parse error: {e}')
        return HttpResponse(status=400)

    event_type = event['type']
    logger.info(f'Stripe webhook received: {event_type}')

    if event_type == 'customer.subscription.deleted':
        _handle_subscription_cancelled(event['data']['object'])
    elif event_type == 'customer.subscription.updated':
        _handle_subscription_updated(event['data']['object'])
    elif event_type == 'invoice.payment_failed':
        _handle_payment_failed(event['data']['object'])
    elif event_type == 'checkout.session.completed':
        _handle_checkout_completed(event['data']['object'])
        _handle_booking_checkout_completed(event['data']['object'])
    elif event_type == 'account.updated':
        _handle_connect_account_updated(event['data']['object'])
    elif event_type == 'charge.refunded':
        _handle_booking_refund(event['data']['object'])
    else:
        logger.info(f'Unhandled Stripe event type: {event_type}')

    return HttpResponse(status=200)


def _handle_subscription_cancelled(subscription):
    try:
        profile = UserProfile.objects.get(stripe_customer_id=subscription.get('customer'))
        profile.subscription_active = False
        profile.save()
    except UserProfile.DoesNotExist:
        pass


def _handle_subscription_updated(subscription):
    try:
        profile = UserProfile.objects.get(stripe_customer_id=subscription.get('customer'))
        profile.subscription_active = subscription.get('status') in ('active', 'trialing')
        profile.save()
    except UserProfile.DoesNotExist:
        pass


def _handle_payment_failed(invoice):
    """Notify user when a payment fails and log the event."""
    logger = __logging.getLogger(__name__)
    try:
        profile = UserProfile.objects.get(stripe_customer_id=invoice.get('customer'))
        user = profile.user
        logger.warning(
            "Payment failed for %s (firm: %s, subscription: %s)",
            user.email,
            profile.firm.name if profile.firm else '—',
            profile.stripe_subscription_id,
        )
        # Notify the user
        from django.core.mail import send_mail
        send_mail(
            subject="Payment failed — Mortacc",
            message=(
                f"Hi {user.first_name or 'there'},\n\n"
                f"Your recent payment for your Mortacc subscription has failed.\n\n"
                f"Please update your payment method to avoid service interruption:\n"
                f"https://www.mortacc.com/settings/\n\n"
                f"If you have any questions, contact support@mortacc.com.\n\n"
                f"— The Mortacc Team"
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mortacc.com'),
            recipient_list=[user.email],
            fail_silently=True,
        )
    except UserProfile.DoesNotExist:
        logger.warning("Payment failed for unknown customer: %s", invoice.get('customer'))


def _handle_checkout_completed(session):
    """Handle checkout.session.completed — ensure subscription is activated."""
    logger = __logging.getLogger('clients')
    try:
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')
        if customer_id and subscription_id:
            profile = UserProfile.objects.get(stripe_customer_id=customer_id)
            if not profile.subscription_active:
                profile.subscription_active = True
                profile.stripe_subscription_id = subscription_id
                profile.save()
                logger.info(
                    'Checkout completed: activated subscription for %s (%s)',
                    profile.user.email, subscription_id,
                )
    except UserProfile.DoesNotExist:
        logger.warning(
            'Checkout completed for unknown customer: %s', session.get('customer')
        )
    except Exception:
        logger.error('Error handling checkout.session.completed', exc_info=True)


# ─────────────────────────────────────────────
# STRIPE CONNECT — BOOKING PAYMENT HANDLERS
# ─────────────────────────────────────────────


def _handle_booking_checkout_completed(session):
    """Handle checkout.session.completed for booking payments via Connect."""
    logger = __logging.getLogger('clients')
    meta = session.get('metadata', {}) or {}
    booking_id = meta.get('booking_id')

    if not booking_id:
        return  # Not a booking checkout — skip

    from decimal import Decimal
    from django.utils import timezone
    from .models import Booking, BookingPayment

    try:
        booking = Booking.objects.select_related('provider', 'service').get(id=booking_id)
    except Booking.DoesNotExist:
        logger.warning('Booking #%s not found for checkout completion', booking_id)
        return

    provider = booking.provider
    service = booking.service

    # Avoid duplicate payment records
    if hasattr(booking, 'payment'):
        return

    try:
        amount = Decimal(str(session.get('amount_total', 0))) / Decimal('100')
        commission_rate = provider.commission_rate
        application_fee = (amount * commission_rate).quantize(Decimal('0.01'))
        net_amount = amount - application_fee

        payment = BookingPayment.objects.create(
            booking=booking,
            stripe_payment_intent_id=session.get('payment_intent', ''),
            stripe_session_id=session.get('id', ''),
            amount=amount,
            application_fee=application_fee,
            net_amount=net_amount,
            currency=(session.get('currency', 'cad') or 'cad').upper(),
            status='completed',
            paid_at=timezone.now(),
        )

        booking.status = 'pending'
        booking.save(update_fields=['status'])

        logger.info(
            'Booking #%s payment: $%s total, $%s fee, $%s net to %s',
            booking_id, amount, application_fee, net_amount, provider.name,
        )

    except Exception:
        logger.error('Error processing booking checkout #%s', booking_id, exc_info=True)


def _handle_connect_account_updated(account):
    """Handle account.updated webhook — update provider Stripe Connect status."""
    logger = __logging.getLogger('clients')
    account_id = account.get('id', '')
    charges_enabled = account.get('charges_enabled', False)
    payouts_enabled = account.get('payouts_enabled', False)
    details_submitted = account.get('details_submitted', False)

    try:
        provider = BeautyProvider.objects.filter(stripe_account_id=account_id).first()
        if not provider:
            return

        was_complete = provider.stripe_onboarding_complete
        provider.stripe_onboarding_complete = details_submitted and charges_enabled

        if provider.stripe_onboarding_complete and not was_complete:
            logger.info('Provider %s completed Stripe Connect onboarding', provider.name)

        provider.save(update_fields=['stripe_onboarding_complete'])

    except Exception:
        logger.error('Error handling account.updated for %s', account_id, exc_info=True)


def _handle_booking_refund(charge):
    """Handle charge.refunded — update BookingPayment and cancel booking if fully refunded."""
    logger = __logging.getLogger('clients')
    payment_intent = charge.get('payment_intent', '')

    if not payment_intent:
        return

    from decimal import Decimal

    try:
        payment = BookingPayment.objects.filter(stripe_payment_intent_id=payment_intent).first()
        if not payment:
            return

        amount_refunded = Decimal(str(charge.get('amount_refunded', 0))) / Decimal('100')
        amount_charged = Decimal(str(charge.get('amount', 0))) / Decimal('100')

        if amount_refunded >= amount_charged:
            payment.status = 'refunded'
            booking = payment.booking
            booking.status = 'cancelled'
            booking.save(update_fields=['status'])
        else:
            payment.status = 'partially_refunded'

        payment.save(update_fields=['status'])

        logger.info(
            'Refund for PaymentIntent %s: $%s refunded of $%s',
            payment_intent, amount_refunded, amount_charged,
        )

    except Exception:
        logger.error('Error handling refund for %s', payment_intent, exc_info=True)


# ─────────────────────────────────────────────
# BILLING PORTAL
# ─────────────────────────────────────────────

@login_required
def billing_portal(request):
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    try:
        customer_id = request.user.userprofile.stripe_customer_id
        if not customer_id:
            return redirect('settings')
        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{site_url}/settings/",
        )
        return redirect(portal.url)
    except Exception:
        return redirect('settings')


# ─────────────────────────────────────────────
# UPGRADE PLAN
# ─────────────────────────────────────────────

@login_required
def upgrade_plan(request):
    """
    Show upgrade options and handle plan switching via Stripe.
    - If user has an active subscription: upgrade via Stripe subscription items (proration).
    - If somehow no subscription: fall back to new Checkout session.
    """
    profile = getattr(request.user, 'userprofile', None)
    if not profile:
        return redirect('dashboard')

    current_plan = profile.plan  # starter | professional | enterprise

    # Map plan → next upgrade target
    UPGRADE_PATH = {
        'starter':      'professional',
        'professional': 'enterprise',
        'enterprise':   None,  # already at top
    }
    target_plan = UPGRADE_PATH.get(current_plan)

    if request.method == 'POST':
        chosen_plan = request.POST.get('plan')  # professional | enterprise
        billing_cycle = profile.billing_cycle or 'monthly'

        # Map canonical plan names back to PRICE_IDS keys
        PLAN_TO_BUNDLE = {
            'professional': 'growth',
            'enterprise':   'pro',
        }
        bundle = PLAN_TO_BUNDLE.get(chosen_plan)
        if not bundle:
            return redirect('settings')

        price_id = PRICE_IDS.get(bundle, {}).get(billing_cycle, '')
        if not price_id:
            return redirect('settings')

        # If they have an active Stripe subscription, upgrade in-place (with proration)
        if profile.stripe_subscription_id:
            try:
                sub = stripe.Subscription.retrieve(profile.stripe_subscription_id)
                item_id = sub['items']['data'][0]['id']
                stripe.Subscription.modify(
                    profile.stripe_subscription_id,
                    items=[{'id': item_id, 'price': price_id}],
                    proration_behavior='create_prorations',
                    metadata={'plan': chosen_plan},
                )
                # Update locally immediately
                profile.plan = BUNDLE_TO_PLAN.get(bundle, profile.plan)
                profile.save()
                return redirect('upgrade_success')
            except stripe.error.StripeError as e:
                import logging
                _logging.getLogger(__name__).error(f"Stripe upgrade error: {e}")
                # Fall through to checkout if something went wrong
        
        # Fallback: new Checkout session
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='subscription',
                customer=profile.stripe_customer_id or None,
                line_items=[{'price': price_id, 'quantity': 1}],
                success_url=request.build_absolute_uri('/upgrade/success/?session_id={CHECKOUT_SESSION_ID}'),
                cancel_url=request.build_absolute_uri('/settings/#plan'),
                metadata={
                    'upgrade': 'true',
                    'plan': chosen_plan,
                    'user_id': str(request.user.id),
                },
            )
            return redirect(session.url)
        except stripe.error.StripeError as e:
            import logging
            _logging.getLogger(__name__).error(f"Stripe upgrade checkout error: {e}")
            return redirect('settings')

    # GET — show the upgrade page
    PLAN_DETAILS = {
        'professional': {
            'name': 'Professional',
            'price_monthly': 299,
            'price_yearly': 2990,
            'features': [
                'Up to 50 clients',
                'Engagement letters',
                'All onboarding tools',
                'Compliance dashboard',
                'PDF generators (EN + FR)',
                'Priority support',
            ],
        },
        'enterprise': {
            'name': 'Enterprise',
            'price_monthly': 499,
            'price_yearly': 4990,
            'features': [
                'Unlimited clients',
                'Everything in Professional',
                'API access',
                'Dedicated account manager',
                'Custom onboarding',
                'SLA guarantee',
            ],
        },
    }

    return render(request, 'clients/upgrade_plan.html', {
        'current_plan': current_plan,
        'target_plan': target_plan,
        'plan_details': PLAN_DETAILS,
        'billing_cycle': profile.billing_cycle or 'monthly',
    })


@login_required
def upgrade_success(request):
    """Landing page after a successful plan upgrade."""
    # If came from a new Checkout session, verify and update plan
    session_id = request.GET.get('session_id')
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            meta = session.metadata or {}
            plan = meta.get('plan', '')
            user_id = meta.get('user_id', '')
            if plan and str(request.user.id) == user_id:
                profile = request.user.userprofile
                profile.plan = plan
                profile.stripe_subscription_id = session.subscription or profile.stripe_subscription_id
                profile.subscription_active = True
                profile.save()
        except Exception:
            pass

    return render(request, 'clients/upgrade_success.html', {
        'plan': getattr(request.user.userprofile, 'plan', 'professional'),
    })
