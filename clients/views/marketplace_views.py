"""Beauty Requests Marketplace — clients post requests, providers quote."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import models as django_models
from ..models import BeautyRequest, ProviderQuote, BeautyProvider


# ── Public: Submit Request ──────────────────────────────────────────────


def submit_request_view(request):
    """Client submits a beauty service request."""
    cities = BeautyProvider.objects.filter(is_active=True).values_list('city', flat=True).distinct().order_by('city')

    if request.method == 'POST':
        service = request.POST.get('service', '').strip()
        city = request.POST.get('city', '').strip()
        budget = request.POST.get('budget', '').strip()
        preferred_date = request.POST.get('preferred_date', '').strip() or None
        description = request.POST.get('description', '').strip()
        client_name = request.POST.get('client_name', '').strip()
        client_email = request.POST.get('client_email', '').strip()
        client_phone = request.POST.get('client_phone', '').strip()

        if not all([service, city, description, client_name, client_email]):
            return render(request, 'clients/marketplace/submit_request.html', {
                'error': 'Please fill in all required fields.',
                'cities': cities,
                'services': BeautyRequest.SERVICE_CHOICES,
            })

        req = BeautyRequest.objects.create(
            service=service, city=city, budget=budget,
            preferred_date=preferred_date, description=description,
            client_name=client_name, client_email=client_email,
            client_phone=client_phone,
        )
        return redirect('request_detail', request_id=req.id)

    return render(request, 'clients/marketplace/submit_request.html', {
        'cities': cities,
        'services': BeautyRequest.SERVICE_CHOICES,
    })


def request_detail_view(request, request_id):
    """View a request and its quotes."""
    req = get_object_or_404(BeautyRequest.objects.prefetch_related('quotes__provider'), id=request_id)
    matching_providers = BeautyProvider.objects.filter(
        is_active=True, city__iexact=req.city
    ).exclude(quotes__request=req)[:5]

    return render(request, 'clients/marketplace/request_detail.html', {
        'request': req,
        'matching_providers': matching_providers,
    })


# ── Provider: Leads Dashboard ───────────────────────────────────────────


def provider_leads_view(request, slug):
    """Provider views available leads in their city and sends quotes."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_active=True)

    if request.method == 'POST':
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')
        beauty_req = get_object_or_404(BeautyRequest, id=request_id)

        if action == 'quote':
            price = request.POST.get('price_estimate', '').strip()
            availability = request.POST.get('availability', '').strip()
            message = request.POST.get('message', '').strip()
            portfolio = request.POST.get('portfolio_links', '').strip()

            quote, created = ProviderQuote.objects.get_or_create(
                request=beauty_req, provider=provider,
                defaults={
                    'price_estimate': price, 'availability': availability,
                    'message': message, 'portfolio_links': portfolio,
                }
            )
            if created:
                beauty_req.quote_count = beauty_req.quotes.count()
                beauty_req.save()
                messages.success(request, 'Quote sent! The client will be notified.')
            else:
                messages.warning(request, 'You already quoted on this request.')
        return redirect('provider_leads', slug=provider.slug)

    # Available leads in same city
    available = BeautyRequest.objects.filter(
        status='open', city__iexact=provider.city
    ).exclude(quotes__provider=provider).order_by('-created_at')[:20]

    # My quotes
    my_quotes = ProviderQuote.objects.filter(
        provider=provider
    ).select_related('request').order_by('-created_at')

    won = my_quotes.filter(status='accepted').count()
    sent = my_quotes.count()

    return render(request, 'clients/marketplace/provider_leads.html', {
        'provider': provider,
        'available': available,
        'my_quotes': my_quotes,
        'won': won,
        'sent': sent,
    })


# ── Customer Dashboard ─────────────────────────────────────────────────


def customer_dashboard_view(request, email=None):
    """Customer views their requests and provider responses."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        return redirect('customer_dashboard_email', email=email)

    if not email:
        return render(request, 'clients/marketplace/customer_login.html')

    requests = BeautyRequest.objects.filter(
        client_email__iexact=email
    ).prefetch_related('quotes__provider').order_by('-created_at')

    if request.method == 'POST' and request.POST.get('action') == 'accept':
        quote_id = request.POST.get('quote_id')
        quote = get_object_or_404(ProviderQuote, id=quote_id)
        quote.status = 'accepted'
        quote.save()
        quote.request.status = 'closed'
        quote.request.accepted_quote = quote
        quote.request.save()
        messages.success(request, f'You accepted the quote from {quote.provider.name}!')

    return render(request, 'clients/marketplace/customer_dashboard.html', {
        'requests': requests,
        'email': email,
    })


# ── Admin Analytics ────────────────────────────────────────────────────


def lead_analytics_view(request):
    """Admin dashboard for lead marketplace analytics."""
    total_requests = BeautyRequest.objects.count()
    open_requests = BeautyRequest.objects.filter(status='open').count()
    closed_requests = BeautyRequest.objects.filter(status='closed').count()
    total_quotes = ProviderQuote.objects.count()
    accepted_quotes = ProviderQuote.objects.filter(status='accepted').count()
    conversion_rate = round(accepted_quotes / total_quotes * 100, 1) if total_quotes else 0

    top_providers = (
        ProviderQuote.objects.values('provider__name', 'provider__slug')
        .annotate(c=django_models.Count('id'), won=django_models.Count('id', filter=django_models.Q(status='accepted')))
        .order_by('-c')[:10]
    )

    return render(request, 'clients/marketplace/admin_analytics.html', {
        'total_requests': total_requests,
        'open_requests': open_requests,
        'closed_requests': closed_requests,
        'total_quotes': total_quotes,
        'accepted_quotes': accepted_quotes,
        'conversion_rate': conversion_rate,
        'top_providers': top_providers,
    })
