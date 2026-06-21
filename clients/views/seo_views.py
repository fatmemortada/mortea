"""SEO-optimized pages: service+city, service hubs, city hubs."""
from django.shortcuts import render, get_object_or_404
from django.db import models as django_models
from django.http import Http404, HttpResponse
from django.urls import reverse
from ..models import BeautyProvider, BeautyService, BeforeAfterResult, ProviderReview


# ── Service + City mappings ─────────────────────────────────────────────

SERVICE_SLUGS = {
    'botox': {'name': 'Botox', 'procedure': 'botox', 'icon': '💉', 'intro': 'Botox is one of the most popular non-surgical cosmetic treatments. It works by temporarily relaxing facial muscles to smooth fine lines and wrinkles — especially on the forehead, between the brows, and around the eyes.'},
    'lip-fillers': {'name': 'Lip Fillers', 'procedure': 'lip_fillers', 'icon': '💋', 'intro': 'Lip fillers use hyaluronic acid-based dermal fillers to add volume, shape, and hydration to the lips. Results are immediate and can last 6–18 months depending on the product used.'},
    'prp': {'name': 'PRP Therapy', 'procedure': 'prp', 'icon': '🩸', 'intro': 'Platelet-Rich Plasma (PRP) therapy uses your own blood plasma to stimulate collagen production and cell regeneration. Popular for facial rejuvenation (the "Vampire Facial") and hair restoration.'},
    'laser-hair-removal': {'name': 'Laser Hair Removal', 'procedure': 'laser_hair', 'icon': '⚡', 'intro': 'Laser hair removal uses concentrated light energy to target hair follicles, preventing future growth. After 6–8 sessions, most patients experience permanent hair reduction.'},
    'hair-extensions': {'name': 'Hair Extensions', 'procedure': 'hair_extensions', 'icon': '💇', 'intro': 'Hair extensions add instant length, volume, and color without the wait. Modern methods — hand-tied, tape-in, and keratin bond — create seamless, natural-looking results.'},
    'brows': {'name': 'Brows', 'procedure': 'brows', 'icon': '👁', 'intro': 'Professional brow services — including microblading, lamination, and sculpting — frame your face and enhance your natural features. Semi-permanent techniques can last 1–3 years.'},
    'lashes': {'name': 'Lashes', 'procedure': 'lashes', 'icon': '👁', 'intro': 'Eyelash extensions add length, curl, and volume to your natural lashes. From natural classic sets to dramatic volume fans — customized to your eye shape and lifestyle.'},
    'hydrafacial': {'name': 'Hydrafacial', 'procedure': 'hydrafacial', 'icon': '💧', 'intro': 'Hydrafacial is a multi-step facial treatment that cleanses, exfoliates, extracts, and hydrates the skin using patented vortex technology. Suitable for all skin types with zero downtime.'},
    'skin-treatments': {'name': 'Skin Treatments', 'procedure': 'skin', 'icon': '✨', 'intro': 'Professional skin treatments — including microneedling, chemical peels, and IPL photofacials — target acne scars, hyperpigmentation, fine lines, and uneven texture for radiant skin.'},
    'microneedling': {'name': 'Microneedling', 'procedure': 'microneedling', 'icon': '🪡', 'intro': 'Microneedling uses tiny sterile needles to create micro-injuries in the skin, triggering collagen production. Excellent for acne scars, fine lines, and overall skin rejuvenation.'},
    'chemical-peel': {'name': 'Chemical Peel', 'procedure': 'chemical_peel', 'icon': '🧪', 'intro': 'Chemical peels use alpha and beta hydroxy acids to exfoliate the outer layers of skin, revealing smoother, brighter skin underneath. Available in light, medium, and deep strengths.'},
    'head-spa': {'name': 'Head Spa', 'procedure': None, 'icon': '🧖', 'intro': 'Japanese-inspired head spa treatments combine deep cleansing, scalp massage, and hydration to promote healthy hair growth and deep relaxation.'},
    'hair-salon': {'name': 'Hair Salon', 'procedure': None, 'icon': '✂️', 'intro': 'Find top-rated hair salons offering precision cuts, vibrant color, balayage, and expert styling from experienced professionals.'},
    'nails': {'name': 'Nails', 'procedure': None, 'icon': '💅', 'intro': 'Discover the best nail studios for Russian manicures, gel extensions, intricate nail art, and luxurious spa pedicures.'},
    'makeup': {'name': 'Makeup', 'procedure': None, 'icon': '💄', 'intro': 'Professional makeup artists for bridal, events, and editorial work. From natural glam to full beat — find your perfect artist.'},
    'eyelash-extensions': {'name': 'Eyelash Extensions', 'procedure': 'lashes', 'icon': '👁', 'intro': 'Semi-permanent eyelash extensions customized to your eye shape. Classic, hybrid, and volume sets available.'},
}

CITY_SLUGS = ['montreal', 'laval', 'brossard', 'ottawa', 'toronto', 'quebec-city', 'gatineau', 'longueuil', 'sherbrooke']


def _find_providers(service_info, city):
    """Find providers matching a service and city."""
    providers = BeautyProvider.objects.filter(is_active=True)
    if city:
        providers = providers.filter(city__iexact=city)
    if service_info['procedure']:
        providers = providers.filter(
            before_after_results__procedure_type=service_info['procedure'],
            before_after_results__is_published=True,
        ).distinct()
    if not service_info['procedure']:
        providers = providers.filter(
            services__name__icontains=service_info['name']
        ).distinct()
    return providers.select_related().prefetch_related('services', 'reviews').order_by('-is_featured', '-rating', 'name')


def _get_results(service_info, city):
    """Get before/after results for a service and city."""
    results = BeforeAfterResult.objects.filter(is_published=True).select_related('provider')
    if service_info['procedure']:
        results = results.filter(procedure_type=service_info['procedure'])
    if city:
        results = results.filter(city__iexact=city)
    return results.order_by('-created_at')[:6]


# ── Views ────────────────────────────────────────────────────────────────


def service_city_view(request, service, city):
    """SEO page: /services/botox/montreal/"""
    city_display = city.replace('-', ' ').title()
    service_info = SERVICE_SLUGS.get(service)
    if not service_info:
        raise Http404('Service not found')

    providers = _find_providers(service_info, city_display)
    results = _get_results(service_info, city_display)
    reviews = ProviderReview.objects.filter(
        provider__in=providers
    ).select_related('provider').order_by('-created_at')[:5]

    title = f"Best {service_info['name']} in {city_display}"
    meta_desc = f"Discover top-rated {service_info['name'].lower()} providers in {city_display}. Compare reviews, prices, before-and-after photos, and book consultations through Mortea."

    related_services = [s for s in SERVICE_SLUGS.keys() if s != service][:8]
    related_cities = [c for c in CITY_SLUGS if c != service][:5]

    return render(request, 'clients/seo/service_city.html', {
        'service_info': service_info,
        'service_slug': service,
        'city': city_display,
        'city_slug': city,
        'title': title,
        'meta_desc': meta_desc,
        'providers': providers,
        'results': results,
        'reviews': reviews,
        'total_providers': providers.count(),
        'related_services': [(s, SERVICE_SLUGS[s]['name']) for s in related_services],
        'related_cities': [(c, c.replace('-', ' ').title()) for c in related_cities],
    })


def service_hub_view(request, service):
    """SEO page: /services/botox/ — service directory hub."""
    service_info = SERVICE_SLUGS.get(service)
    if not service_info:
        raise Http404('Service not found')

    providers = _find_providers(service_info, None)
    results = _get_results(service_info, None)
    cities_with_providers = (
        providers.values_list('city', flat=True)
        .distinct().order_by('city')
    )

    title = f"Best {service_info['name']} Providers in Canada"
    meta_desc = f"Find the best {service_info['name'].lower()} providers across Canada. Compare reviews, prices, before-and-after results, and book your consultation through Mortea."

    return render(request, 'clients/seo/service_hub.html', {
        'service_info': service_info,
        'service_slug': service,
        'title': title,
        'meta_desc': meta_desc,
        'providers': providers[:12],
        'results': results,
        'cities_with_providers': cities_with_providers,
        'total_providers': providers.count(),
        'all_services': SERVICE_SLUGS,
    })


def city_hub_view(request, city):
    """SEO page: /montreal/ — city directory hub."""
    city_display = city.replace('-', ' ').title()
    if city not in CITY_SLUGS:
        raise Http404('City not found')

    providers = BeautyProvider.objects.filter(
        is_active=True, city__iexact=city_display
    ).prefetch_related('services', 'reviews').order_by('-is_featured', '-rating', 'name')

    results = BeforeAfterResult.objects.filter(
        is_published=True, city__iexact=city_display
    ).select_related('provider').order_by('-created_at')

    top_services = []
    for slug, info in SERVICE_SLUGS.items():
        if info['procedure']:
            count = results.filter(procedure_type=info['procedure']).count()
            if count > 0:
                top_services.append((slug, info, count))
    top_services.sort(key=lambda x: x[2], reverse=True)
    top_services = top_services[:8]

    # Slice after counting
    results = results[:6]

    title = f"Best Beauty Providers in {city_display}"
    meta_desc = f"Discover top-rated beauty salons, med spas, and clinics in {city_display}. Compare reviews, services, before-and-after photos, and book through Mortea."

    return render(request, 'clients/seo/city_hub.html', {
        'city': city_display,
        'city_slug': city,
        'title': title,
        'meta_desc': meta_desc,
        'providers': providers,
        'results': results,
        'top_services': top_services,
        'total_providers': providers.count(),
        'all_cities': CITY_SLUGS,
        'all_services': SERVICE_SLUGS,
    })


# ── XML Sitemap ─────────────────────────────────────────────────────────


def sitemap_view(request):
    """Generate XML sitemap for all SEO pages."""
    base = 'https://mortea.com'
    urls = []

    # Homepage
    urls.append({'loc': f'{base}/', 'priority': '1.0'})

    # Providers
    for p in BeautyProvider.objects.filter(is_active=True):
        urls.append({
            'loc': f'{base}/providers/{p.slug}/',
            'priority': '0.9',
            'lastmod': p.updated_at.strftime('%Y-%m-%d') if p.updated_at else None,
        })

    # Service hubs
    for slug in SERVICE_SLUGS:
        urls.append({'loc': f'{base}/services/{slug}/', 'priority': '0.8'})

    # Service + City pages
    for svc_slug in SERVICE_SLUGS:
        for city_slug in CITY_SLUGS:
            urls.append({'loc': f'{base}/services/{svc_slug}/{city_slug}/', 'priority': '0.7'})

    # City hubs
    for city_slug in CITY_SLUGS:
        urls.append({'loc': f'{base}/{city_slug}/', 'priority': '0.8'})

    # Results gallery
    urls.append({'loc': f'{base}/results/', 'priority': '0.7'})

    # Before & After results
    for r in BeforeAfterResult.objects.filter(is_published=True).select_related('provider'):
        urls.append({
            'loc': f'{base}/providers/{r.provider.slug}/',
            'priority': '0.6',
        })

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in urls:
        xml += '  <url>\n'
        xml += f'    <loc>{u["loc"]}</loc>\n'
        if u.get('lastmod'):
            xml += f'    <lastmod>{u["lastmod"]}</lastmod>\n'
        xml += f'    <priority>{u["priority"]}</priority>\n'
        xml += '  </url>\n'
    xml += '</urlset>'

    return HttpResponse(xml, content_type='application/xml')
