"""Corporate Services Marketplace — provider directory."""
from django.db import models
from .client import Firm


SERVICE_CATEGORIES = [
    ('incorporation', 'Incorporation Services'),
    ('paralegal', 'Paralegal Services'),
    ('lawyer', 'Corporate Lawyer'),
    ('minute_book', 'Minute Book Specialist'),
    ('registered_office', 'Registered Office Provider'),
    ('virtual_address', 'Virtual Address Provider'),
    ('compliance', 'Compliance Services'),
    ('tax', 'Corporate Tax Services'),
    ('ubo', 'UBO Filing Services'),
    ('other', 'Other'),
]

JURISDICTIONS = [
    ('federal', 'Federal'),
    ('ontario', 'Ontario'),
    ('bc', 'British Columbia'),
    ('quebec', 'Quebec'),
    ('alberta', 'Alberta'),
]


class ServiceProvider(models.Model):
    """A professional service provider listed in the marketplace."""
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='provider_listings')
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=30, choices=SERVICE_CATEGORIES)
    description = models.TextField()
    jurisdictions = models.JSONField(default=list, help_text='List of jurisdictions served')
    website = models.URLField(blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=50, blank=True)
    hourly_rate = models.CharField(max_length=50, blank=True, help_text='e.g. $150-300/hr or Flat fee')
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_featured', 'name']

    def __str__(self):
        return f"{self.name} — {self.get_category_display()}"


class ServiceInquiry(models.Model):
    """A client inquiry sent to a service provider."""
    provider = models.ForeignKey(ServiceProvider, on_delete=models.CASCADE, related_name='inquiries')
    client_name = models.CharField(max_length=255)
    client_email = models.EmailField()
    client_phone = models.CharField(max_length=30, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
