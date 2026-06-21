"""Firm white-label branding."""
from django.db import models
from .client import Firm


class FirmBranding(models.Model):
    """Custom branding for a firm — logo, colors, domain."""
    firm = models.OneToOneField(Firm, on_delete=models.CASCADE, related_name='branding')
    logo = models.ImageField(upload_to='branding/logos/', null=True, blank=True, help_text='Firm logo (PNG, max 500KB)')
    primary_color = models.CharField(max_length=7, default='#2563eb', help_text='Hex color for buttons, links, accents')
    accent_color = models.CharField(max_length=7, default='#7c3aed', help_text='Secondary accent color')
    portal_title = models.CharField(max_length=100, blank=True, help_text='Custom portal title shown in browser tab')
    custom_domain = models.CharField(max_length=255, blank=True, help_text='e.g. portal.youraccountingfirm.com')
    custom_css = models.TextField(blank=True, help_text='Optional custom CSS overrides')
    hide_mortacc_branding = models.BooleanField(default=False, help_text='Hide "Powered by Mortacc" from portal')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Branding for {self.firm.name}"


class FirmDomain(models.Model):
    """Verified custom domains for firm portals."""
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='domains')
    domain = models.CharField(max_length=255, unique=True)
    verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
