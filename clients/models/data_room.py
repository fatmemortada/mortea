"""
Due Diligence Data Room.

One-click generates a structured virtual data room from entity records.
Permissioned external access with activity tracking, expiry dates.
$99/data room/month subscription add-on.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .client import Client, Firm


class DataRoom(models.Model):
    """A virtual data room for due diligence, M&A, or financing."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('archived', 'Archived'),
    ]
    ACCESS_LEVEL_CHOICES = [
        ('restricted', 'Restricted — Email invite only'),
        ('link', 'Link — Anyone with the link'),
        ('public', 'Public — No authentication'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='data_rooms')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='data_rooms')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    name = models.CharField(max_length=255, help_text='e.g., "ABC Corp — Series A Financing Q2 2026"')
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Access control
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='restricted')
    access_code = models.CharField(max_length=64, unique=True, blank=True, help_text='Unique access link code')
    require_nda = models.BooleanField(default=True, help_text='Require NDA acceptance before access')
    nda_text = models.TextField(blank=True, help_text='Custom NDA text')

    # Timing
    opens_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    auto_archive_days = models.PositiveIntegerField(default=90, help_text='Auto-archive after this many days')

    # Watermarking
    watermark_text = models.CharField(max_length=255, blank=True, help_text='e.g., "CONFIDENTIAL — Acme Corp Due Diligence"')
    watermark_email = models.BooleanField(default=True, help_text='Include viewer email in watermark')

    # Activity
    total_views = models.PositiveIntegerField(default=0)
    total_downloads = models.PositiveIntegerField(default=0)
    total_documents = models.PositiveIntegerField(default=0)

    # Billing
    is_paid = models.BooleanField(default=False)
    subscription_invoice = models.ForeignKey('SubscriptionInvoice', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['access_code']),
        ]
        verbose_name = 'Data Room'
        verbose_name_plural = 'Data Rooms'

    def save(self, *args, **kwargs):
        if not self.access_code:
            from django.utils.crypto import get_random_string
            self.access_code = get_random_string(48)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} — {self.client.name}"

    @property
    def is_active(self):
        if self.status != 'active':
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    @property
    def access_url(self):
        return f"/dataroom/{self.access_code}/"


class DataRoomDocument(models.Model):
    """A document included in a data room."""
    room = models.ForeignKey(DataRoom, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='data_rooms/')
    category = models.CharField(max_length=50, choices=[
        ('corporate', 'Corporate Records'),
        ('financial', 'Financial Statements'),
        ('tax', 'Tax Returns & Filings'),
        ('contracts', 'Contracts & Agreements'),
        ('ip', 'Intellectual Property'),
        ('hr', 'HR & Employment'),
        ('regulatory', 'Regulatory & Compliance'),
        ('other', 'Other'),
    ], default='corporate')
    sort_order = models.PositiveIntegerField(default=0)
    file_size = models.PositiveIntegerField(default=0)
    is_confidential = models.BooleanField(default=False)
    require_nda = models.BooleanField(default=False)

    # Stats
    view_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Data Room Document'
        verbose_name_plural = 'Data Room Documents'

    def __str__(self):
        return f"{self.name} — {self.room.name}"


class DataRoomAccess(models.Model):
    """Track who accessed the data room and when."""
    room = models.ForeignKey(DataRoom, on_delete=models.CASCADE, related_name='access_logs')
    viewer_name = models.CharField(max_length=255, blank=True)
    viewer_email = models.EmailField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # NDA
    nda_accepted = models.BooleanField(default=False)
    nda_accepted_at = models.DateTimeField(null=True, blank=True)
    nda_ip = models.GenericIPAddressField(null=True, blank=True)

    # Activity
    first_accessed = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(auto_now=True)
    total_views = models.PositiveIntegerField(default=0)
    total_downloads = models.PositiveIntegerField(default=0)
    documents_viewed = models.JSONField(default=list, blank=True)

    access_token = models.CharField(max_length=64, unique=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_accessed']
        indexes = [
            models.Index(fields=['room', 'viewer_email']),
        ]
        verbose_name_plural = 'Data Room Accesses'

    def save(self, *args, **kwargs):
        if not self.access_token:
            from django.utils.crypto import get_random_string
            self.access_token = get_random_string(48)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.viewer_email or self.viewer_name} — {self.room.name} ({self.total_views} views)"


class DataRoomInvite(models.Model):
    """Invitation to access a data room."""
    room = models.ForeignKey(DataRoom, on_delete=models.CASCADE, related_name='invites')
    email = models.EmailField()
    inviter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField(blank=True)
    access_token = models.CharField(max_length=64, unique=True, blank=True)

    # Status
    is_sent = models.BooleanField(default=False)
    is_accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Data Room Invite'
        verbose_name_plural = 'Data Room Invites'

    def save(self, *args, **kwargs):
        if not self.access_token:
            from django.utils.crypto import get_random_string
            self.access_token = get_random_string(48)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invite: {self.email} → {self.room.name}"
