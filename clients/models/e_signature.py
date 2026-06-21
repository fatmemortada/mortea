"""
E-Signature System — OneSpan-like document signing workflow.

Envelope-based multi-signer signatures with:
- Sequential or parallel signing order
- Signing ceremony with document preview
- Full audit trail
- Certificate of completion
- Email notifications at every step
- Status tracking dashboard
- Reusable envelope templates
"""
import secrets
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .client import Firm, Client


class ESignatureEnvelope(models.Model):
    """A signature envelope containing a document to be signed by one or more signers."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('viewed', 'Viewed'),
        ('partially_signed', 'Partially Signed'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
        ('voided', 'Voided'),
    ]
    SIGNING_ORDER = [
        ('sequential', 'Sequential — signers sign one after another'),
        ('parallel', 'Parallel — all signers can sign at any time'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='signature_envelopes')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='signature_envelopes')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_envelopes')

    title = models.CharField(max_length=255, help_text='Name of this signature package')
    message = models.TextField(blank=True, help_text='Message to all signers')
    document_file = models.FileField(upload_to='e_signatures/', help_text='The document to be signed')
    document_name = models.CharField(max_length=255, help_text='Display name of the document')

    signing_order = models.CharField(max_length=20, choices=SIGNING_ORDER, default='sequential')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    require_signer_name = models.BooleanField(default=True, help_text='Require signers to type their full name')

    expires_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['firm', '-created_at']),
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_completed(self):
        return self.status == 'completed'

    @property
    def signers_count(self):
        return self.signers.count()

    @property
    def completed_signers_count(self):
        return self.signers.filter(status='signed').count()

    @property
    def current_signer(self):
        """Get the next signer in sequence, or None if all done."""
        if self.signing_order == 'parallel':
            return None  # All can sign simultaneously
        pending = self.signers.filter(status='pending').order_by('order').first()
        return pending

    def update_status(self):
        """Recalculate envelope status based on signer statuses."""
        signers = self.signers.all()
        if not signers:
            return

        statuses = set(s.status for s in signers)

        if any(s.status == 'declined' for s in signers):
            self.status = 'declined'
        elif all(s.status == 'signed' for s in signers):
            self.status = 'completed'
            self.completed_at = timezone.now()
        elif any(s.status == 'signed' for s in signers):
            self.status = 'partially_signed'
        elif any(s.status == 'viewed' for s in signers):
            self.status = 'viewed'
        elif any(s.status == 'sent' for s in signers):
            self.status = 'sent'

        self.save(update_fields=['status', 'completed_at'])


class ESignatureSigner(models.Model):
    """An individual signer on an envelope."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('viewed', 'Viewed'),
        ('signed', 'Signed'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]

    envelope = models.ForeignKey(ESignatureEnvelope, on_delete=models.CASCADE, related_name='signers')
    name = models.CharField(max_length=255)
    email = models.EmailField()
    order = models.PositiveIntegerField(default=0, help_text='Signing order (0 = first)')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Signing evidence
    signed_name = models.CharField(max_length=255, blank=True, help_text='Name typed by signer at signing')
    signed_ip = models.GenericIPAddressField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    user_agent = models.TextField(blank=True, help_text='Browser user agent at signing')

    # Declination
    decline_reason = models.TextField(blank=True)

    viewed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        unique_together = [('envelope', 'email')]

    def __str__(self):
        return f"{self.name} <{self.email}> — {self.get_status_display()}"

    def is_expired(self):
        if self.envelope.expires_at:
            return timezone.now() > self.envelope.expires_at
        return False


class ESignatureEvent(models.Model):
    """Audit trail event for an envelope."""
    EVENT_TYPES = [
        ('created', 'Envelope Created'),
        ('sent', 'Sent to Signers'),
        ('viewed', 'Document Viewed'),
        ('signed', 'Document Signed'),
        ('completed', 'All Signatures Completed'),
        ('declined', 'Signature Declined'),
        ('reminded', 'Reminder Sent'),
        ('expired', 'Envelope Expired'),
        ('voided', 'Envelope Voided'),
    ]

    envelope = models.ForeignKey(ESignatureEnvelope, on_delete=models.CASCADE, related_name='events')
    signer = models.ForeignKey(ESignatureSigner, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.get_event_type_display()} — {self.envelope.title}"
