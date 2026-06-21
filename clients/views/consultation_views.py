"""AI Beauty Consultation — rule-based recommendation engine."""
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..models import BeautyProvider, BeforeAfterResult


# ── Beauty Goal → Service Mapping ──────────────────────────────────────

GOAL_MAP = {
    'fuller lips': {
        'service': 'Lip Fillers',
        'explanation': 'Lip fillers use hyaluronic acid to add volume, shape, and hydration to your lips. Results are immediate and last 6-18 months. A qualified injector will work with your natural lip shape to create balanced, beautiful results.',
        'procedure': 'lip_fillers',
        'icon': '💋',
    },
    'acne scars': {
        'service': 'Microneedling & Skin Treatments',
        'explanation': 'Microneedling and chemical peels are the gold standard for acne scar treatment. Microneedling creates micro-channels that trigger collagen production, while chemical peels resurface the top layer of skin. Most clients need 3-6 sessions for optimal results.',
        'procedure': 'microneedling',
        'icon': '✨',
    },
    'wrinkles': {
        'service': 'Botox & Dermal Fillers',
        'explanation': 'Botox relaxes the muscles that cause expression lines (forehead, crow\'s feet, frown lines), while dermal fillers restore lost volume in areas like cheeks and nasolabial folds. Botox results appear in 3-7 days and last 3-4 months. Fillers are instant and last 6-18 months.',
        'procedure': 'botox',
        'icon': '💉',
    },
    'hair thinning': {
        'service': 'PRP Hair Restoration & Head Spa',
        'explanation': 'PRP (Platelet-Rich Plasma) therapy uses growth factors from your own blood to stimulate hair follicles. Combined with regular head spa treatments for scalp health, many clients see visible improvement in 3-6 months.',
        'procedure': 'prp',
        'icon': '🧖',
    },
    'healthier skin': {
        'service': 'Hydrafacial & Skin Treatments',
        'explanation': 'Hydrafacial is a multi-step treatment that cleanses, exfoliates, extracts, and hydrates in one session — with zero downtime. For more targeted concerns, treatments like IPL photofacials and LED light therapy address specific issues like sun damage and redness.',
        'procedure': 'hydrafacial',
        'icon': '💧',
    },
    'laser hair': {
        'service': 'Laser Hair Removal',
        'explanation': 'Laser hair removal uses concentrated light to target hair follicles, preventing future growth. Most areas need 6-8 sessions spaced 4-6 weeks apart. Modern diode lasers work safely on all skin types.',
        'procedure': 'laser_hair',
        'icon': '⚡',
    },
    'brows': {
        'service': 'Microblading & Brow Services',
        'explanation': 'Microblading creates natural-looking hair strokes using semi-permanent pigment. Brow lamination restructures brow hairs for a fuller, lifted look. Results last 1-3 years for microblading and 6-8 weeks for lamination.',
        'procedure': 'brows',
        'icon': '👁',
    },
    'lashes': {
        'service': 'Eyelash Extensions',
        'explanation': 'Lash extensions add length, curl, and volume to your natural lashes. Classic sets create a natural look, while volume sets (2D-5D fans) create more drama. Fills are needed every 2-3 weeks to maintain the look.',
        'procedure': 'lashes',
        'icon': '👁',
    },
    'hair extensions': {
        'service': 'Hair Extensions',
        'explanation': 'Modern hair extensions — hand-tied, tape-in, or keratin bond — add instant length and volume. Premium Remy hair is ethically sourced and can be colored, styled, and treated like your natural hair.',
        'procedure': 'hair_extensions',
        'icon': '💇',
    },
    'nails': {
        'service': 'Nail Services',
        'explanation': 'Russian manicures provide the most precise, long-lasting results with a completely dry manicure technique. Gel extensions and nail art allow for endless creativity and personalization.',
        'procedure': None,
        'icon': '💅',
    },
}

DISCLAIMER = '\n\n---\n⚠️ *This is an educational recommendation, not medical advice. Always consult with a qualified professional for personalized assessment. Mortea helps you discover providers — the final treatment decision should be made with your chosen provider.*'


def _match_goal(query):
    """Match user query to beauty goals."""
    query_lower = query.lower()
    matches = []
    for goal, data in GOAL_MAP.items():
        # Check if any word in the goal appears in the query
        goal_words = set(goal.split())
        query_words = set(query_lower.split())
        overlap = goal_words & query_words
        if overlap:
            matches.append((len(overlap), goal, data))
        # Also check if the goal itself is a substring of the query
        elif goal in query_lower:
            matches.append((1, goal, data))
    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[2] for m in matches[:3]]


def _get_providers(procedure_type, city=None):
    """Find providers for a procedure."""
    providers = BeautyProvider.objects.filter(is_active=True)
    if city:
        providers = providers.filter(city__iexact=city)
    if procedure_type:
        providers = providers.filter(
            before_after_results__procedure_type=procedure_type,
            before_after_results__is_published=True,
        ).distinct()
    return providers.order_by('-rating', '-is_featured')[:3]


def _get_results(procedure_type, city=None):
    """Get before/after results for a procedure."""
    results = BeforeAfterResult.objects.filter(is_published=True)
    if procedure_type:
        results = results.filter(procedure_type=procedure_type)
    if city:
        results = results.filter(city__iexact=city)
    return results.select_related('provider').order_by('-created_at')[:3]


# ── API Endpoint ────────────────────────────────────────────────────────


@csrf_exempt
def consultation_api(request):
    """AJAX endpoint for AI consultation chat."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    query = request.POST.get('message', '').strip()
    city = request.POST.get('city', '').strip()

    if not query:
        return JsonResponse({'response': "Hi! Tell me about your beauty goals and I'll help you find the right services and providers. 😊"})

    matches = _match_goal(query)

    if not matches:
        return JsonResponse({
            'response': "I'm not sure I understood your beauty goal. Try describing what you're looking for — for example:\n\n• I want fuller lips\n• I have acne scars\n• I want to reduce wrinkles\n• I have hair thinning\n• I want healthier skin\n\nI'm here to help! 💫"
        })

    # Build response
    lines = []
    providers_added = []
    results_added = []

    for i, match in enumerate(matches):
        lines.append(f"### {match['icon']} {match['service']}")
        lines.append(match['explanation'])

        providers = _get_providers(match.get('procedure'), city)
        if providers.exists():
            lines.append(f"\n**Top-rated providers{' in ' + city if city else ''}:**")
            for p in providers:
                lines.append(f"• [{p.name}](providers/{p.slug}/) — ★ {p.rating} ({p.review_count} reviews)")
                if p.id not in [pr['id'] for pr in providers_added]:
                    providers_added.append({
                        'id': p.id, 'name': p.name, 'slug': p.slug,
                        'rating': float(p.rating), 'review_count': p.review_count,
                        'city': p.city,
                    })

        results = _get_results(match.get('procedure'), city)
        if results.exists():
            lines.append(f"\n**Before & After examples:**")
            for r in results[:2]:
                lines.append(f"• [{r.provider.name}](providers/{r.provider.slug}/) — {r.get_procedure_type_display()} ({r.date.strftime('%b %Y') if r.date else ''})")
                if r.id not in [res['id'] for res in results_added]:
                    results_added.append({
                        'id': r.id, 'provider_name': r.provider.name,
                        'provider_slug': r.provider.slug,
                        'procedure': r.get_procedure_type_display(),
                        'date': str(r.date) if r.date else None,
                    })

        if i < len(matches) - 1:
            lines.append('\n---\n')

    lines.append(f'\n**Ready to take the next step?** Book a consultation with one of the providers above to discuss your goals in person.')
    lines.append(DISCLAIMER)

    return JsonResponse({
        'response': '\n'.join(lines),
        'providers': providers_added[:5],
        'results': results_added[:5],
    })


def consultation_view(request):
    """AI beauty consultation page."""
    return render(request, 'clients/consultation.html', {})
