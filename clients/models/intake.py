"""
AI-Powered Intake Form Processor.

Accountant fills intake form → system auto-creates client, corporate
profile, directors, shareholders, incorporation project, compliance
tasks, and invoice. One-click incorporation from intake.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client, Firm


class IntakeForm(models.Model):
    """
    A single incorporation intake form. Captures all fields needed
    to create a complete corporate entity. On processing, auto-creates
    the Client, CorporateProfile, Directors, Shareholders,
    IncorporationProject, ComplianceTasks, and Invoice.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('needs_review', 'Needs Review'),
        ('failed', 'Failed'),
    ]
    JURISDICTION_CHOICES = [
        ('federal', 'Federal (CBCA)'),
        ('ontario', 'Ontario (OBCA)'),
        ('bc', 'British Columbia (BCBCA)'),
        ('alberta', 'Alberta (ABCA)'),
        ('quebec', 'Quebec (QBCA)'),
        ('nova_scotia', 'Nova Scotia'),
        ('manitoba', 'Manitoba'),
        ('saskatchewan', 'Saskatchewan'),
        ('new_brunswick', 'New Brunswick'),
    ]
    STRUCTURE_CHOICES = [
        ('named', 'Named Corporation'),
        ('numbered', 'Numbered Company'),
        ('professional', 'Professional Corporation'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='intake_forms')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # ── Client / Entity Info ──────────────────────────────────────────
    client_name = models.CharField(max_length=255, help_text='Proposed corporation name or leave blank for numbered')
    client_email = models.EmailField(help_text='Primary contact email')
    client_phone = models.CharField(max_length=30, blank=True)
    client_language = models.CharField(max_length=10, default='english', choices=[('english','English'),('french','French')])

    # ── Corporate Details ─────────────────────────────────────────────
    jurisdiction = models.CharField(max_length=30, choices=JURISDICTION_CHOICES, default='federal')
    structure_type = models.CharField(max_length=20, choices=STRUCTURE_CHOICES, default='named')
    is_numbered = models.BooleanField(default=False)

    # Proposed names
    proposed_name_1 = models.CharField(max_length=255, blank=True)
    proposed_name_2 = models.CharField(max_length=255, blank=True)
    proposed_name_3 = models.CharField(max_length=255, blank=True)

    # Address
    registered_address = models.TextField(blank=True, help_text='Registered office address')
    mailing_address = models.TextField(blank=True)

    # Business
    business_activity = models.TextField(blank=True, help_text='Description of business activity')
    industry_sector = models.CharField(max_length=100, blank=True)

    # Fiscal
    fiscal_year_end = models.CharField(max_length=20, default='December 31')
    authorize_unlimited_shares = models.BooleanField(default=True)
    authorized_share_classes = models.TextField(blank=True, help_text='e.g., "Common, Preferred"')

    # ── Directors ─────────────────────────────────────────────────────
    director_1_name = models.CharField(max_length=255, blank=True)
    director_1_address = models.TextField(blank=True)
    director_1_is_president = models.BooleanField(default=True)

    director_2_name = models.CharField(max_length=255, blank=True)
    director_2_address = models.TextField(blank=True)
    director_2_is_secretary = models.BooleanField(default=True)

    director_3_name = models.CharField(max_length=255, blank=True)
    director_3_address = models.TextField(blank=True)

    director_4_name = models.CharField(max_length=255, blank=True)
    director_4_address = models.TextField(blank=True)

    # ── Shareholders ──────────────────────────────────────────────────
    shareholder_1_name = models.CharField(max_length=255, blank=True)
    shareholder_1_address = models.TextField(blank=True)
    shareholder_1_shares = models.PositiveIntegerField(default=100)
    shareholder_1_class = models.CharField(max_length=50, default='Common')

    shareholder_2_name = models.CharField(max_length=255, blank=True)
    shareholder_2_address = models.TextField(blank=True)
    shareholder_2_shares = models.PositiveIntegerField(default=0)
    shareholder_2_class = models.CharField(max_length=50, default='Common')

    shareholder_3_name = models.CharField(max_length=255, blank=True)
    shareholder_3_address = models.TextField(blank=True)
    shareholder_3_shares = models.PositiveIntegerField(default=0)
    shareholder_3_class = models.CharField(max_length=50, default='Common')

    # ── Services & Billing ────────────────────────────────────────────
    incorporation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=1499.00)
    disbursements = models.DecimalField(max_digits=10, decimal_places=2, default=200.00, help_text='NUANS + filing fees')
    create_subscription = models.BooleanField(default=True, help_text='Auto-subscribe to annual maintenance')
    subscription_plan_tier = models.CharField(max_length=20, default='standard', choices=[
        ('basic','Basic ($29/mo)'),('standard','Standard ($79/mo)'),('premium','Premium ($199/mo)'),
    ])
    rush_service = models.BooleanField(default=False)
    rush_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    # ── Additional Services ───────────────────────────────────────────
    include_gst_registration = models.BooleanField(default=True)
    include_payroll_setup = models.BooleanField(default=False)
    include_bank_package = models.BooleanField(default=True)
    include_minute_book = models.BooleanField(default=True)
    include_share_certificates = models.BooleanField(default=True)
    include_engagement_letter = models.BooleanField(default=True)

    # ── Referral Source ───────────────────────────────────────────────
    referral_source = models.CharField(max_length=100, blank=True)
    referral_name = models.CharField(max_length=255, blank=True)

    # ── Notes ─────────────────────────────────────────────────────────
    special_instructions = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    # ── Processing Results ────────────────────────────────────────────
    created_client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_from_intake')
    created_incorporation_project = models.ForeignKey('IncorporationProject', on_delete=models.SET_NULL, null=True, blank=True)
    processing_log = models.JSONField(default=list, blank=True, help_text='Step-by-step processing log')
    processing_error = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    # ── Client portal submission ──────────────────────────────────────
    is_client_submitted = models.BooleanField(default=False)
    client_submitted_at = models.DateTimeField(null=True, blank=True)
    onboarding_token = models.CharField(max_length=64, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['firm', 'status']),
            models.Index(fields=['created_client']),
        ]
        verbose_name = 'Intake Form'
        verbose_name_plural = 'Intake Forms'

    def save(self, *args, **kwargs):
        if not self.onboarding_token:
            from django.utils.crypto import get_random_string
            self.onboarding_token = get_random_string(48)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Intake: {self.client_name or 'New Corp'} — {self.get_jurisdiction_display()} ({self.get_status_display()})"

    def get_directors(self):
        """Return list of (name, address, is_officer, title) tuples for non-empty directors."""
        directors = []
        for i in range(1, 5):
            name = getattr(self, f'director_{i}_name', '')
            address = getattr(self, f'director_{i}_address', '')
            if name.strip():
                title = ''
                if i == 1 and self.director_1_is_president:
                    title = 'President'
                elif i == 2 and self.director_2_is_secretary:
                    title = 'Secretary'
                directors.append((name.strip(), address.strip(), bool(title), title))
        return directors

    def get_shareholders(self):
        """Return list of (name, address, shares, share_class) tuples for non-empty shareholders."""
        shareholders = []
        for i in range(1, 4):
            name = getattr(self, f'shareholder_{i}_name', '')
            if name.strip():
                shareholders.append((
                    name.strip(),
                    getattr(self, f'shareholder_{i}_address', '').strip(),
                    getattr(self, f'shareholder_{i}_shares', 0),
                    getattr(self, f'shareholder_{i}_class', 'Common'),
                ))
        return shareholders

    @property
    def total_directors(self):
        return len(self.get_directors())

    @property
    def total_shareholders(self):
        return len(self.get_shareholders())

    @property
    def total_estimated(self):
        return float(self.incorporation_fee) + float(self.disbursements) + float(self.rush_fee)
