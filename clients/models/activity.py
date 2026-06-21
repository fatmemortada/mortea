from django.db import models
from django.contrib.auth.models import User
from .client import Firm, Client


class ActivityLog(models.Model):
    """
    Immutable audit trail recording every significant action in the platform.
    """
    ACTION_CHOICES = [
        ('create',  'Created'),
        ('update',  'Updated'),
        ('delete',  'Deleted'),
        ('download','Downloaded'),
        ('sign',    'Signed'),
        ('login',   'Logged In'),
        ('invite',  'Invited'),
        ('payment', 'Payment'),
        ('status',  'Status Change'),
        ('export',  'Exported'),
        ('other',   'Other'),
    ]

    firm       = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='activity_logs', null=True, blank=True)
    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_logs')
    action     = models.CharField(max_length=20, choices=ACTION_CHOICES, default='other')
    target_type = models.CharField(max_length=50, blank=True, help_text='e.g. Client, Invoice, ComplianceTask')
    target_id   = models.PositiveIntegerField(null=True, blank=True)
    target_name = models.CharField(max_length=255, blank=True, help_text='Human-readable name of the target')
    description = models.TextField(blank=True)
    metadata    = models.JSONField(default=dict, blank=True, help_text='Arbitrary extra data (changes, file names, etc.)')
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['firm', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['target_type', 'target_id']),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else 'system'
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {user_str} {self.action} {self.target_type}"


def log_activity(user, action, target_type='', target_id=None, target_name='', description='', metadata=None, firm=None):
    """
    Convenience helper to record an activity log entry.
    """
    if metadata is None:
        metadata = {}

    if firm is None and user and user.is_authenticated:
        try:
            firm = user.userprofile.firm
        except Exception:
            pass

    return ActivityLog.objects.create(
        firm=firm,
        user=user if (user and user.is_authenticated) else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        description=description,
        metadata=metadata or {},
        ip_address=None,
    )
