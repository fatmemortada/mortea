"""Stripe Connect marketplace views — provider onboarding, payment, payouts."""
import os
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from .models import BeautyProvider

logger = logging.getLogger('clients')

# ── Connect Onboarding ─────────────────────────────────────────────────────


def connect_stripe_start(request, slug):
    """Initiate Stripe Connect Express onboarding for a provider."""
    import stripe
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

    provider = get_object_or_404(BeautyProvider, slug=slug, is_claimed=True)
    owner = getattr(provider, 'owner', None)

    if not request.user.is_staff and (not owner or request.user != owner):
        messages.error(request, 'Only the business owner can connect payments.')
        return redirect('owner_dashboard', slug=slug)

    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')

    if not provider.stripe_account_id:
        account = stripe.Account.create(
            type='express',
            country='CA',
            email=provider.email or (owner.email if owner else ''),
            business_type='individual',
            business_profile={
                'name': provider.name,
                'url': f'{site_url}/providers/{provider.slug}/',
                'product_description': (provider.description or provider.get_category_display())[:250],
            },
            capabilities={'transfers': {'requested': True}},
            metadata={
                'provider_id': str(provider.id),
                'provider_name': provider.name,
            },
        )
        provider.stripe_account_id = account.id
        provider.save(update_fields=['stripe_account_id'])

    account_link = stripe.AccountLink.create(
        account=provider.stripe_account_id,
        refresh_url=f'{site_url}/providers/{provider.slug}/connect/stripe/',
        return_url=f'{site_url}/providers/{provider.slug}/connect/return/',
        type='account_onboarding',
    )

    return redirect(account_link.url)


def connect_stripe_return(request, slug):
    """Handle return from Stripe Connect onboarding flow."""
    import stripe
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

    provider = get_object_or_404(BeautyProvider, slug=slug)
    owner = getattr(provider, 'owner', None)

    if not request.user.is_staff and (not owner or request.user != owner):
        return redirect('owner_dashboard', slug=slug)

    if provider.stripe_account_id:
        try:
            account = stripe.Account.retrieve(provider.stripe_account_id)
            provider.stripe_onboarding_complete = (
                account.get('details_submitted', False)
                and account.get('charges_enabled', False)
            )
            provider.save(update_fields=['stripe_onboarding_complete'])
            if provider.stripe_onboarding_complete:
                messages.success(request, 'Stripe Connect is now active. You can receive payments!')
            else:
                messages.warning(request, 'Stripe onboarding is not yet complete. Please finish all steps.')
        except stripe.error.StripeError as e:
            logger.error('Stripe account retrieve failed for %s: %s', provider.name, e)
            messages.error(request, 'Could not verify Stripe status. Please try again.')

    return redirect('owner_dashboard', slug=slug)


def connect_stripe_dashboard(request, slug):
    """Create a Stripe Express dashboard login link for the provider."""
    import stripe
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

    provider = get_object_or_404(BeautyProvider, slug=slug, stripe_onboarding_complete=True)
    owner = getattr(provider, 'owner', None)

    if not request.user.is_staff and (not owner or request.user != owner):
        return redirect('owner_dashboard', slug=slug)

    try:
        login_link = stripe.Account.create_login_link(provider.stripe_account_id)
        return redirect(login_link.url)
    except stripe.error.StripeError as e:
        logger.error('Stripe dashboard login failed for %s: %s', provider.name, e)
        messages.error(request, 'Could not access Stripe dashboard. Ensure your account is fully set up.')
        return redirect('owner_dashboard', slug=slug)
