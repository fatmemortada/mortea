"""
Bulk Minute Book Remediation Engine.

Scope multiple entities, batch-generate missing documents,
track per-entity progress, and invoice per entity as completed.
Designed for Corporate Service Providers managing large portfolios.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client, Firm


class RemediationProject(models.Model):
    """
    A bulk remediation project covering one or more entities.
    Used when a firm takes over entities with deficient minute books.
    """
    STATUS_CHOICES = [
        ('scoping', 'Scoping'),
        ('in_progress', 'In Progress'),
        ('review', 'In Review'),
        ('completed', 'Completed'),
        ('invoiced', 'Invoiced'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='remediation_projects')
    name = models.CharField(max_length=255, help_text='e.g., "Q1 2026 Catch-Up Batch"')
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scoping')

    # Billing
    fixed_fee_per_entity = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    total_estimated = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    total_invoiced = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)

    # Stats
    total_entities = models.PositiveIntegerField(default=0)
    completed_entities = models.PositiveIntegerField(default=0)
    total_documents_needed = models.PositiveIntegerField(default=0)
    documents_generated = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Remediation Project'
        verbose_name_plural = 'Remediation Projects'

    def __str__(self):
        return f"{self.name} — {self.firm.name} ({self.completed_entities}/{self.total_entities})"

    @property
    def progress_pct(self):
        if self.total_entities == 0:
            return 0
        return int((self.completed_entities / self.total_entities) * 100)


class RemediationEntity(models.Model):
    """
    A single entity within a remediation project.
    Tracks what's missing, what's been generated, and billing status.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('ready_for_review', 'Ready for Review'),
        ('completed', 'Completed'),
        ('invoiced', 'Invoiced'),
    ]

    project = models.ForeignKey(RemediationProject, on_delete=models.CASCADE, related_name='entities')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='remediation_entries')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Scope
    years_to_remediate = models.JSONField(default=list, blank=True, help_text='List of years needing catch-up')
    missing_documents = models.JSONField(default=list, blank=True, help_text='List of missing document types')
    generated_documents = models.JSONField(default=list, blank=True, help_text='List of generated document IDs')

    # Billing
    fixed_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    hours_spent = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    is_invoiced = models.BooleanField(default=False)
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True)

    # Assignment
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['status', 'client__name']
        indexes = [
            models.Index(fields=['project', 'status']),
        ]
        verbose_name = 'Remediation Entity'
        verbose_name_plural = 'Remediation Entities'

    def __str__(self):
        return f"{self.client.name} — {self.project.name} ({self.get_status_display()})"

    @property
    def missing_count(self):
        return len(self.missing_documents) if self.missing_documents else 0

    @property
    def generated_count(self):
        return len(self.generated_documents) if self.generated_documents else 0

    def mark_complete(self):
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
        # Update project counters
        project = self.project
        project.completed_entities = RemediationEntity.objects.filter(
            project=project, status__in=['completed', 'invoiced']
        ).count()
        project.documents_generated = sum(
            e.generated_count for e in RemediationEntity.objects.filter(project=project)
        )
        project.save()


class DocumentDeficiency(models.Model):
    """
    A specific document that's missing or deficient for an entity.
    Used during scoping to catalog what needs to be generated.
    """
    DOCUMENT_TYPES = [
        ('articles', 'Articles of Incorporation'),
        ('bylaw_no1', 'By-law No. 1'),
        ('org_resolution', 'Organizational Resolutions'),
        ('directors_register', 'Register of Directors'),
        ('shareholders_register', 'Register of Shareholders'),
        ('share_certificates', 'Share Certificates'),
        ('annual_resolution', 'Annual Resolutions'),
        ('annual_return', 'Annual Return Filing'),
        ('director_consent', 'Consent to Act as Director'),
        ('shareholder_agreement', 'Shareholder Agreement'),
        ('minute_book', 'Minute Book'),
        ('banking_resolution', 'Banking Resolution'),
        ('ubo_register', 'UBO Register'),
        ('tax_filings', 'Tax Filings (T2, T5)'),
        ('agm_minutes', 'AGM Minutes'),
        ('director_minutes', 'Director Meeting Minutes'),
        ('shareholder_minutes', 'Shareholder Meeting Minutes'),
        ('other', 'Other'),
    ]
    SEVERITY_CHOICES = [
        ('critical', 'Critical — Legal requirement missing'),
        ('high', 'High — Should exist'),
        ('medium', 'Medium — Best practice'),
        ('low', 'Low — Nice to have'),
    ]

    entity = models.ForeignKey(RemediationEntity, on_delete=models.CASCADE, related_name='deficiencies')
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    year = models.PositiveIntegerField(null=True, blank=True, help_text='Fiscal year this document relates to')
    description = models.CharField(max_length=255)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='high')
    is_generated = models.BooleanField(default=False)
    generated_document_id = models.PositiveIntegerField(null=True, blank=True)
    estimated_minutes = models.PositiveIntegerField(default=15)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-severity', 'year']
        verbose_name = 'Document Deficiency'
        verbose_name_plural = 'Document Deficiencies'

    def __str__(self):
        return f"{self.entity.client.name} — {self.get_document_type_display()} ({self.year or 'N/A'})"


# Common document deficiencies by jurisdiction
COMMON_DEFICIENCIES = {
    'federal': [
        {'type': 'annual_resolution', 'desc': 'Annual shareholder resolution', 'severity': 'high'},
        {'type': 'annual_return', 'desc': 'Annual return filed with Corporations Canada', 'severity': 'critical'},
        {'type': 'director_consent', 'desc': 'Consent to act as director (each director)', 'severity': 'high'},
        {'type': 'ubo_register', 'desc': 'Register of individuals with significant control', 'severity': 'critical'},
    ],
    'ontario': [
        {'type': 'annual_return', 'desc': 'Ontario Annual Return (Form 1)', 'severity': 'critical'},
        {'type': 'directors_register', 'desc': 'Updated register of directors', 'severity': 'high'},
        {'type': 'ubo_register', 'desc': 'Ontario Business Registry UBO filing', 'severity': 'critical'},
    ],
    'bc': [
        {'type': 'annual_return', 'desc': 'BC Annual Report filing', 'severity': 'critical'},
        {'type': 'directors_register', 'desc': 'BC Transparency Register', 'severity': 'critical'},
        {'type': 'shareholder_agreement', 'desc': 'Shareholder agreement', 'severity': 'medium'},
    ],
    'alberta': [
        {'type': 'annual_return', 'desc': 'Alberta Annual Return', 'severity': 'critical'},
        {'type': 'directors_register', 'desc': 'Corporate Registry filing — director changes', 'severity': 'high'},
    ],
    'quebec': [
        {'type': 'annual_return', 'desc': 'Déclaration de mise à jour annuelle (REQ)', 'severity': 'critical'},
        {'type': 'bylaw_no1', 'desc': 'Règlement général (French by-law)', 'severity': 'high'},
        {'type': 'shareholder_agreement', 'desc': 'Convention entre actionnaires', 'severity': 'medium'},
    ],
}
