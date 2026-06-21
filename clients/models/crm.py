"""CRM models — client management, appointments, marketing, revenue."""
from django.db import models
from django.conf import settings
from .provider import BeautyProvider


class ClientProfile(models.Model):
    """Client managed by a provider in their CRM."""
    provider = models.ForeignKey(BeautyProvider, on_delete=models.CASCADE, related_name='crm_clients')
    full_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    birthday = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    tags = models.CharField(max_length=200, blank=True, help_text='e.g., VIP, Botox, Referral')
    total_visits = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_visit = models.DateField(null=True, blank=True)
    next_appointment = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_visit', '-created_at']
        unique_together = ['provider', 'email']

    def __str__(self):
        return f"{self.full_name} ({self.provider.name})"


class TreatmentNote(models.Model):
    """Treatment record for a client."""
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='treatments')
    provider = models.ForeignKey(BeautyProvider, on_delete=models.CASCADE, related_name='treatment_notes')
    service_name = models.CharField(max_length=200)
    date = models.DateField()
    notes = models.TextField(blank=True)
    products_used = models.CharField(max_length=300, blank=True)
    before_photo = models.ImageField(upload_to='crm/treatments/', blank=True)
    after_photo = models.ImageField(upload_to='crm/treatments/', blank=True)
    consent_signed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.service_name} — {self.client.full_name} ({self.date})"


class MarketingCampaign(models.Model):
    """Email/SMS campaign sent by a provider."""
    TYPE_CHOICES = [
        ('email', 'Email Campaign'),
        ('sms', 'SMS Reminder'),
        ('promotion', 'Promotion'),
        ('birthday', 'Birthday Offer'),
        ('rebooking', 'Rebooking Reminder'),
    ]
    provider = models.ForeignKey(BeautyProvider, on_delete=models.CASCADE, related_name='campaigns')
    campaign_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    recipient_count = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(auto_now_add=True)
    is_scheduled = models.BooleanField(default=False)
    scheduled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.get_campaign_type_display()}: {self.subject}"
