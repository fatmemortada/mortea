"""
Unified Notification Center.

Replaces fragmented alerts across compliance, billing, documents
with a single clean feed. In-app + email + push per user preferences.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client, Firm


class Notification(models.Model):
    """A single notification in the unified notification center."""
    CATEGORY_CHOICES = [
        ('compliance', 'Compliance'),
        ('billing', 'Billing'),
        ('document', 'Document'),
        ('client', 'Client Activity'),
        ('subscription', 'Subscription'),
        ('risk', 'Risk Alert'),
        ('collaboration', 'Collaboration'),
        ('system', 'System'),
        ('announcement', 'Announcement'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('critical', 'Critical'),
    ]
    CHANNEL_CHOICES = [
        ('in_app', 'In-App Only'),
        ('email', 'Email Only'),
        ('both', 'Both'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='notifications')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)

    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='system')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='both')

    # Link
    link_url = models.CharField(max_length=500, blank=True)
    link_text = models.CharField(max_length=100, default='View')

    # Status
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_actioned = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    # Related objects
    related_client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    related_invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['firm', 'is_read']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['category', 'is_read']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"

    def mark_read(self):
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save()

    def send_email(self):
        if self.user and self.user.email and not self.email_sent:
            from django.core.mail import send_mail
            send_mail(
                subject=f'[{self.get_category_display()}] {self.title}',
                message=f'{self.message}\n\n{"View: " + self.link_url if self.link_url else ""}',
                from_email='support@mortacc.com',
                recipient_list=[self.user.email],
                fail_silently=True,
            )
            self.email_sent = True
            self.email_sent_at = __import__('django').utils.timezone.now()
            self.save()


class NotificationPreference(models.Model):
    """Per-user notification preferences."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')

    # Global
    enable_in_app = models.BooleanField(default=True)
    enable_email = models.BooleanField(default=True)
    enable_push = models.BooleanField(default=True)

    # Digest
    daily_digest = models.BooleanField(default=False)
    weekly_digest = models.BooleanField(default=True)
    digest_time = models.TimeField(default='09:00')

    # Per-category toggles
    notify_compliance = models.BooleanField(default=True)
    notify_billing = models.BooleanField(default=True)
    notify_document = models.BooleanField(default=True)
    notify_client = models.BooleanField(default=True)
    notify_subscription = models.BooleanField(default=True)
    notify_risk = models.BooleanField(default=True)
    notify_collaboration = models.BooleanField(default=True)
    notify_announcement = models.BooleanField(default=True)

    # Priority thresholds
    email_priority_threshold = models.CharField(max_length=10, default='high', choices=[
        ('low', 'All'), ('normal', 'Normal+'), ('high', 'High+'), ('critical', 'Critical Only'),
    ])

    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(default='22:00')
    quiet_hours_end = models.TimeField(default='07:00')

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'

    def __str__(self):
        return f"Notification Preferences — {self.user.email}"

    def wants_email(self, category, priority):
        if not self.enable_email:
            return False
        cat_map = {
            'compliance': self.notify_compliance, 'billing': self.notify_billing,
            'document': self.notify_document, 'client': self.notify_client,
            'subscription': self.notify_subscription, 'risk': self.notify_risk,
            'collaboration': self.notify_collaboration, 'announcement': self.notify_announcement,
        }
        if not cat_map.get(category, True):
            return False
        priorities = {'low': 0, 'normal': 1, 'high': 2, 'critical': 3}
        threshold = priorities.get(self.email_priority_threshold, 2)
        return priorities.get(priority, 1) >= threshold


def create_notification(firm, title, message, category='system', priority='normal',
                        user=None, link_url='', related_client=None, channel='both'):
    """Helper to create a notification and optionally send email."""
    notif = Notification.objects.create(
        firm=firm, user=user, title=title, message=message,
        category=category, priority=priority, channel=channel,
        link_url=link_url, related_client=related_client,
    )
    if channel in ('email', 'both') and user:
        pref = NotificationPreference.objects.filter(user=user).first()
        if pref and pref.wants_email(category, priority):
            notif.send_email()
    return notif
