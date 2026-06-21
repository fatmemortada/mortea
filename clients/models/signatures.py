"""E-signature workflow — request, sign, audit."""
from django.db import models
from django.contrib.auth.models import User
from .client import Client
from .onboarding import OnboardingDocument


class SignatureRequest(models.Model):
    """A signature request sent to a signer for a specific document."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('signed', 'Signed'),
        ('expired', 'Expired'),
        ('declined', 'Declined'),
    ]

    document = models.ForeignKey(
        OnboardingDocument, on_delete=models.CASCADE,
        related_name='signature_requests',
    )
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='signature_requests')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_signatures')

    signer_name = models.CharField(max_length=255, help_text='Full name of the person who needs to sign')
    signer_email = models.EmailField()
    message = models.TextField(blank=True, help_text='Optional message to include in the signing request')

    token = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    signed_name = models.CharField(max_length=255, blank=True, help_text='Name typed by signer at signing time')
    signed_ip = models.GenericIPAddressField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.signer_name} — {self.document.document_name} ({self.get_status_display()})"
