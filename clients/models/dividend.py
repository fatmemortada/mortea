"""
Dividend Resolution + T5 Generator.

Complete dividend workflow: declare dividend → generate corporate
resolution → director solvency declaration → T5 slips → track
dividend history per shareholder. The single most common transaction
that accountants still do manually.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client


class DividendDeclaration(models.Model):
    """A single dividend declaration for a corporate entity."""
    DIVIDEND_TYPE_CHOICES = [
        ('cash', 'Cash Dividend'),
        ('stock', 'Stock Dividend'),
        ('capital', 'Capital Dividend (CDA)'),
        ('eligible', 'Eligible Dividend'),
        ('non_eligible', 'Non-Eligible Dividend'),
        ('deemed', 'Deemed Dividend'),
        ('return_capital', 'Return of Capital'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('declared', 'Declared'),
        ('paid', 'Paid'),
        ('filed', 'Filed with CRA'),
        ('void', 'Void'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='dividend_declarations')
    declared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    dividend_type = models.CharField(max_length=20, choices=DIVIDEND_TYPE_CHOICES, default='non_eligible')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Financial details
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    declaration_date = models.DateField()
    payment_date = models.DateField(null=True, blank=True)
    fiscal_year = models.PositiveIntegerField(null=True, blank=True)
    tax_year = models.PositiveIntegerField(default=2026)

    # Resolution
    resolution_generated = models.BooleanField(default=False)
    resolution_document_id = models.PositiveIntegerField(null=True, blank=True)
    solvency_declaration_generated = models.BooleanField(default=False)

    # CRA filing
    t5_summary_filed = models.BooleanField(default=False)
    t5_filing_date = models.DateField(null=True, blank=True)
    cra_confirmation_number = models.CharField(max_length=50, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-declaration_date']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['tax_year', 'status']),
        ]
        verbose_name = 'Dividend Declaration'
        verbose_name_plural = 'Dividend Declarations'

    def __str__(self):
        return f"{self.client.name} — ${self.total_amount:.2f} {self.get_dividend_type_display()} ({self.declaration_date})"

    @property
    def total_t5_slips(self):
        return self.recipients.count()

    def mark_paid(self):
        from django.utils import timezone
        self.status = 'paid'
        self.payment_date = timezone.now().date()
        self.save()


class DividendRecipient(models.Model):
    """A single shareholder receiving a dividend distribution."""
    declaration = models.ForeignKey(DividendDeclaration, on_delete=models.CASCADE, related_name='recipients')
    shareholder_name = models.CharField(max_length=255)
    shareholder_address = models.TextField(blank=True)

    # Identification
    sin = models.CharField(max_length=15, blank=True, help_text='Social Insurance Number')
    business_number = models.CharField(max_length=15, blank=True, help_text='For corporate recipients')

    # Distribution
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2)
    tax_withheld = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    shares_owned = models.PositiveIntegerField(default=0)
    dividend_per_share = models.DecimalField(max_digits=10, decimal_places=6, default=0.0)

    # Tax info
    eligible_dividend_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.0, help_text='Eligible for enhanced dividend tax credit')
    non_eligible_dividend_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    capital_dividend_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.0, help_text='From CDA')
    foreign_tax_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)

    # T5 slip
    t5_generated = models.BooleanField(default=False)
    t5_slip_number = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['shareholder_name']
        verbose_name = 'Dividend Recipient'
        verbose_name_plural = 'Dividend Recipients'

    def save(self, *args, **kwargs):
        if not self.net_amount:
            self.net_amount = float(self.gross_amount) - float(self.tax_withheld)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.shareholder_name} — ${self.gross_amount:.2f} from {self.declaration.client.name}"


class DividendHistory(models.Model):
    """Historical record of dividends paid to a shareholder across entities."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='dividend_history')
    shareholder_name = models.CharField(max_length=255)
    fiscal_year = models.PositiveIntegerField()
    total_dividends = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    eligible_dividends = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    non_eligible_dividends = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    capital_dividends = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    t5_filed = models.BooleanField(default=False)
    t5_summary_total = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fiscal_year', 'shareholder_name']
        unique_together = ['client', 'shareholder_name', 'fiscal_year']
        indexes = [
            models.Index(fields=['client', 'fiscal_year']),
        ]
        verbose_name_plural = 'Dividend Histories'

    def __str__(self):
        return f"{self.shareholder_name} — FY{self.fiscal_year} — ${self.total_dividends:.2f}"
