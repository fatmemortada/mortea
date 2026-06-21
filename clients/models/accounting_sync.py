"""
QBO/Xero Sync Integration.

Two-way sync with QuickBooks Online and Xero.
Chart of accounts linked to entity structure.
Financial data flows into Mortacc entity dashboards.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .client import Client, Firm


class AccountingConnection(models.Model):
    """A connection to an external accounting system (QBO or Xero)."""
    PLATFORM_CHOICES = [
        ('qbo', 'QuickBooks Online'),
        ('xero', 'Xero'),
    ]
    STATUS_CHOICES = [
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error'),
        ('expired', 'Token Expired'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='accounting_connections')
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disconnected')

    # OAuth tokens
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    realm_id = models.CharField(max_length=100, blank=True, help_text='QBO Company ID / Xero Tenant ID')

    # Sync settings
    auto_sync_enabled = models.BooleanField(default=False)
    sync_frequency_minutes = models.PositiveIntegerField(default=60, help_text='How often to sync')
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_invoices = models.BooleanField(default=True)
    sync_payments = models.BooleanField(default=True)
    sync_chart_of_accounts = models.BooleanField(default=True)
    sync_contacts = models.BooleanField(default=True)

    # Error tracking
    last_error = models.TextField(blank=True)
    consecutive_errors = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['firm', 'platform']
        ordering = ['platform']
        verbose_name = 'Accounting Connection'
        verbose_name_plural = 'Accounting Connections'

    def __str__(self):
        return f"{self.get_platform_display()} — {self.firm.name} ({self.get_status_display()})"


class EntityAccountMapping(models.Model):
    """Map a Mortacc client entity to an accounting system account/contact."""
    connection = models.ForeignKey(AccountingConnection, on_delete=models.CASCADE, related_name='entity_mappings')
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='accounting_mapping')

    # External IDs
    external_customer_id = models.CharField(max_length=100, blank=True, help_text='Customer ID in QBO/Xero')
    external_vendor_id = models.CharField(max_length=100, blank=True)
    external_account_id = models.CharField(max_length=100, blank=True, help_text='Default revenue account')

    # Sync status
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending'), ('synced', 'Synced'), ('error', 'Error'),
    ])
    sync_error = models.TextField(blank=True)

    # Invoice sync
    last_invoice_sync = models.DateTimeField(null=True, blank=True)
    invoices_synced = models.PositiveIntegerField(default=0)

    # Payment sync
    last_payment_sync = models.DateTimeField(null=True, blank=True)
    payments_synced = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['client__name']
        verbose_name = 'Entity Account Mapping'
        verbose_name_plural = 'Entity Account Mappings'

    def __str__(self):
        return f"{self.client.name} → {self.connection.get_platform_display()} ({self.sync_status})"


class SyncLog(models.Model):
    """Log of sync operations between Mortacc and accounting systems."""
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('partial', 'Partial'),
        ('failed', 'Failed'),
    ]

    connection = models.ForeignKey(AccountingConnection, on_delete=models.CASCADE, related_name='sync_logs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    direction = models.CharField(max_length=20, default='export', choices=[
        ('export', 'Mortacc → Accounting'),
        ('import', 'Accounting → Mortacc'),
        ('bidirectional', 'Bidirectional'),
    ])

    entity_type = models.CharField(max_length=30, default='invoices', choices=[
        ('invoices', 'Invoices'), ('payments', 'Payments'),
        ('contacts', 'Contacts'), ('accounts', 'Chart of Accounts'),
        ('all', 'Full Sync'),
    ])

    records_processed = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)

    error_details = models.JSONField(default=list, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Sync Log'
        verbose_name_plural = 'Sync Logs'

    def __str__(self):
        return f"{self.connection.get_platform_display()} Sync — {self.get_status_display()} ({self.records_processed} records)"
