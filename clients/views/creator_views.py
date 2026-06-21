"""Creator/Influencer program views."""
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from ..models import CreatorProfile, CreatorPost, CreatorCollection, CreatorFavorite, AffiliateLink, ReferralEarning, BeautyProvider


def creator_profile_view(request, slug):
    """Public creator profile page."""
    creator = get_object_or_404(
        CreatorProfile.objects.prefetch_related('posts', 'collections', 'favorites__provider'),
        slug=slug
    )
    posts = creator.posts.filter(is_published=True).order_by('-created_at')[:6]
    collections = creator.collections.filter(is_published=True).order_by('-created_at')[:4]
    favorites = creator.favorites.select_related('provider').order_by('-created_at')[:8]

    return render(request, 'clients/creator/profile.html', {
        'creator': creator,
        'posts': posts,
        'collections': collections,
        'favorites': favorites,
    })


def creator_dashboard_view(request, slug):
    """Creator dashboard with stats, posts, earnings."""
    creator = get_object_or_404(CreatorProfile, slug=slug)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'post':
            CreatorPost.objects.create(
                creator=creator,
                post_type=request.POST.get('post_type', 'experience'),
                title=request.POST.get('title'),
                body=request.POST.get('body'),
            )
            messages.success(request, 'Post created!')
        elif action == 'collection':
            col = CreatorCollection.objects.create(
                creator=creator,
                title=request.POST.get('title'),
                description=request.POST.get('description', ''),
            )
            provider_ids = request.POST.getlist('providers')
            col.providers.set(provider_ids)
            messages.success(request, 'Collection created!')
        return redirect('creator_dashboard', slug=creator.slug)

    posts = creator.posts.order_by('-created_at')
    collections = creator.collections.order_by('-created_at')
    affiliate_links = creator.affiliate_links.select_related('provider')
    earnings = creator.earnings.select_related('provider').order_by('-created_at')[:10]
    providers = BeautyProvider.objects.filter(is_active=True).order_by('name')

    # 30-day stats
    days_30 = timezone.now() - datetime.timedelta(days=30)
    views_30d = sum(p.views_count for p in posts.filter(created_at__gte=days_30))
    clicks_30d = sum(l.clicks for l in affiliate_links)

    return render(request, 'clients/creator/dashboard.html', {
        'creator': creator,
        'posts': posts,
        'collections': collections,
        'affiliate_links': affiliate_links,
        'earnings': earnings,
        'providers': providers,
        'views_30d': views_30d,
        'clicks_30d': clicks_30d,
    })


def affiliate_click_view(request, code):
    """Track affiliate link click and redirect to provider."""
    link = get_object_or_404(AffiliateLink, unique_code=code)
    link.clicks += 1
    link.save(update_fields=['clicks'])
    link.creator.total_clicks += 1
    link.creator.save(update_fields=['total_clicks'])
    return redirect('provider_profile', slug=link.provider.slug)


def creators_discovery_view(request):
    """Browse all creators."""
    creators = CreatorProfile.objects.filter(is_featured=True).prefetch_related('posts')[:12]
    return render(request, 'clients/creator/discovery.html', {
        'creators': creators,
    })
