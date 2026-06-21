"""
White-Label Client Portal.

Full white-label configuration for Corporate Service Providers.
Custom domain, logo, colors, email templates, portal title.
CSPs sell it as their own platform. Opens the $500M CSP market.
"""
from django.db import models
from .client import Firm


class WhiteLabelConfig(models.Model):
    """Complete white-label configuration for a firm."""
    firm = models.OneToOneField(Firm, on_delete=models.CASCADE, related_name='whitelabel_config')
    is_enabled = models.BooleanField(default=False)

    # Branding
    company_name = models.CharField(max_length=255, blank=True, help_text='Displayed as portal provider name')
    company_short_name = models.CharField(max_length=50, blank=True)
    company_tagline = models.CharField(max_length=200, blank=True)

    # Visual
    logo = models.FileField(upload_to='whitelabel/logos/', null=True, blank=True)
    favicon = models.FileField(upload_to='whitelabel/favicons/', null=True, blank=True)
    login_background = models.FileField(upload_to='whitelabel/backgrounds/', null=True, blank=True)

    primary_color = models.CharField(max_length=7, default='#2563eb', help_text='Primary brand color hex')
    secondary_color = models.CharField(max_length=7, default='#1d4ed8')
    accent_color = models.CharField(max_length=7, default='#3b82f6')
    success_color = models.CharField(max_length=7, default='#16a34a')
    warning_color = models.CharField(max_length=7, default='#d97706')
    danger_color = models.CharField(max_length=7, default='#dc2626')
    background_color = models.CharField(max_length=7, default='#f8fafc')
    text_color = models.CharField(max_length=7, default='#0f172a')

    font_family = models.CharField(max_length=100, default='Inter, system-ui, sans-serif')
    border_radius = models.CharField(max_length=10, default='8px')

    # Custom CSS/JS
    custom_css = models.TextField(blank=True)
    custom_header_js = models.TextField(blank=True)
    custom_footer_js = models.TextField(blank=True)

    # Domain
    custom_domain = models.CharField(max_length=255, blank=True, help_text='e.g., portal.cspname.com')
    custom_domain_verified = models.BooleanField(default=False)
    custom_domain_verification_code = models.CharField(max_length=100, blank=True)
    use_custom_domain = models.BooleanField(default=False)

    # Email
    email_from_name = models.CharField(max_length=255, blank=True, help_text='e.g., "Smith Corporate Services"')
    email_from_address = models.EmailField(blank=True)
    email_signature = models.TextField(blank=True)
    email_footer_html = models.TextField(blank=True)

    # Portal
    portal_title = models.CharField(max_length=255, blank=True, help_text='Browser tab title')
    portal_welcome_title = models.CharField(max_length=255, blank=True)
    portal_welcome_message = models.TextField(blank=True)
    portal_terms_url = models.URLField(blank=True)
    portal_privacy_url = models.URLField(blank=True)

    # Hide Mortacc
    hide_mortacc_branding = models.BooleanField(default=True)
    hide_powered_by = models.BooleanField(default=True)
    custom_powered_by_text = models.CharField(max_length=100, blank=True)

    # Client-facing pages
    login_page_title = models.CharField(max_length=255, blank=True)
    login_page_subtitle = models.CharField(max_length=255, blank=True)

    # Documents
    document_header_html = models.TextField(blank=True, help_text='Added to top of generated documents')
    document_footer_html = models.TextField(blank=True)

    # Invoice branding
    invoice_logo = models.FileField(upload_to='whitelabel/invoice_logos/', null=True, blank=True)
    invoice_footer_text = models.TextField(blank=True)
    invoice_payment_instructions = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'White-Label Configuration'
        verbose_name_plural = 'White-Label Configurations'

    def __str__(self):
        return f"White-Label: {self.firm.name} ({'Enabled' if self.is_enabled else 'Disabled'})"

    @property
    def effective_primary_color(self):
        return self.primary_color if self.is_enabled else '#2563eb'

    @property
    def effective_logo_url(self):
        if self.is_enabled and self.logo:
            return self.logo.url
        return None

    @property
    def effective_company_name(self):
        return self.company_name if self.is_enabled else 'Mortacc'

    def get_css_variables(self):
        """Generate CSS custom properties for the white-label theme."""
        if not self.is_enabled:
            return ''
        return f'''
:root {{
    --brand: {self.primary_color};
    --brand-hover: {self.secondary_color};
    --brand-muted: {self.accent_color}40;
    --brand-soft: {self.accent_color}15;
    --green: {self.success_color};
    --amber: {self.warning_color};
    --red: {self.red if hasattr(self, 'red') else self.danger_color};
    --ink: {self.text_color};
    --surface: #ffffff;
    --surface-2: {self.background_color};
    --font-family: {self.font_family};
    --radius: {self.border_radius};
    --radius-lg: calc({self.border_radius} * 1.5);
}}
'''


class WhiteLabelPage(models.Model):
    """Custom page for the white-label portal (e.g., About, Services, FAQ)."""
    config = models.ForeignKey(WhiteLabelConfig, on_delete=models.CASCADE, related_name='custom_pages')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    content = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    show_in_nav = models.BooleanField(default=False)
    nav_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nav_order', 'title']
        unique_together = ['config', 'slug']
        verbose_name = 'White-Label Page'
        verbose_name_plural = 'White-Label Pages'

    def __str__(self):
        return f"{self.title} — {self.config.firm.name}"


class WhiteLabelDomain(models.Model):
    """Verified custom domain for white-label portal."""
    config = models.ForeignKey(WhiteLabelConfig, on_delete=models.CASCADE, related_name='domains')
    domain = models.CharField(max_length=255, unique=True)
    is_verified = models.BooleanField(default=False)
    verification_method = models.CharField(max_length=20, default='dns', choices=[
        ('dns', 'DNS TXT Record'), ('file', 'File Upload'), ('meta', 'Meta Tag'),
    ])
    verification_code = models.CharField(max_length=100)
    ssl_enabled = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'White-Label Domain'
        verbose_name_plural = 'White-Label Domains'

    def __str__(self):
        return f"{self.domain} ({'Verified' if self.is_verified else 'Pending'})"
