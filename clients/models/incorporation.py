"""
End-to-End Incorporation Engine.

Tracks the full incorporation workflow: name search → NUANS →
articles → CRA BN → GST/HST → bank account → welcome package.
Each step generates documents, tracks status, and feeds into
compliance and billing once complete.
"""
from django.db import models
from django.utils import timezone
from .client import Client, Firm


class IncorporationProject(models.Model):
    """
    A single incorporation project tracking all steps from
    name search through final welcome package delivery.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('name_search', 'Name Search'),
        ('nuans', 'NUANS Report'),
        ('articles', 'Articles of Incorporation'),
        ('bylaws', 'Organizational By-laws'),
        ('org_resolutions', 'Organizational Resolutions'),
        ('cra_bn', 'CRA Business Number'),
        ('gst_hst', 'GST/HST Registration'),
        ('payroll', 'Payroll Registration'),
        ('banking', 'Banking Package'),
        ('minute_book', 'Minute Book Assembly'),
        ('welcome_package', 'Welcome Package'),
        ('complete', 'Complete'),
        ('on_hold', 'On Hold'),
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
        ('pei', 'PEI'),
        ('newfoundland', 'Newfoundland & Labrador'),
        ('nunavut', 'Nunavut'),
        ('nwt', 'Northwest Territories'),
        ('yukon', 'Yukon'),
    ]

    CORPORATE_STRUCTURE_CHOICES = [
        ('named', 'Named Share Corporation'),
        ('numbered', 'Numbered Corporation'),
        ('professional', 'Professional Corporation'),
        ('nonprofit', 'Non-Profit / Charity'),
        ('unlimited', 'Unlimited Liability Company'),
    ]

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='incorporation_projects'
    )
    firm = models.ForeignKey(
        Firm, on_delete=models.CASCADE, related_name='incorporation_projects'
    )

    # Basic info
    proposed_name_1 = models.CharField(max_length=255, blank=True, help_text='First choice name')
    proposed_name_2 = models.CharField(max_length=255, blank=True, help_text='Second choice name')
    proposed_name_3 = models.CharField(max_length=255, blank=True, help_text='Third choice name')
    is_numbered = models.BooleanField(default=False, help_text='Use numbered company instead of named')

    jurisdiction = models.CharField(max_length=30, choices=JURISDICTION_CHOICES, default='federal')
    structure_type = models.CharField(max_length=20, choices=CORPORATE_STRUCTURE_CHOICES, default='named')

    # Core details
    registered_address = models.TextField(blank=True)
    mailing_address = models.TextField(blank=True)
    business_activity = models.TextField(blank=True, help_text='Description of business activity')

    # Share structure
    authorized_shares = models.TextField(blank=True, help_text='e.g., "Unlimited Common shares without par value"')
    has_multiple_share_classes = models.BooleanField(default=False)
    share_class_details = models.TextField(blank=True)

    # Director(s)
    min_directors = models.PositiveIntegerField(default=1)
    max_directors = models.PositiveIntegerField(default=10)

    # Fiscal year
    fiscal_year_end = models.CharField(max_length=20, default='December 31')

    # Workflow tracking
    current_step = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    steps_completed = models.JSONField(default=list, blank=True)
    steps_pending = models.JSONField(default=list, blank=True)
    total_steps = models.PositiveIntegerField(default=10)

    # Billing integration
    fixed_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text='Fixed incorporation fee')
    disbursements = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text='Government filing fees etc.')
    invoice_generated = models.BooleanField(default=False)
    invoice = models.ForeignKey(
        'Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='incorporation_project'
    )

    # Documents generated
    documents_generated = models.JSONField(default=list, blank=True, help_text='List of document IDs/names generated')

    # Completion tracking
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_incorporations'
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'current_step']),
            models.Index(fields=['firm', 'current_step']),
            models.Index(fields=['jurisdiction']),
        ]
        verbose_name = 'Incorporation Project'
        verbose_name_plural = 'Incorporation Projects'

    def __str__(self):
        return f"Incorporation: {self.client.name} ({self.get_jurisdiction_display()}) — {self.get_current_step_display()}"

    @property
    def progress_pct(self):
        """Calculate completion percentage."""
        if self.current_step == 'complete':
            return 100
        step_order = [s[0] for s in self.STATUS_CHOICES]
        try:
            current_idx = step_order.index(self.current_step)
            return int((current_idx / (len(step_order) - 2)) * 100)  # -2 for 'complete' and 'on_hold'
        except (ValueError, IndexError):
            return 0

    @property
    def estimated_total_cost(self):
        """Total cost estimate including fees and disbursements."""
        return float(self.fixed_fee or 0) + float(self.disbursements or 0)

    @property
    def days_in_progress(self):
        """Days since project was created."""
        if self.completed_at:
            delta = self.completed_at - self.created_at
        else:
            delta = timezone.now() - self.created_at
        return max(1, delta.days)

    def advance_step(self, new_step, save=True):
        """Advance to the next step, recording the current step as completed."""
        if self.current_step not in self.steps_completed and self.current_step != 'draft':
            self.steps_completed.append(self.current_step)
        self.current_step = new_step
        if save:
            self.save()

    def mark_complete(self, user=None):
        """Mark the project as complete."""
        if self.current_step not in self.steps_completed:
            self.steps_completed.append(self.current_step)
        self.current_step = 'complete'
        self.completed_at = timezone.now()
        if user:
            self.completed_by = user
        self.save()

    def get_required_documents(self):
        """Return list of documents that should be generated for this incorporation."""
        docs = [
            ('articles', 'Articles of Incorporation'),
            ('bylaw_no1', 'By-law No. 1'),
            ('org_resolution_directors', 'Organizational Resolution — Directors'),
            ('org_resolution_shareholders', 'Organizational Resolution — Shareholders'),
            ('directors_register', 'Register of Directors'),
            ('shareholders_register', 'Register of Shareholders'),
            ('share_certificates', 'Share Certificates'),
            ('banking_resolution', 'Banking Resolution'),
            ('consent_directors', 'Consent to Act as Director'),
            ('subscription_shares', 'Subscription for Shares'),
        ]
        if self.jurisdiction == 'federal':
            docs.append(('nuans_report', 'NUANS Name Search Report'))
        if self.structure_type == 'professional':
            docs.append(('professional_corp_cert', 'Professional Corporation Certificate'))
        return docs


class IncorporationStep(models.Model):
    """
    Individual step within an incorporation project.
    Tracks completion status, generated documents, and notes.
    """
    project = models.ForeignKey(
        IncorporationProject, on_delete=models.CASCADE, related_name='steps'
    )
    step_key = models.CharField(max_length=50)
    step_name = models.CharField(max_length=255)
    step_order = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ], default='pending')

    checklist_items = models.JSONField(default=list, blank=True)
    generated_documents = models.JSONField(default=list, blank=True)
    external_reference = models.CharField(max_length=255, blank=True, help_text='NUANS order #, CRA confirmation #, etc.')

    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['step_order']
        unique_together = ['project', 'step_key']
        indexes = [
            models.Index(fields=['project', 'status']),
        ]

    def __str__(self):
        return f"{self.project.client.name} — {self.step_name} ({self.get_status_display()})"

    def mark_complete(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


# Default workflow steps for each jurisdiction
INCORPORATION_WORKFLOW = [
    {'key': 'name_search', 'name': 'Name Search & Availability', 'order': 1},
    {'key': 'nuans', 'name': 'NUANS Report (Federal)', 'order': 2},
    {'key': 'client_info', 'name': 'Collect Client Information', 'order': 3},
    {'key': 'articles', 'name': 'Prepare Articles of Incorporation', 'order': 4},
    {'key': 'bylaws', 'name': 'Prepare By-law No. 1', 'order': 5},
    {'key': 'org_resolutions', 'name': 'Organizational Resolutions', 'order': 6},
    {'key': 'share_structure', 'name': 'Set Up Share Structure', 'order': 7},
    {'key': 'directors_officers', 'name': 'Appoint Directors & Officers', 'order': 8},
    {'key': 'cra_bn', 'name': 'CRA Business Number Application', 'order': 9},
    {'key': 'gst_hst', 'name': 'GST/HST Registration', 'order': 10},
    {'key': 'payroll', 'name': 'Payroll Account Setup', 'order': 11},
    {'key': 'banking', 'name': 'Banking Package & Account Setup', 'order': 12},
    {'key': 'minute_book', 'name': 'Assemble Minute Book', 'order': 13},
    {'key': 'welcome_package', 'name': 'Client Welcome Package', 'order': 14},
    {'key': 'compliance_setup', 'name': 'Set Up Compliance Tracking', 'order': 15},
]
