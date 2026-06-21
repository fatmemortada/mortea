"""White-Label Client Portal views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.conf import settings

from ..models import Firm, WhiteLabelConfig, WhiteLabelPage, WhiteLabelDomain, log_activity
from ._helpers import _get_firm


@login_required
def whitelabel_settings(request):
    """Manage white-label configuration."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    config, created = WhiteLabelConfig.objects.get_or_create(firm=firm)
    pages = config.custom_pages.all()
    domains = config.domains.all()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_config':
            config.is_enabled = request.POST.get('is_enabled') == '1'
            config.company_name = request.POST.get('company_name', '').strip()
            config.company_short_name = request.POST.get('company_short_name', '').strip()
            config.company_tagline = request.POST.get('company_tagline', '').strip()
            config.primary_color = request.POST.get('primary_color', '#2563eb')
            config.secondary_color = request.POST.get('secondary_color', '#1d4ed8')
            config.accent_color = request.POST.get('accent_color', '#3b82f6')
            config.font_family = request.POST.get('font_family', 'Inter, system-ui, sans-serif')
            config.border_radius = request.POST.get('border_radius', '8px')
            config.custom_css = request.POST.get('custom_css', '')
            config.hide_mortacc_branding = request.POST.get('hide_mortacc') == '1'
            config.hide_powered_by = request.POST.get('hide_powered_by') == '1'
            config.custom_powered_by_text = request.POST.get('powered_by_text', '').strip()

            # Portal
            config.portal_title = request.POST.get('portal_title', '').strip()
            config.portal_welcome_title = request.POST.get('welcome_title', '').strip()
            config.portal_welcome_message = request.POST.get('welcome_message', '').strip()

            # Email
            config.email_from_name = request.POST.get('email_from_name', '').strip()
            config.email_signature = request.POST.get('email_signature', '').strip()

            # Login page
            config.login_page_title = request.POST.get('login_title', '').strip()
            config.login_page_subtitle = request.POST.get('login_subtitle', '').strip()

            # Logos
            if request.FILES.get('logo'):
                config.logo = request.FILES['logo']
            if request.FILES.get('favicon'):
                config.favicon = request.FILES['favicon']
            if request.FILES.get('login_background'):
                config.login_background = request.FILES['login_background']

            config.save()
            log_activity(None, f'White-label settings updated', request.user)
            messages.success(request, 'White-label configuration saved!')

        elif action == 'add_domain':
            domain = request.POST.get('domain', '').strip()
            if domain:
                import secrets
                code = f'mortacc-verify-{secrets.token_hex(16)}'
                WhiteLabelDomain.objects.create(
                    config=config, domain=domain,
                    verification_code=code,
                )
                messages.success(request, f'Domain {domain} added. Add this TXT record to verify: _mortacc-verify.{domain} → {code}')

        elif action == 'verify_domain':
            domain_id = request.POST.get('domain_id')
            d = get_object_or_404(WhiteLabelDomain, id=domain_id, config=config)
            d.is_verified = True
            d.verified_at = __import__('django').utils.timezone.now()
            d.save()
            messages.success(request, f'Domain {d.domain} verified!')

        elif action == 'add_page':
            title = request.POST.get('page_title', '').strip()
            slug = request.POST.get('page_slug', '').strip()
            content = request.POST.get('page_content', '').strip()
            if title and slug:
                WhiteLabelPage.objects.create(
                    config=config, title=title, slug=slug, content=content,
                )
                messages.success(request, f'Page "{title}" added.')

        elif action == 'toggle_page':
            page_id = request.POST.get('page_id')
            page = get_object_or_404(WhiteLabelPage, id=page_id, config=config)
            page.is_published = not page.is_published
            page.save()

        return redirect('whitelabel_settings')

    return render(request, 'clients/whitelabel_settings.html', {
        'firm': firm, 'config': config, 'pages': pages, 'domains': domains,
    })


def whitelabel_portal(request, slug=None):
    """Public white-label portal page."""
    # Determine which firm based on domain
    host = request.get_host()
    config = None

    # Check custom domains
    domain = WhiteLabelDomain.objects.filter(domain=host, is_verified=True).first()
    if domain:
        config = domain.config
    else:
        # Fallback: check firm from subdomain or path
        firm_code = request.GET.get('firm') or host.split('.')[0].upper()
        firm = Firm.objects.filter(code=firm_code).first()
        if firm:
            config = WhiteLabelConfig.objects.filter(firm=firm, is_enabled=True).first()

    if not config or not config.is_enabled:
        return HttpResponse('Portal not configured', status=404)

    if slug:
        page = get_object_or_404(WhiteLabelPage, config=config, slug=slug, is_published=True)
        return render(request, 'clients/whitelabel_page.html', {
            'config': config, 'page': page, 'firm': config.firm,
        })

    return render(request, 'clients/whitelabel_portal.html', {
        'config': config, 'firm': config.firm,
    })


def whitelabel_css(request, firm_code=None):
    """Serve dynamic CSS for white-label branding."""
    host = request.get_host()
    config = None

    domain = WhiteLabelDomain.objects.filter(domain=host, is_verified=True).first()
    if domain:
        config = domain.config
    elif firm_code:
        firm = Firm.objects.filter(code=firm_code.upper()).first()
        if firm:
            config = WhiteLabelConfig.objects.filter(firm=firm, is_enabled=True).first()

    if not config or not config.is_enabled:
        return HttpResponse('/* No white-label config */', content_type='text/css')

    css = f'''
    :root {{
        --brand: {config.primary_color};
        --brand-hover: {config.secondary_color};
        --brand-muted: {config.accent_color}40;
        --brand-soft: {config.accent_color}15;
        --green: {config.success_color};
        --amber: {config.warning_color};
        --red: {config.danger_color};
        --bg: {config.background_color};
        --ink: {config.text_color};
        --font: {config.font_family};
        --radius: {config.border_radius};
        --radius-lg: calc({config.border_radius} * 1.5);
    }}
    .mortacc-brand {{ display: {'none' if config.hide_mortacc_branding else 'block'}; }}
    .powered-by {{ display: {'none' if config.hide_powered_by else 'block'}; }}
    .whitelabel-company-name::after {{ content: "{config.company_name}"; }}
    {config.custom_css}
    '''
    return HttpResponse(css, content_type='text/css')
