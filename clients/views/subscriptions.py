"""
Entity subscription management views.

Handles:
- Subscription plan catalog
- Entity subscription creation, management, cancellation
- Billing cycle management
- Subscription analytics
"""
import os
import stripe
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Count, Q
from django.conf import settings
from datetime import date, timedelta

from ..models import (
    Client, Firm, UserProfile,
    SubscriptionPlan, EntitySubscription, SubscriptionInvoice,
    Invoice, log_activity,
)
from ._helpers import _get_firm, require_permission

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

SITE_URL = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')


@login_required
@require_permission('subscriptions', 'view')
def subscription_plans_view(request):
    """Show available subscription plans for entities."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order')

    # Get firm's current entity subscriptions for context
    entity_subs = EntitySubscription.objects.filter(
        firm=firm
    ).select_related('client', 'plan').order_by('-created_at')

    total_mrr = sum(s.monthly_revenue for s in entity_subs if s.is_active)
    active_count = entity_subs.filter(status='active').count()
    total_subscribed = entity_subs.filter(status__in=['active', 'trialing', 'past_due']).count()

    clients_without_subs = Client.objects.filter(
        firm=firm
    ).exclude(
        id__in=entity_subs.values_list('client_id', flat=True)
    )

    return render(request, 'clients/subscription_plans.html', {
        'firm': firm,
        'plans': plans,
        'entity_subs': entity_subs,
        'total_mrr': total_mrr,
        'active_count': active_count,
        'total_subscribed': total_subscribed,
        'clients_without_subs': clients_without_subs,
        'stripe_publishable_key': os.environ.get('STRIPE_PUBLISHABLE_KEY', ''),
    })


@login_required
def entity_subscription_create(request, client_id):
    """Create a new subscription for a client entity."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    # Allow form override when posting from subscription_plans page (client_id=0 placeholder)
    if client_id == 0 and request.method == 'POST':
        override_id = request.POST.get('client_id_override')
        if override_id:
            client = get_object_or_404(Client, id=override_id, firm=firm)
        else:
            messages.error(request, 'Please select an entity.')
            return redirect('subscription_plans')
    else:
        client = get_object_or_404(Client, id=client_id, firm=firm)

    # Check if already subscribed
    existing = EntitySubscription.objects.filter(
        client=client, status__in=['active', 'trialing', 'past_due']
    ).first()
    if existing:
        messages.warning(request, f'{client.name} already has an active subscription.')
        return redirect('subscription_plans')

    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order')

    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        billing_cycle = request.POST.get('billing_cycle', 'annual')
        custom_price = request.POST.get('custom_price') or None
        create_stripe = request.POST.get('create_stripe_subscription') == '1'

        plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)

        # Calculate price
        price_map = {
            'monthly': plan.price_monthly,
            'annual': plan.price_annual,
            'quarterly': plan.price_quarterly,
        }
        price_cents = price_map.get(billing_cycle, plan.price_monthly)

        if custom_price:
            try:
                custom_price = int(float(custom_price) * 100)
            except (ValueError, TypeError):
                custom_price = None

        today = date.today()
        if billing_cycle == 'monthly':
            period_end = today + timedelta(days=30)
        elif billing_cycle == 'quarterly':
            period_end = today + timedelta(days=90)
        else:
            period_end = today + timedelta(days=365)

        # Create the subscription with Stripe
        stripe_sub_id = ''
        if create_stripe and plan.stripe_price_id_annual:
            try:
                customer_id = request.user.userprofile.stripe_customer_id
                if customer_id:
                    sub = stripe.Subscription.create(
                        customer=customer_id,
                        items=[{'price': plan.stripe_price_id_annual}],
                        metadata={
                            'client_id': str(client.id),
                            'firm_id': str(firm.id),
                            'plan': plan.name,
                        },
                    )
                    stripe_sub_id = sub.id
            except stripe.error.StripeError as e:
                import logging
                logging.getLogger(__name__).error(f'Stripe subscription error: {e}')
                messages.error(request, f'Payment processing error: {e}')
                return redirect('subscription_plans')

        sub = EntitySubscription.objects.create(
            client=client,
            plan=plan,
            firm=firm,
            status='active',
            billing_cycle=billing_cycle,
            current_period_start=today,
            current_period_end=period_end,
            next_billing_date=period_end,
            custom_price_override=custom_price,
            stripe_subscription_id=stripe_sub_id,
            auto_renew=True,
        )

        # Generate first invoice
        inv = Invoice.objects.create(
            client=client,
            description=f'Entity Subscription: {plan.name} ({billing_cycle})',
            service_type='subscription',
            amount=(custom_price or price_cents) / 100,
            status='sent',
            invoice_date=today,
            due_date=today + timedelta(days=30),
            auto_generated=True,
        )
        SubscriptionInvoice.objects.create(
            subscription=sub,
            invoice=inv,
            billing_period_start=today,
            billing_period_end=period_end,
            amount_charged=(custom_price or price_cents) / 100,
        )

        log_activity(client, f'Subscribed to {plan.name} plan (${(custom_price or price_cents)/100:.2f}/{billing_cycle})', request.user)
        messages.success(request, f'{client.name} is now subscribed to {plan.name}!')
        return redirect('subscription_plans')

    return render(request, 'clients/subscription_create.html', {
        'firm': firm,
        'client': client,
        'plans': plans,
    })


@login_required
def entity_subscription_manage(request, subscription_id):
    """Manage an existing subscription — change plan, cancel, update billing."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    sub = get_object_or_404(
        EntitySubscription.objects.select_related('client', 'plan'),
        id=subscription_id, firm=firm
    )

    plans = SubscriptionPlan.objects.filter(is_active=True).exclude(id=sub.plan.id)
    invoices = SubscriptionInvoice.objects.filter(subscription=sub).select_related('invoice').order_by('-created_at')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'change_plan':
            new_plan_id = request.POST.get('plan_id')
            new_plan = get_object_or_404(SubscriptionPlan, id=new_plan_id, is_active=True)
            new_cycle = request.POST.get('billing_cycle') or sub.billing_cycle
            sub.change_plan(new_plan, new_cycle)
            log_activity(sub.client, f'Changed subscription plan to {new_plan.name}', request.user)
            messages.success(request, f'Plan changed to {new_plan.name}.')

        elif action == 'cancel':
            reason = request.POST.get('cancellation_reason', '')
            sub.cancel(reason)
            log_activity(sub.client, 'Subscription canceled', request.user)
            messages.warning(request, f'Subscription for {sub.client.name} has been canceled.')

        elif action == 'resume':
            sub.status = 'active'
            sub.auto_renew = True
            sub.canceled_at = None
            sub.cancellation_reason = ''
            sub.save()
            log_activity(sub.client, 'Subscription resumed', request.user)
            messages.success(request, 'Subscription resumed.')

        elif action == 'pause':
            sub.status = 'paused'
            sub.save()
            log_activity(sub.client, 'Subscription paused', request.user)

        elif action == 'update_cycle':
            sub.billing_cycle = request.POST.get('billing_cycle', 'annual')
            sub.save()

        elif action == 'update_price':
            new_price = request.POST.get('custom_price')
            if new_price:
                try:
                    sub.custom_price_override = int(float(new_price) * 100)
                except (ValueError, TypeError):
                    pass
            else:
                sub.custom_price_override = None
            sub.save()

        return redirect('subscription_manage', subscription_id=sub.id)

    return render(request, 'clients/subscription_manage.html', {
        'firm': firm,
        'subscription': sub,
        'plans': plans,
        'invoices': invoices,
        'stripe_publishable_key': os.environ.get('STRIPE_PUBLISHABLE_KEY', ''),
    })


@login_required
@require_permission('subscriptions', 'view')
def subscription_analytics_view(request):
    """MRR/ARR analytics, churn, expansion revenue for the firm."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    all_subs = EntitySubscription.objects.filter(firm=firm)

    # MRR breakdown
    active_subs = all_subs.filter(status='active')
    mrr = sum(s.monthly_revenue for s in active_subs)
    arr = mrr * 12

    # By plan
    by_plan = active_subs.values('plan__name').annotate(
        count=Count('id'), mrr=Sum('custom_price_override')
    ).order_by('-mrr')
    for entry in by_plan:
        effective_mrr = 0
        for s in active_subs.filter(plan__name=entry['plan__name']):
            effective_mrr += s.monthly_revenue
        entry['effective_mrr'] = effective_mrr / 100

    # Churn this month
    month_ago = timezone.now() - timedelta(days=30)
    churned = all_subs.filter(status='canceled', canceled_at__gte=month_ago).count()
    churn_rate = (churned / max(all_subs.count(), 1)) * 100

    # New this month
    new_subs = all_subs.filter(created_at__gte=month_ago).count()

    # Expansion revenue (upgrades)
    # Track plan changes in the last 30 days

    # Upcoming renewals (next 30 days)
    next_30 = date.today() + timedelta(days=30)
    upcoming_renewals = all_subs.filter(
        status='active', next_billing_date__gte=date.today(), next_billing_date__lte=next_30
    ).select_related('client', 'plan').order_by('next_billing_date')

    today_plus_7 = date.today() + timedelta(days=7)

    return render(request, 'clients/subscription_analytics.html', {
        'firm': firm,
        'mrr': mrr / 100,
        'arr': arr / 100,
        'active_count': active_subs.count(),
        'total_subs': all_subs.count(),
        'by_plan': by_plan,
        'churned': churned,
        'churn_rate': round(churn_rate, 1),
        'new_subs': new_subs,
        'upcoming_renewals': upcoming_renewals,
        'today_plus_7': today_plus_7,
    })


@login_required
def subscription_api_summary(request):
    """API endpoint returning subscription summary as JSON."""
    firm = _get_firm(request.user)
    if not firm:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    active_subs = EntitySubscription.objects.filter(firm=firm, status='active')
    mrr = sum(s.monthly_revenue for s in active_subs)

    return JsonResponse({
        'active_subscriptions': active_subs.count(),
        'mrr': mrr / 100,
        'arr': (mrr * 12) / 100,
        'by_plan': [
            {
                'plan': plan_name,
                'count': active_subs.filter(plan__name=plan_name).count(),
            }
            for plan_name in sorted(set(active_subs.values_list('plan__name', flat=True)))
        ],
    })
