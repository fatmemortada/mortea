"""Models for business acquisition: CSV imports, onboarding, email templates."""
from django.db import models
from django.conf import settings
from .provider import BeautyProvider


class BusinessImport(models.Model):
    """Tracks a batch CSV import of businesses."""
    STATUS_CHOICES = [
        ('draft', 'Draft — Previewing'),
        ('imported', 'Imported'),
        ('rejected', 'Rejected'),
    ]
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='business_imports'
    )
    csv_file = models.FileField(upload_to='imports/')
    filename = models.CharField(max_length=200)
    total_rows = models.PositiveIntegerField(default=0)
    imported_count = models.PositiveIntegerField(default=0)
    error_rows = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Import {self.filename} — {self.get_status_display()} ({self.imported_count}/{self.total_rows})"


class EmailTemplate(models.Model):
    """Email template for automated communications."""
    TYPE_CHOICES = [
        ('welcome', 'Welcome to Mortea'),
        ('claim', 'Claim Your Business'),
        ('upgrade', 'Upgrade to Premium'),
        ('review_reminder', 'Review Reminder'),
        ('booking_confirmation', 'Booking Confirmation'),
        ('onboarding', 'Complete Your Profile'),
    ]
    template_type = models.CharField(max_length=30, choices=TYPE_CHOICES, unique=True)
    subject = models.CharField(max_length=200)
    body_html = models.TextField(help_text='HTML email body')
    body_text = models.TextField(blank=True, help_text='Plain text fallback')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['template_type']

    def __str__(self):
        return f"{self.get_template_type_display()} — {self.subject}"


class SentEmail(models.Model):
    """Log of sent emails."""
    provider = models.ForeignKey(
        BeautyProvider, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_emails'
    )
    template = models.ForeignKey(
        EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_emails'
    )
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"Email → {self.recipient_email} ({self.subject[:40]})"
