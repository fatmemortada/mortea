"""Template context processor for firm branding."""
from .models.branding import FirmBranding


def firm_branding(request):
    """Add firm branding to template context if available."""
    if not request.user.is_authenticated:
        return {}

    try:
        firm = request.user.userprofile.firm
        if not firm:
            return {}
        branding = FirmBranding.objects.filter(firm=firm).first()
        if branding:
            return {
                'firm_branding': branding,
                'brand_primary': branding.primary_color,
                'brand_accent': branding.accent_color,
                'brand_logo_url': branding.logo.url if branding.logo else None,
                'brand_title': branding.portal_title or firm.name,
                'brand_css': branding.custom_css,
                'hide_mortacc': branding.hide_mortacc_branding,
            }
    except Exception:
        pass
    return {}


def demo_context(request):
    """Add is_demo flag to template context for demo users."""
    is_demo = False
    if request.user.is_authenticated and request.user.email.endswith('@mortacc.demo'):
        is_demo = True
    return {'is_demo': is_demo}
