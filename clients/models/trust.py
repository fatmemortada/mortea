"""Trust & Safety models — reports, moderation, verification."""
from django.db import models
from django.conf import settings
from .provider import BeautyProvider, ProviderReview, ProviderPhoto


class ContentReport(models.Model):
    """User report on any content type."""
    REPORT_TYPE = [
        ('provider', 'Provider'),
        ('review', 'Review'),
        ('photo', 'Photo'),
        ('message', 'Message'),
        ('fake_review', 'Fake Review'),
        ('spam', 'Spam'),
        ('impersonation', 'Impersonation'),
    ]
    STATUS = [('pending', 'Pending Review'), ('resolved', 'Resolved'), ('dismissed', 'Dismissed')]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPE)
    reported_by_name = models.CharField(max_length=100, blank=True)
    reported_by_email = models.EmailField(blank=True)
    reason = models.TextField()
    provider = models.ForeignKey(BeautyProvider, on_delete=models.CASCADE, null=True, blank=True, related_name='reports_against')
    review = models.ForeignKey(ProviderReview, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    photo = models.ForeignKey(ProviderPhoto, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    status = models.CharField(max_length=20, choices=STATUS, default='pending', db_index=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Report: {self.get_report_type_display()} — {self.get_status_display()}"


class VerificationRecord(models.Model):
    """Verification attempt for a provider."""
    TYPE = [
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('business', 'Business License'),
        ('social', 'Social Media'),
        ('identity', 'Identity'),
    ]
    STATUS = [('pending', 'Pending'), ('verified', 'Verified'), ('failed', 'Failed')]

    provider = models.ForeignKey(BeautyProvider, on_delete=models.CASCADE, related_name='verification_records')
    verification_type = models.CharField(max_length=20, choices=TYPE)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    evidence = models.TextField(blank=True, help_text='Verification details or document reference')
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['provider', 'verification_type']

    def __str__(self):
        return f"{self.get_verification_type_display()} — {self.provider.name} ({self.get_status_display()})"


class ModerationAction(models.Model):
    """Log of moderation actions for audit trail."""
    ACTION_TYPES = [
        ('approve_provider', 'Approved Provider'),
        ('reject_provider', 'Rejected Provider'),
        ('remove_review', 'Removed Review'),
        ('remove_photo', 'Removed Photo'),
        ('resolve_report', 'Resolved Report'),
        ('dismiss_report', 'Dismissed Report'),
        ('verify_provider', 'Verified Provider'),
        ('suspend_provider', 'Suspended Provider'),
    ]
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    provider = models.ForeignKey(BeautyProvider, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderation_actions')
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_type_display()} — {self.created_at.strftime('%b %d %H:%M')}"


class TrustedReviewer(models.Model):
    """User marked as a trusted reviewer."""
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    reviews_count = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Trusted: {self.name} ({self.email})"
