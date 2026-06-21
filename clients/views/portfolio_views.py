"""Portfolio: discovery feed, posts, likes, saves, follows."""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db import models as django_models
from django.views.decorators.csrf import csrf_exempt
from ..models import BeautyProvider, PortfolioPost, PortfolioLike, PortfolioSave, ProviderFollow


def _get_session_key(request):
    """Get or create a session key for anonymous users."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


# ── Discovery Feed ──────────────────────────────────────────────────────


def discovery_feed_view(request):
    """Instagram-style discovery feed of portfolio posts across Canada."""
    procedure = request.GET.get('procedure', '').strip()
    city = request.GET.get('city', '').strip()
    provider_slug = request.GET.get('provider', '').strip()
    sort = request.GET.get('sort', 'recent').strip()

    posts = PortfolioPost.objects.filter(is_published=True).select_related('provider')

    if procedure:
        posts = posts.filter(procedure_type=procedure)
    if city:
        posts = posts.filter(provider__city__iexact=city)
    if provider_slug:
        posts = posts.filter(provider__slug=provider_slug)
    if sort == 'likes':
        posts = posts.order_by('-likes_count', '-created_at')
    else:
        posts = posts.order_by('-created_at')

    procedures = PortfolioPost.PROCEDURE_CHOICES
    cities = (
        BeautyProvider.objects.filter(portfolio_posts__is_published=True)
        .values_list('city', flat=True).distinct().order_by('city')
    )

    return render(request, 'clients/portfolio/feed.html', {
        'posts': posts,
        'procedure': procedure,
        'city': city,
        'provider_slug': provider_slug,
        'sort': sort,
        'total_posts': posts.count(),
        'procedures': procedures,
        'cities': cities,
    })


# ── Like / Save / Follow API ────────────────────────────────────────────


@csrf_exempt
def toggle_like(request, post_id):
    """AJAX toggle like on a portfolio post."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    post = get_object_or_404(PortfolioPost, id=post_id, is_published=True)
    session_key = _get_session_key(request)

    like, created = PortfolioLike.objects.get_or_create(
        post=post,
        session_key=session_key,
        defaults={'user': request.user if request.user.is_authenticated else None},
    )

    if not created:
        like.delete()
        post.likes_count = max(0, post.likes_count - 1)
        post.save()
        return JsonResponse({'liked': False, 'count': post.likes_count})

    post.likes_count += 1
    post.save()
    return JsonResponse({'liked': True, 'count': post.likes_count})


@csrf_exempt
def toggle_save(request, post_id):
    """AJAX toggle save/bookmark on a portfolio post."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    post = get_object_or_404(PortfolioPost, id=post_id, is_published=True)
    session_key = _get_session_key(request)

    saved, created = PortfolioSave.objects.get_or_create(
        post=post,
        session_key=session_key,
        defaults={'user': request.user if request.user.is_authenticated else None},
    )

    if not created:
        saved.delete()
        return JsonResponse({'saved': False})

    return JsonResponse({'saved': True})


@csrf_exempt
def toggle_follow(request, provider_slug):
    """AJAX toggle follow on a provider."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    provider = get_object_or_404(BeautyProvider, slug=provider_slug, is_active=True)
    session_key = _get_session_key(request)

    follow, created = ProviderFollow.objects.get_or_create(
        provider=provider,
        session_key=session_key,
        defaults={'user': request.user if request.user.is_authenticated else None},
    )

    if not created:
        follow.delete()
        return JsonResponse({'following': False, 'count': provider.followers.count()})

    return JsonResponse({'following': True, 'count': provider.followers.count()})
