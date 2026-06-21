from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from .client import Client


class CorporateProfile(models.Model):
    JURISDICTION_CHOICES = [
        ('federal', 'Federal'),
        ('ontario', 'Ontario'),
        ('bc', 'British Columbia'),
        ('quebec', 'Quebec'),
        ('alberta', 'Alberta'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('dissolved', 'Dissolved'),
        ('in_progress', 'In Progress'),
        ('inactive', 'Inactive'),
    ]

    client = models.OneToOneField('Client', on_delete=models.CASCADE, related_name='corporate_profile')
    jurisdiction = models.CharField(max_length=20, choices=JURISDICTION_CHOICES, blank=True)
    incorporation_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    business_number = models.CharField(max_length=20, blank=True)
    hst_number = models.CharField(max_length=20, blank=True)
    fiscal_year_end = models.CharField(max_length=10, blank=True, help_text='e.g. December 31')
    registered_address = models.TextField(blank=True)
    annual_return_due = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['jurisdiction']),
        ]

    def __str__(self):
        return f"{self.client.name} — Corporate Profile"


class Director(models.Model):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='directors')
    full_name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    appointment_date = models.DateField(null=True, blank=True)
    resignation_date = models.DateField(null=True, blank=True)
    is_officer = models.BooleanField(default=False)
    officer_title = models.CharField(max_length=100, blank=True, help_text='e.g. President, Secretary')

    def __str__(self):
        return f"{self.full_name} — {self.client.name}"

    @property
    def is_active(self):
        return self.resignation_date is None


class Shareholder(models.Model):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='shareholders')
    full_name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    share_class = models.CharField(max_length=50, default='Common', blank=True)
    num_shares = models.PositiveIntegerField(default=0)
    acquisition_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.full_name} — {self.num_shares} shares ({self.client.name})"


class AnnualFiling(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('filed', 'Filed'),
        ('overdue', 'Overdue'),
    ]
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='annual_filings')
    year = models.PositiveIntegerField()
    due_date = models.DateField()
    filed_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-year']

    def __str__(self):
        return f"{self.client.name} — {self.year} Annual Filing"
