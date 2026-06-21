"""
AI Compliance Risk Detection Engine.

Proactively scans entity records for anomalies and risks:
- Director resignations not filed with registry
- Share issuance exceeding authorized capital
- UBO register gaps
- Jurisdiction mismatches
- Missing annual filings
- Stale corporate records

Generates risk-scored reports with remediation proposals.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client


class RiskScan(models.Model):
    """
    A single AI-powered risk scan of an entity's records.
    Each scan produces multiple RiskFinding records.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scanning', 'Scanning'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='risk_scans')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Scan scope
    check_directors = models.BooleanField(default=True)
    check_shareholders = models.BooleanField(default=True)
    check_registrations = models.BooleanField(default=True)
    check_ubo = models.BooleanField(default=True)
    check_compliance = models.BooleanField(default=True)
    check_documents = models.BooleanField(default=True)

    # Results
    total_findings = models.PositiveIntegerField(default=0)
    critical_count = models.PositiveIntegerField(default=0)
    high_count = models.PositiveIntegerField(default=0)
    medium_count = models.PositiveIntegerField(default=0)
    low_count = models.PositiveIntegerField(default=0)
    overall_score = models.PositiveIntegerField(default=0, help_text='0-100, higher = better')

    error_message = models.TextField(blank=True)
    scan_duration_ms = models.PositiveIntegerField(default=0)
    raw_ai_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
        ]
        verbose_name = 'Risk Scan'
        verbose_name_plural = 'Risk Scans'

    def __str__(self):
        return f"Risk Scan — {self.client.name} (Score: {self.overall_score}, {self.total_findings} findings)"


class RiskFinding(models.Model):
    """
    A single risk or anomaly found during a scan.
    """
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    CATEGORY_CHOICES = [
        ('directors', 'Directors & Officers'),
        ('shareholders', 'Shareholders & Equity'),
        ('registrations', 'Registrations & Filings'),
        ('ubo', 'Beneficial Ownership'),
        ('compliance', 'Compliance Deadlines'),
        ('documents', 'Documents & Records'),
        ('jurisdiction', 'Jurisdiction & Multi-Provincial'),
        ('tax', 'Tax Compliance'),
        ('other', 'Other'),
    ]

    scan = models.ForeignKey(RiskScan, on_delete=models.CASCADE, related_name='findings')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='risk_findings')

    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    title = models.CharField(max_length=255)
    description = models.TextField()
    detail = models.JSONField(default=dict, blank=True, help_text='Structured detail about the finding')

    # Remediation
    remediation = models.TextField(blank=True, help_text='Suggested fix')
    estimated_hours = models.DecimalField(max_digits=5, decimal_places=1, default=0.0, help_text='Estimated time to fix')
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text='Estimated cost to remediate')
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_findings')
    resolution_notes = models.TextField(blank=True)

    # AI confidence
    ai_confidence = models.FloatField(default=0.0, help_text='0.0-1.0 AI confidence score')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-severity', '-ai_confidence']
        indexes = [
            models.Index(fields=['client', 'is_resolved']),
            models.Index(fields=['severity', 'is_resolved']),
        ]
        verbose_name = 'Risk Finding'
        verbose_name_plural = 'Risk Findings'

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.title} — {self.client.name}"

    def resolve(self, user=None, notes=''):
        self.is_resolved = True
        self.resolved_at = models.DateTimeField(auto_now_add=True) if True else None
        from django.utils import timezone
        self.resolved_at = timezone.now()
        if user:
            self.resolved_by = user
        if notes:
            self.resolution_notes = notes
        self.save()


class BulkRiskScan(models.Model):
    """
    Batch risk scan across multiple entities at once.
    For CSPs managing large portfolios.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scanning', 'Scanning'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    firm = models.ForeignKey('Firm', on_delete=models.CASCADE, related_name='bulk_scans')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    client_filter = models.JSONField(default=dict, blank=True, help_text='Filter criteria for clients to scan')

    total_clients = models.PositiveIntegerField(default=0)
    scanned_clients = models.PositiveIntegerField(default=0)
    total_findings = models.PositiveIntegerField(default=0)
    critical_count = models.PositiveIntegerField(default=0)
    high_count = models.PositiveIntegerField(default=0)

    average_score = models.PositiveIntegerField(default=0)
    summary_report = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Bulk Risk Scan'
        verbose_name_plural = 'Bulk Risk Scans'

    def __str__(self):
        return f"Bulk Risk Scan — {self.firm.name} ({self.scanned_clients}/{self.total_clients} clients)"
