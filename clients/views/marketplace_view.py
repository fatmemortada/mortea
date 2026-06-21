"""Corporate Services Marketplace views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models.marketplace import ServiceProvider, ServiceInquiry, SERVICE_CATEGORIES, JURISDICTIONS
from ..models.collaboration import SharedMatter, CollaborationTask, Approval


@login_required
def marketplace(request):
    """Browse service providers."""
    category_filter = request.GET.get('category', '')
    jurisdiction_filter = request.GET.get('jurisdiction', '')

    providers = ServiceProvider.objects.filter(is_active=True)
    if category_filter:
        providers = providers.filter(category=category_filter)
    if jurisdiction_filter:
        providers = providers.filter(jurisdictions__contains=[jurisdiction_filter])

    my_listings = ServiceProvider.objects.filter(firm=request.user.userprofile.firm) if hasattr(request.user, 'userprofile') else []

    return render(request, 'clients/marketplace.html', {
        'providers': providers,
        'categories': SERVICE_CATEGORIES,
        'jurisdictions': JURISDICTIONS,
        'category_filter': category_filter,
        'jurisdiction_filter': jurisdiction_filter,
        'my_listings': my_listings,
    })


@login_required
def marketplace_add(request):
    """Add a service provider listing."""
    if request.method == 'POST':
        try:
            firm = request.user.userprofile.firm
        except Exception:
            return redirect('login')
        jurisdictions = request.POST.getlist('jurisdictions')
        ServiceProvider.objects.create(
            firm=firm, name=request.POST.get('name'), category=request.POST.get('category'),
            description=request.POST.get('description'), jurisdictions=jurisdictions,
            email=request.POST.get('email'), phone=request.POST.get('phone', ''),
            website=request.POST.get('website', ''), city=request.POST.get('city', ''),
            province=request.POST.get('province', ''), hourly_rate=request.POST.get('hourly_rate', ''),
        )
        messages.success(request, 'Listing added!')
        return redirect('marketplace')
    return render(request, 'clients/marketplace_add.html', {
        'categories': SERVICE_CATEGORIES, 'jurisdictions': JURISDICTIONS,
    })


@login_required
def marketplace_inquire(request, provider_id):
    """Send inquiry to a provider."""
    provider = get_object_or_404(ServiceProvider, id=provider_id, is_active=True)
    if request.method == 'POST':
        ServiceInquiry.objects.create(
            provider=provider, client_name=request.POST.get('name'),
            client_email=request.POST.get('email'),
            client_phone=request.POST.get('phone', ''),
            message=request.POST.get('message'),
        )
        messages.success(request, f'Inquiry sent to {provider.name}!')
        return redirect('marketplace')
    return render(request, 'clients/marketplace_inquire.html', {'provider': provider})


@login_required
def collaboration_hub(request):
    """View shared matters and collaboration workspace."""
    user = request.user
    matters = SharedMatter.objects.filter(collaborators=user) | SharedMatter.objects.filter(created_by=user)
    matters = matters.distinct().select_related('client', 'created_by').order_by('-created_at')

    return render(request, 'clients/collaboration_hub.html', {
        'matters': matters,
    })
