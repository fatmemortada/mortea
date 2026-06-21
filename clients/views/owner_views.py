"""Owner dashboard views — profile management for claimed businesses."""
import datetime
import random
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncMonth
from ..models import BeautyProvider, BeautyService, ProviderPhoto, ProviderReview, ClaimRequest, AnalyticsEvent, Booking, BeforeAfterResult


# ── Claim Flow ──────────────────────────────────────────────────────────


def claim_business_view(request, slug):
    """Page where a business owner requests to claim a provider profile."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_active=True)
    if provider.is_claimed:
        return redirect('owner_dashboard', slug=provider.slug)

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', '').strip()
        notes = request.POST.get('notes', '').strip()

        if not full_name or not email or not phone or not role:
            return render(request, 'clients/owner/claim_business.html', {
                'provider': provider,
                'error': 'Please fill in all required fields.',
            })

        # Generate verification code
        code = ''.join(random.choices(string.digits, k=6))

        # If user is logged in, link to user
        user = request.user if request.user.is_authenticated else None

        claim = ClaimRequest.objects.create(
            provider=provider,
            user=user,
            full_name=full_name,
            email=email,
            phone=phone,
            role_at_business=role,
            verification_code=code,
            notes=notes,
        )

        # In production, send email with code. For demo, show code on next page.
        return redirect('claim_verify', slug=provider.slug, claim_id=claim.id)

    return render(request, 'clients/owner/claim_business.html', {
        'provider': provider,
    })


def claim_verify_view(request, slug, claim_id):
    """Verification page — enter code to complete claim."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_active=True)
    claim = get_object_or_404(ClaimRequest, id=claim_id, provider=provider)

    if claim.status == 'verified':
        return redirect('owner_dashboard', slug=provider.slug)

    if request.method == 'POST':
        entered_code = request.POST.get('code', '').strip()
        if entered_code == claim.verification_code:
            claim.status = 'verified'
            claim.verified_at = timezone.now()
            claim.save()
            provider.owner = claim.user if claim.user else None
            provider.is_claimed = True
            provider.save()
            return redirect('claim_success', slug=provider.slug)
        else:
            return render(request, 'clients/owner/claim_verify.html', {
                'provider': provider,
                'claim': claim,
                'error': 'Invalid code. Please try again.',
            })

    return render(request, 'clients/owner/claim_verify.html', {
        'provider': provider,
        'claim': claim,
        'demo_code': claim.verification_code,  # Show in demo mode
    })


def claim_success_view(request, slug):
    """Claim successful — welcome page."""
    provider = get_object_or_404(BeautyProvider, slug=slug)
    return render(request, 'clients/owner/claim_success.html', {
        'provider': provider,
    })


# ── Owner Dashboard ─────────────────────────────────────────────────────


def owner_dashboard_view(request, slug):
    """Owner dashboard with overview and management links."""
    provider = get_object_or_404(
        BeautyProvider.objects.prefetch_related('services', 'bookings', 'reviews'),
        slug=slug,
        is_active=True,
        is_claimed=True,
    )
    recent_bookings = provider.bookings.order_by('-created_at')[:5]
    recent_reviews = provider.reviews.order_by('-created_at')[:5]

    return render(request, 'clients/owner/dashboard.html', {
        'provider': provider,
        'recent_bookings': recent_bookings,
        'recent_reviews': recent_reviews,
    })


@login_required
def owner_edit_profile_view(request, slug):
    """Edit business profile information."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_claimed=True)

    if request.method == 'POST':
        provider.name = request.POST.get('name', provider.name)
        provider.description = request.POST.get('description', provider.description)
        provider.address = request.POST.get('address', provider.address)
        provider.city = request.POST.get('city', provider.city)
        provider.province = request.POST.get('province', provider.province)
        provider.postal_code = request.POST.get('postal_code', provider.postal_code)
        provider.phone = request.POST.get('phone', provider.phone)
        provider.email = request.POST.get('email', provider.email)
        provider.website = request.POST.get('website', provider.website)
        provider.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('owner_dashboard', slug=provider.slug)

    return render(request, 'clients/owner/edit_profile.html', {
        'provider': provider,
    })


@login_required
def owner_manage_services_view(request, slug):
    """Manage services and pricing."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_claimed=True)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            BeautyService.objects.create(
                provider=provider,
                name=request.POST.get('name'),
                price=request.POST.get('price') or None,
                duration_minutes=request.POST.get('duration') or None,
                description=request.POST.get('description', ''),
                is_popular=request.POST.get('is_popular') == 'on',
            )
            messages.success(request, 'Service added.')
        elif action == 'delete':
            svc_id = request.POST.get('service_id')
            provider.services.filter(id=svc_id).delete()
            messages.success(request, 'Service removed.')
        elif action == 'edit':
            svc_id = request.POST.get('service_id')
            svc = get_object_or_404(provider.services, id=svc_id)
            svc.name = request.POST.get('name', svc.name)
            svc.price = request.POST.get('price') or None
            svc.duration_minutes = request.POST.get('duration') or None
            svc.description = request.POST.get('description', '')
            svc.is_popular = request.POST.get('is_popular') == 'on'
            svc.save()
            messages.success(request, 'Service updated.')
        return redirect('owner_services', slug=provider.slug)

    return render(request, 'clients/owner/services.html', {
        'provider': provider,
    })


@login_required
def owner_manage_photos_view(request, slug):
    """Manage photo and video gallery."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_claimed=True)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            photo_id = request.POST.get('photo_id')
            provider.photos.filter(id=photo_id).delete()
            messages.success(request, 'Photo removed.')
        elif action == 'add':
            caption = request.POST.get('caption', '')
            video_url = request.POST.get('video_url', '')
            image = request.FILES.get('image')
            if image or video_url:
                ProviderPhoto.objects.create(
                    provider=provider,
                    image=image if image else None,
                    video_url=video_url,
                    caption=caption,
                    order=provider.photos.count(),
                )
                messages.success(request, 'Media added to gallery.')
        return redirect('owner_photos', slug=provider.slug)

    return render(request, 'clients/owner/photos.html', {
        'provider': provider,
    })


@login_required
def owner_manage_social_view(request, slug):
    """Manage social media links."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_claimed=True)

    if request.method == 'POST':
        provider.instagram = request.POST.get('instagram', '')
        provider.tiktok = request.POST.get('tiktok', '')
        provider.facebook = request.POST.get('facebook', '')
        provider.whatsapp = request.POST.get('whatsapp', '')
        provider.website = request.POST.get('website', '')
        provider.save()
        messages.success(request, 'Social links updated.')
        return redirect('owner_dashboard', slug=provider.slug)

    return render(request, 'clients/owner/social.html', {
        'provider': provider,
    })


@login_required
def owner_manage_bookings_view(request, slug):
    """View and manage bookings."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_claimed=True)

    if request.method == 'POST':
        booking_id = request.POST.get('booking_id')
        new_status = request.POST.get('status')
        booking = get_object_or_404(provider.bookings, id=booking_id)
        if new_status in dict(provider.bookings.model.STATUS_CHOICES):
            booking.status = new_status
            booking.save()
            messages.success(request, f'Booking {new_status}.')
        return redirect('owner_bookings', slug=provider.slug)

    bookings = provider.bookings.order_by('-date', '-time')

    return render(request, 'clients/owner/bookings.html', {
        'provider': provider,
        'bookings': bookings,
    })


@login_required
def owner_respond_review_view(request, slug, review_id):
    """Respond to a client review."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_claimed=True)
    review = get_object_or_404(provider.reviews, id=review_id)

    if request.method == 'POST':
        review.reply = request.POST.get('reply', '').strip()
        review.replied_at = timezone.now()
        review.save()
        messages.success(request, 'Reply posted.')
        return redirect('owner_dashboard', slug=provider.slug)

    return render(request, 'clients/owner/respond_review.html', {
        'provider': provider,
        'review': review,
    })


# ── Click Tracking API ─────────────────────────────────────────────────


def track_click(request, slug):
    """API endpoint to track clicks on profile buttons (phone, website, social)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    provider = get_object_or_404(BeautyProvider, slug=slug, is_active=True)
    event_type = request.POST.get('event_type', '').strip()

    valid_events = dict(AnalyticsEvent.EVENT_TYPES)
    if event_type not in valid_events:
        return JsonResponse({'error': 'Invalid event type'}, status=400)

    AnalyticsEvent.objects.create(
        provider=provider,
        event_type=event_type,
        metadata={'source': request.META.get('HTTP_REFERER', '')},
    )

    return JsonResponse({'ok': True})


# ── Analytics Dashboard ────────────────────────────────────────────────


def owner_analytics_view(request, slug):
    """Analytics dashboard with charts and stats for claimed providers."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_claimed=True)

    today = timezone.now().date()
    days_7 = today - datetime.timedelta(days=7)
    days_30 = today - datetime.timedelta(days=30)
    months_12 = today - datetime.timedelta(days=365)

    events = provider.analytics_events

    # ── Stat Cards ──────────────────────────────────────────────────
    total_profile_views = events.filter(event_type='profile_view').count()
    total_search_appearances = events.filter(event_type='search_appearance').count()
    total_phone_clicks = events.filter(event_type='phone_click').count()
    total_website_clicks = events.filter(event_type='website_click').count()
    total_instagram_clicks = events.filter(event_type='instagram_click').count()
    total_tiktok_clicks = events.filter(event_type='tiktok_click').count()
    total_clicks = total_phone_clicks + total_website_clicks + total_instagram_clicks + total_tiktok_clicks
    booking_count = provider.bookings.count()
    review_count = provider.review_count
    avg_rating = float(provider.rating)

    # ── Chart data: last 7 days ─────────────────────────────────────
    def daily_counts(event_type, since):
        qs = (
            events.filter(event_type=event_type, created_at__date__gte=since)
            .annotate(d=TruncDate('created_at'))
            .values('d')
            .annotate(c=Count('id'))
            .order_by('d')
        )
        lookup = {r['d'].isoformat(): r['c'] for r in qs}
        dates = []
        counts = []
        d = since
        while d <= today:
            dates.append(d.strftime('%b %d'))
            counts.append(lookup.get(d.isoformat(), 0))
            d += datetime.timedelta(days=1)
        return dates, counts

    views_7d_dates, views_7d = daily_counts('profile_view', days_7)
    views_30d_dates, views_30d = daily_counts('profile_view', days_30)

    # Monthly for 12 months
    qs_monthly = (
        events.filter(event_type='profile_view', created_at__date__gte=months_12)
        .annotate(m=TruncMonth('created_at'))
        .values('m')
        .annotate(c=Count('id'))
        .order_by('m')
    )
    monthly_lookup = {r['m'].isoformat()[:7]: r['c'] for r in qs_monthly}
    views_12m_labels = []
    views_12m = []
    for i in range(11, -1, -1):
        m = (today.replace(day=1) - datetime.timedelta(days=i * 31)).replace(day=1)
        key = m.isoformat()[:7]
        views_12m_labels.append(m.strftime('%b %Y'))
        views_12m.append(monthly_lookup.get(key, 0))

    # ── Click breakdown ─────────────────────────────────────────────
    click_breakdown = {
        'phone': total_phone_clicks,
        'website': total_website_clicks,
        'instagram': total_instagram_clicks,
        'tiktok': total_tiktok_clicks,
    }

    # ── Notifications ───────────────────────────────────────────────
    recent_bookings = provider.bookings.filter(created_at__date__gte=days_30).order_by('-created_at')[:10]
    recent_reviews = provider.reviews.filter(created_at__date__gte=days_30).order_by('-created_at')[:5]
    recent_claims = provider.claim_requests.filter(created_at__date__gte=days_30).order_by('-created_at')[:5]

    notifications = []
    for b in recent_bookings:
        notifications.append({
            'type': 'booking',
            'icon': '📋',
            'text': f'New booking: {b.client_name} — {b.service.name if b.service else "Service"}',
            'date': b.created_at.strftime('%b %d, %I:%M %p'),
        })
    for r in recent_reviews:
        notifications.append({
            'type': 'review',
            'icon': '⭐',
            'text': f'New review from {r.author_name} ({r.rating}★)',
            'date': r.created_at.strftime('%b %d, %I:%M %p'),
        })
    notifications.sort(key=lambda n: n['date'], reverse=True)
    notifications = notifications[:15]

    return render(request, 'clients/owner/analytics.html', {
        'provider': provider,
        'total_profile_views': total_profile_views,
        'total_search_appearances': total_search_appearances,
        'total_clicks': total_clicks,
        'booking_count': booking_count,
        'review_count': review_count,
        'avg_rating': avg_rating,
        'click_breakdown': click_breakdown,
        'views_7d_dates': views_7d_dates,
        'views_7d': views_7d,
        'views_30d_dates': views_30d_dates,
        'views_30d': views_30d,
        'views_12m_labels': views_12m_labels,
        'views_12m': views_12m,
        'notifications': notifications,
    })


# ── Before & After Results Management ─────────────────────────────────


@login_required
def owner_manage_results_view(request, slug):
    """Manage before-and-after results for a claimed provider."""
    provider = get_object_or_404(BeautyProvider, slug=slug, is_claimed=True)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            BeforeAfterResult.objects.create(
                provider=provider,
                procedure_type=request.POST.get('procedure_type'),
                description=request.POST.get('description', ''),
                date=request.POST.get('date') or None,
                city=provider.city,
                is_published=request.POST.get('is_published') == 'on',
            )
            messages.success(request, 'Result added to gallery.')
        elif action == 'delete':
            result_id = request.POST.get('result_id')
            provider.before_after_results.filter(id=result_id).delete()
            messages.success(request, 'Result removed.')
        elif action == 'toggle':
            result_id = request.POST.get('result_id')
            result = get_object_or_404(provider.before_after_results, id=result_id)
            result.is_published = not result.is_published
            result.save()
            messages.success(request, f'Result {"published" if result.is_published else "unpublished"}.')
        return redirect('owner_results', slug=provider.slug)

    results = provider.before_after_results.order_by('-created_at')
    procedure_choices = BeforeAfterResult.PROCEDURE_CHOICES

    return render(request, 'clients/owner/results.html', {
        'provider': provider,
        'results': results,
        'procedure_choices': procedure_choices,
    })
