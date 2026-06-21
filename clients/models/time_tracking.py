"""
Time tracking and billing entries.

Enables firms to track billable time per client/entity,
auto-generate invoices from time entries, and reconstruct
billable hours from platform activity.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client


class TimeEntry(models.Model):
    """
    A single time entry for billable work on a client entity.

    Supports manual entry and auto-generation from platform activity.
    """
    BILLING_STATUS_CHOICES = [
        ('unbilled', 'Unbilled'),
        ('billed', 'Billed'),
        ('non_billable', 'Non-Billable'),
        ('written_off', 'Written Off'),
    ]

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='time_entries'
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='time_entries'
    )

    # Core fields
    description = models.TextField(help_text='Description of work performed')
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text='Calculated: hours × rate')

    # Classification
    category = models.CharField(max_length=50, default='general', choices=[
        ('incorporation', 'Incorporation'),
        ('annual_maintenance', 'Annual Maintenance'),
        ('compliance', 'Compliance Filing'),
        ('document_drafting', 'Document Drafting'),
        ('minute_book', 'Minute Book Work'),
        ('consultation', 'Consultation'),
        ('tax_filing', 'Tax Filing'),
        ('ubo', 'UBO/KYC'),
        ('registered_agent', 'Registered Agent'),
        ('other', 'Other'),
    ])

    # Billing
    billing_status = models.CharField(
        max_length=20, choices=BILLING_STATUS_CHOICES, default='unbilled'
    )
    invoice = models.ForeignKey(
        'Invoice', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='time_entries', help_text='Invoice this entry was billed on'
    )

    # Auto-generated flag
    auto_generated = models.BooleanField(default=False, help_text='Generated from platform activity')

    # Narrative for client-facing invoice
    client_narrative = models.TextField(blank=True, help_text='Client-ready description for invoice')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['client', 'billing_status']),
            models.Index(fields=['user', 'date']),
            models.Index(fields=['billing_status', 'date']),
            models.Index(fields=['invoice']),
        ]
        verbose_name = 'Time Entry'
        verbose_name_plural = 'Time Entries'

    def save(self, *args, **kwargs):
        if not self.amount and self.hours and self.hourly_rate:
            self.amount = float(self.hours) * float(self.hourly_rate)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.client.name} — {self.hours}h on {self.date} ({self.get_billing_status_display()})"

    def mark_billed(self, invoice):
        """Mark this time entry as billed on the given invoice."""
        self.billing_status = 'billed'
        self.invoice = invoice
        self.save()


class BillingRate(models.Model):
    """
    Default billing rates for a firm, by user role and service category.
    Used as defaults when creating time entries.
    """
    firm = models.ForeignKey('Firm', on_delete=models.CASCADE, related_name='billing_rates')
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True,
        related_name='custom_rates', help_text='User-specific rate override'
    )
    role = models.CharField(max_length=30, blank=True, choices=[
        ('partner', 'Partner'),
        ('associate', 'Associate'),
        ('paralegal', 'Paralegal'),
        ('clerk', 'Corporate Clerk'),
        ('accountant', 'Accountant'),
        ('admin', 'Admin'),
    ])
    category = models.CharField(max_length=50, blank=True, choices=TimeEntry._meta.get_field('category').choices)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2)
    is_default = models.BooleanField(default=False, help_text='Fallback rate when no other match')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['firm', 'role', 'category']
        indexes = [
            models.Index(fields=['firm', 'role']),
        ]
        verbose_name = 'Billing Rate'
        verbose_name_plural = 'Billing Rates'

    def __str__(self):
        scope = self.user.username if self.user else self.role or 'All'
        return f"{self.firm.name} — {scope} — ${self.hourly_rate}/hr"


class UnbilledActivity(models.Model):
    """
    Tracks platform activity that could be billable but hasn't been
    converted to a time entry yet. Powers the "AI billable time reconstruction" feature.
    """
    ACTIVITY_TYPE_CHOICES = [
        ('document_generated', 'Document Generated'),
        ('document_edited', 'Document Edited'),
        ('compliance_task_completed', 'Compliance Task Completed'),
        ('email_sent', 'Email Sent to Client'),
        ('filing_submitted', 'Filing Submitted'),
        ('call_logged', 'Call Logged'),
        ('meeting_held', 'Meeting Held'),
        ('review_completed', 'Review Completed'),
        ('template_filled', 'Template Filled'),
        ('ai_draft_performed', 'AI Draft Performed'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='unbilled_activities')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPE_CHOICES)
    description = models.TextField()
    occurred_at = models.DateTimeField()
    estimated_minutes = models.PositiveIntegerField(default=0)
    suggested_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    is_converted = models.BooleanField(default=False, help_text='Converted to TimeEntry')
    converted_entry = models.ForeignKey(
        TimeEntry, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='source_activity'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['client', 'is_converted']),
            models.Index(fields=['user', 'is_converted']),
        ]
        verbose_name = 'Unbilled Activity'
        verbose_name_plural = 'Unbilled Activities'

    def __str__(self):
        return f"{self.client.name} — {self.get_activity_type_display()} ({self.estimated_minutes}m)"

    def convert_to_time_entry(self):
        """Convert this activity into a billable time entry."""
        entry = TimeEntry.objects.create(
            client=self.client,
            user=self.user,
            description=self.description,
            date=self.occurred_at.date(),
            hours=self.estimated_minutes / 60.0,
            hourly_rate=self.suggested_rate,
            category=self._map_activity_to_category(),
            auto_generated=True,
        )
        self.is_converted = True
        self.converted_entry = entry
        self.save()
        return entry

    def _map_activity_to_category(self):
        mapping = {
            'document_generated': 'document_drafting',
            'document_edited': 'document_drafting',
            'compliance_task_completed': 'compliance',
            'email_sent': 'consultation',
            'filing_submitted': 'compliance',
            'call_logged': 'consultation',
            'meeting_held': 'consultation',
            'review_completed': 'document_drafting',
            'template_filled': 'document_drafting',
            'ai_draft_performed': 'document_drafting',
        }
        return mapping.get(self.activity_type, 'other')
