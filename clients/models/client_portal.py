"""
Client Portal 2.0 — Real-Time Entity Dashboard.

Clients see their entities, compliance status, documents,
invoices. Self-serve document requests, invoice payments,
and entity change requests. Cuts email by 80%.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client


class ClientPortalRequest(models.Model):
    """A service request submitted by a client through their portal."""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
    ]
    REQUEST_TYPE_CHOICES = [
        ('document', 'Request a Document'),
        ('change', 'Change Request (director, address, etc.)'),
        ('incorporation', 'Incorporate a New Entity'),
        ('compliance', 'Compliance Question'),
        ('billing', 'Billing Question'),
        ('general', 'General Inquiry'),
        ('urgent', 'Urgent Request'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='portal_requests')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    request_type = models.CharField(max_length=30, choices=REQUEST_TYPE_CHOICES, default='general')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    subject = models.CharField(max_length=255)
    description = models.TextField()
    related_entity = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='related_requests')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    admin_response = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_portal_requests')
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Attachment
    attachment = models.FileField(upload_to='portal_requests/', null=True, blank=True)

    # Auto-generated invoice if this becomes billable
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['status', 'priority']),
        ]
        verbose_name = 'Client Portal Request'
        verbose_name_plural = 'Client Portal Requests'

    def __str__(self):
        return f"{self.subject} — {self.client.name} ({self.get_status_display()})"

    def resolve(self, user=None, response=''):
        from django.utils import timezone
        self.status = 'completed'
        self.resolved_by = user
        self.resolved_at = timezone.now()
        if response:
            self.admin_response = response
        self.save()


class ClientInvoicePayment(models.Model):
    """Client-side invoice payment through the portal."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='portal_payments')
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='portal_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, default='stripe', choices=[
        ('stripe', 'Credit Card'), ('bank', 'Bank Transfer'), ('other', 'Other'),
    ])
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed'),
    ])
    paid_at = models.DateTimeField(null=True, blank=True)
    receipt_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Client Invoice Payment'
        verbose_name_plural = 'Client Invoice Payments'

    def __str__(self):
        return f"${self.amount:.2f} payment for {self.invoice.invoice_number}"


class ClientNotification(models.Model):
    """Notification shown to a client in their portal."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='portal_notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, default='general', choices=[
        ('compliance', 'Compliance Update'),
        ('document_ready', 'Document Ready'),
        ('invoice', 'Invoice'),
        ('payment', 'Payment Confirmation'),
        ('request_update', 'Request Update'),
        ('announcement', 'Announcement'),
        ('reminder', 'Reminder'),
        ('general', 'General'),
    ])
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    link_url = models.CharField(max_length=500, blank=True)
    priority = models.CharField(max_length=10, default='normal', choices=[
        ('low', 'Low'), ('normal', 'Normal'), ('high', 'High'),
    ])
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'is_read']),
        ]
        verbose_name = 'Client Notification'
        verbose_name_plural = 'Client Notifications'

    def __str__(self):
        return f"{self.title} — {self.client.name}"
