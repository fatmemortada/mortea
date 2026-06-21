"""Unified Mortea admin dashboard with platform analytics."""
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum, Q
from django.utils import timezone
from ..models import (
    BeautyProvider, Booking, ProviderReview, ClaimRequest,
    PortfolioPost, BeforeAfterResult, AnalyticsEvent, SentEmail,
)


@staff_member_required
def verification_dashboard_view(request):
    """Verification management — review and verify providers."""
    providers = BeautyProvider.objects.filter(is_active=True).order_by('-verification_score', '-rating')

    if request.method == 'POST':
        provider_id = request.POST.get('provider_id')
        action = request.POST.get('action')
        provider = get_object_or_404(BeautyProvider, id=provider_id)

        if action == 'recompute':
            provider.compute_verification()
            messages.success(request, f'{provider.name} verification recomputed. Score: {provider.verification_score}/5')
        elif action == 'verify':
            provider.is_verified = True
            provider.verification_score = max(provider.verification_score, 3)
            from django.utils import timezone
            provider.verified_at = timezone.now()
            provider.save()
            messages.success(request, f'{provider.name} manually verified.')
        elif action == 'unverify':
            provider.is_verified = False
            provider.save()
            messages.success(request, f'{provider.name} verification removed.')
        elif action == 'recompute_all':
            count = 0
            for p in BeautyProvider.objects.filter(is_active=True):
                p.compute_verification()
                count += 1
            messages.success(request, f'{count} providers recomputed.')
        return redirect('verification_dashboard')

    return render(request, 'clients/admin/verification.html', {
        'providers': providers,
    })


@staff_member_required
def admin_dashboard_view(request):
    """Unified Mortea admin — platform overview."""
    today = timezone.now().date()
    days_30 = today - timezone.timedelta(days=30)

    # Stats
    total_providers = BeautyProvider.objects.filter(is_active=True).count()
    total_claimed = BeautyProvider.objects.filter(is_claimed=True, is_active=True).count()
    total_unclaimed = total_providers - total_claimed
    total_bookings = Booking.objects.count()
    pending_bookings = Booking.objects.filter(status='pending').count()
    total_reviews = ProviderReview.objects.count()
    total_posts = PortfolioPost.objects.filter(is_published=True).count()
    total_results = BeforeAfterResult.objects.filter(is_published=True).count()
    pending_claims = ClaimRequest.objects.filter(status='pending').count()
    emails_sent = SentEmail.objects.count()

    # Revenue stats
    from ..models import BookingPayment
    completed_payments = BookingPayment.objects.filter(status='completed')
    agg = completed_payments.aggregate(
        total_commission=Sum('application_fee'),
        total_volume=Sum('amount'),
        payment_count=Count('id'),
    )
    total_commission = agg['total_commission'] or 0
    total_booking_volume = agg['total_volume'] or 0
    total_paid_bookings = agg['payment_count'] or 0

    # 30-day activity
    profile_views_30d = AnalyticsEvent.objects.filter(
        event_type='profile_view', created_at__date__gte=days_30
    ).count()
    bookings_30d = Booking.objects.filter(created_at__date__gte=days_30).count()
    new_providers_30d = BeautyProvider.objects.filter(created_at__date__gte=days_30).count()

    # Top providers by views
    top_providers = (
        AnalyticsEvent.objects.filter(event_type='profile_view')
        .values('provider__name', 'provider__slug')
        .annotate(c=Count('id'))
        .order_by('-c')[:10]
    )

    # Top cities
    top_cities = (
        BeautyProvider.objects.filter(is_active=True)
        .values('city')
        .annotate(c=Count('id'))
        .order_by('-c')[:10]
    )

    # Recent activity
    recent_bookings = Booking.objects.select_related('provider').order_by('-created_at')[:5]
    recent_reviews = ProviderReview.objects.select_related('provider').order_by('-created_at')[:5]
    recent_claims = ClaimRequest.objects.filter(status='pending').select_related('provider').order_by('-created_at')[:5]

    return render(request, 'clients/admin/dashboard.html', {
        'total_providers': total_providers,
        'total_claimed': total_claimed,
        'total_unclaimed': total_unclaimed,
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'total_reviews': total_reviews,
        'total_posts': total_posts,
        'total_results': total_results,
        'pending_claims': pending_claims,
        'emails_sent': emails_sent,
        'profile_views_30d': profile_views_30d,
        'bookings_30d': bookings_30d,
        'new_providers_30d': new_providers_30d,
        'top_providers': top_providers,
        'top_cities': top_cities,
        'recent_bookings': recent_bookings,
        'recent_reviews': recent_reviews,
        'recent_claims': recent_claims,
        'total_commission': total_commission,
        'total_booking_volume': total_booking_volume,
        'total_paid_bookings': total_paid_bookings,
    })


@staff_member_required
def admin_revenue_view(request):
    """Detailed revenue dashboard — commissions, provider breakdown, city breakdown."""
    from decimal import Decimal
    from django.db.models import Sum, Count
    from django.db.models.functions import TruncMonth
    from ..models import BookingPayment

    completed = BookingPayment.objects.filter(status='completed').select_related('booking__provider')

    agg = completed.aggregate(
        total_commission=Sum('application_fee'),
        total_volume=Sum('amount'),
        payment_count=Count('id'),
    )

    # Revenue by provider
    by_provider = (
        completed.values(
            'booking__provider__name',
            'booking__provider__slug',
            'booking__provider__city',
            'booking__provider__plan',
        )
        .annotate(
            total=Sum('amount'),
            commission=Sum('application_fee'),
            count=Count('id'),
        )
        .order_by('-commission')[:20]
    )

    # Revenue by city
    by_city = (
        completed.values('booking__provider__city')
        .annotate(
            total=Sum('amount'),
            commission=Sum('application_fee'),
            count=Count('id'),
        )
        .order_by('-commission')
    )

    # Monthly revenue
    monthly = (
        completed.annotate(month=TruncMonth('paid_at'))
        .values('month')
        .annotate(
            total=Sum('amount'),
            commission=Sum('application_fee'),
            count=Count('id'),
        )
        .order_by('-month')[:12]
    )

    return render(request, 'clients/admin/revenue.html', {
        'total_commission': agg['total_commission'] or Decimal('0'),
        'total_volume': agg['total_volume'] or Decimal('0'),
        'total_payments': agg['payment_count'] or 0,
        'by_provider': by_provider,
        'by_city': by_city,
        'monthly': monthly,
    })
