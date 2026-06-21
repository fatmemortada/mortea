"""
Enhanced Multi-Jurisdiction Compliance Hub.

Jurisdiction-specific rules, registry fee schedules, filing
requirements for all 14 Canadian jurisdictions. Enhanced
deadline intelligence with cascading dependencies.
"""
from django.db import models
from django.utils import timezone
from .client import Firm


class JurisdictionRules(models.Model):
    """Rules and requirements for a specific Canadian jurisdiction."""
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
        ('pei', 'Prince Edward Island'),
        ('newfoundland', 'Newfoundland & Labrador'),
        ('nunavut', 'Nunavut'),
        ('nwt', 'Northwest Territories'),
        ('yukon', 'Yukon'),
    ]
    ENTITY_TYPE_CHOICES = [
        ('business', 'Business Corporation'),
        ('professional', 'Professional Corporation'),
        ('nonprofit', 'Non-Profit / Society'),
        ('unlimited', 'Unlimited Liability Company'),
        ('llp', 'Limited Liability Partnership'),
    ]

    jurisdiction = models.CharField(max_length=30, choices=JURISDICTION_CHOICES, unique=True)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPE_CHOICES, default='business')

    # Core requirements
    min_directors = models.PositiveIntegerField(default=1)
    min_shareholders = models.PositiveIntegerField(default=1)
    requires_canadian_resident_director = models.BooleanField(default=True, help_text='At least 25% must be Canadian residents for federal')
    requires_auditor = models.BooleanField(default=False)

    # Filing requirements
    annual_return_due_months = models.PositiveIntegerField(default=12, help_text='Months after incorporation or last filing')
    annual_return_name = models.CharField(max_length=255, default='Annual Return', help_text='What this jurisdiction calls it')
    annual_return_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    annual_return_online_filing = models.BooleanField(default=True)
    annual_return_filing_url = models.URLField(blank=True)

    # Extra-provincial registration
    extra_provincial_required = models.BooleanField(default=False)
    extra_provincial_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    extra_provincial_renewal_months = models.PositiveIntegerField(default=12)

    # Transparency / UBO
    requires_ubo_register = models.BooleanField(default=True)
    ubo_registry_name = models.CharField(max_length=255, blank=True)

    # Tax
    corporate_tax_rate_general = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, help_text='General corporate tax rate %')
    corporate_tax_rate_small_business = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    small_business_limit = models.DecimalField(max_digits=12, decimal_places=2, default=500000.00)
    hst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)

    # Filing deadlines
    t2_deadline_months_after_ye = models.PositiveIntegerField(default=6)
    t2_installment_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=3000.00)

    # Governing legislation
    governing_act = models.CharField(max_length=255, blank=True)
    registry_name = models.CharField(max_length=255, blank=True)
    registry_url = models.URLField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['jurisdiction']
        verbose_name_plural = 'Jurisdiction Rules'

    def __str__(self):
        return f"{self.get_jurisdiction_display()} — {self.get_entity_type_display()}"


class ComplianceDeadlineRule(models.Model):
    """A specific compliance deadline rule for a firm or jurisdiction."""
    TRIGGER_CHOICES = [
        ('incorporation', 'After Incorporation'),
        ('fiscal_year_end', 'After Fiscal Year End'),
        ('anniversary', 'On Anniversary Date'),
        ('event', 'After Specific Event'),
        ('quarterly', 'Quarterly'),
        ('monthly', 'Monthly'),
        ('annual', 'Annual'),
    ]

    jurisdiction = models.CharField(max_length=30, choices=JurisdictionRules.JURISDICTION_CHOICES, default='federal')
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, null=True, blank=True, related_name='custom_deadline_rules')
    task_type = models.CharField(max_length=50)
    task_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    trigger = models.CharField(max_length=30, choices=TRIGGER_CHOICES, default='annual')
    trigger_offset_days = models.IntegerField(default=0, help_text='Days after trigger to set deadline')
    trigger_month = models.PositiveIntegerField(null=True, blank=True, help_text='Specific month for annual deadlines')
    trigger_day = models.PositiveIntegerField(null=True, blank=True)

    priority = models.CharField(max_length=20, default='normal', choices=[
        ('critical', 'Critical'), ('high', 'High'), ('normal', 'Normal'), ('low', 'Low'),
    ])
    penalty_description = models.TextField(blank=True, help_text='What happens if missed')
    estimated_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=True, help_text='System-provided default rule')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['jurisdiction', 'priority']
        verbose_name = 'Compliance Deadline Rule'
        verbose_name_plural = 'Compliance Deadline Rules'

    def __str__(self):
        return f"[{self.get_jurisdiction_display()}] {self.task_name} ({self.get_trigger_display()})"


class RegistryFeeSchedule(models.Model):
    """Fee schedule for a jurisdiction's corporate registry."""
    jurisdiction = models.CharField(max_length=30, choices=JurisdictionRules.JURISDICTION_CHOICES)
    filing_type = models.CharField(max_length=100, help_text='e.g., "Articles of Incorporation", "Annual Return"')
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='CAD')
    expedited_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    expedited_days = models.PositiveIntegerField(default=0, help_text='Processing days if expedited')
    standard_days = models.PositiveIntegerField(default=10, help_text='Standard processing days')
    is_online = models.BooleanField(default=True)
    payment_methods = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    effective_date = models.DateField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['jurisdiction', 'filing_type']
        verbose_name = 'Registry Fee Schedule'
        verbose_name_plural = 'Registry Fee Schedules'

    def __str__(self):
        return f"{self.get_jurisdiction_display()} — {self.filing_type} (${self.fee_amount})"


class ComplianceAlert(models.Model):
    """A compliance alert for a specific entity — generated by the rules engine."""
    SEVERITY_CHOICES = [
        ('critical', 'Critical — Immediate action required'),
        ('warning', 'Warning — Action needed soon'),
        ('info', 'Information — For awareness'),
    ]

    client_id = models.PositiveIntegerField()
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='compliance_alerts')
    jurisdiction = models.CharField(max_length=30)
    title = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='info')
    due_date = models.DateField(null=True, blank=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    source_rule = models.ForeignKey(ComplianceDeadlineRule, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-severity', 'due_date']
        indexes = [
            models.Index(fields=['client_id', 'resolved']),
            models.Index(fields=['firm', 'severity']),
        ]
        verbose_name = 'Compliance Alert'
        verbose_name_plural = 'Compliance Alerts'

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.title}"


# Seed data — Canadian jurisdiction rules
CANADIAN_JURISDICTION_RULES = [
    {
        'jurisdiction': 'federal', 'entity_type': 'business',
        'min_directors': 1, 'requires_canadian_resident_director': True,
        'annual_return_name': 'Annual Return (Form 22)',
        'annual_return_fee': 20.00, 'extra_provincial_required': False,
        'corporate_tax_rate_general': 15.0, 'corporate_tax_rate_small_business': 9.0,
        'small_business_limit': 500000, 'gst_rate': 5.0, 'hst_rate': 0.0,
        'governing_act': 'Canada Business Corporations Act',
        'registry_name': 'Corporations Canada', 'registry_url': 'https://ised-isde.canada.ca/',
    },
    {
        'jurisdiction': 'ontario', 'entity_type': 'business',
        'min_directors': 1, 'requires_canadian_resident_director': True,
        'annual_return_name': 'Annual Return (Form 1)',
        'annual_return_fee': 0.00, 'extra_provincial_required': True, 'extra_provincial_fee': 300.00,
        'corporate_tax_rate_general': 11.5, 'corporate_tax_rate_small_business': 3.2,
        'small_business_limit': 500000, 'hst_rate': 13.0,
        'governing_act': 'Business Corporations Act (Ontario)',
        'registry_name': 'Ontario Business Registry', 'registry_url': 'https://www.ontario.ca/page/business',
    },
    {
        'jurisdiction': 'bc', 'entity_type': 'business',
        'min_directors': 1, 'requires_canadian_resident_director': False,
        'annual_return_name': 'Annual Report',
        'annual_return_fee': 43.39, 'extra_provincial_required': True, 'extra_provincial_fee': 350.00,
        'corporate_tax_rate_general': 12.0, 'corporate_tax_rate_small_business': 2.0,
        'small_business_limit': 500000, 'gst_rate': 5.0, 'hst_rate': 0.0,
        'governing_act': 'Business Corporations Act (BC)',
        'registry_name': 'BC Corporate Registry', 'registry_url': 'https://www.bcregistry.ca/',
    },
    {
        'jurisdiction': 'alberta', 'entity_type': 'business',
        'min_directors': 1, 'requires_canadian_resident_director': True,
        'annual_return_name': 'Annual Return',
        'annual_return_fee': 75.00, 'extra_provincial_required': True, 'extra_provincial_fee': 425.00,
        'corporate_tax_rate_general': 8.0, 'corporate_tax_rate_small_business': 2.0,
        'small_business_limit': 500000, 'gst_rate': 5.0, 'hst_rate': 0.0,
        'governing_act': 'Business Corporations Act (Alberta)',
        'registry_name': 'Alberta Corporate Registry', 'registry_url': 'https://www.alberta.ca/corporate-registry.aspx',
    },
    {
        'jurisdiction': 'quebec', 'entity_type': 'business',
        'min_directors': 1, 'requires_canadian_resident_director': False,
        'annual_return_name': 'Déclaration de mise à jour annuelle',
        'annual_return_fee': 82.00, 'extra_provincial_required': True, 'extra_provincial_fee': 318.00,
        'corporate_tax_rate_general': 11.5, 'corporate_tax_rate_small_business': 3.2,
        'small_business_limit': 500000, 'hst_rate': 0.0, 'gst_rate': 5.0, 'qst_rate': 9.975,
        'governing_act': 'Business Corporations Act (Quebec)',
        'registry_name': 'Registraire des entreprises du Québec', 'registry_url': 'https://www.registreentreprises.gouv.qc.ca/',
    },
]
