"""
AI Shareholder Agreement Generator.

Drafts full unanimous shareholder agreements with buy-sell,
drag-along, tag-along, shotgun, ROFR, valuation mechanisms.
Builds on existing template infrastructure + AI capabilities.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client, Firm


class ShareholderAgreement(models.Model):
    """A generated shareholder agreement for a corporate entity."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'In Review'),
        ('final', 'Final'),
        ('signed', 'Signed'),
        ('expired', 'Expired'),
    ]
    GOVERNING_LAW_CHOICES = [
        ('ontario', 'Ontario'),
        ('bc', 'British Columbia'),
        ('alberta', 'Alberta'),
        ('federal', 'Federal (CBCA)'),
        ('quebec', 'Quebec'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='shareholder_agreements')
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='shareholder_agreements')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    title = models.CharField(max_length=255, default='Unanimous Shareholder Agreement')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    governing_law = models.CharField(max_length=20, choices=GOVERNING_LAW_CHOICES, default='ontario')

    # Parties
    corporation_name = models.CharField(max_length=255)
    shareholder_names = models.JSONField(default=list, help_text='List of shareholder full names')
    witness_name = models.CharField(max_length=255, blank=True)

    # Key commercial terms
    authorized_shares = models.CharField(max_length=255, blank=True, help_text='e.g., "Unlimited Common shares"')
    issued_shares = models.JSONField(default=dict, blank=True, help_text='{"Shareholder A": 100, "Shareholder B": 50}')

    # Clause selections
    include_right_of_first_refusal = models.BooleanField(default=True)
    include_shotgun_clause = models.BooleanField(default=True)
    include_drag_along = models.BooleanField(default=False)
    include_tag_along = models.BooleanField(default=True)
    include_put_option = models.BooleanField(default=False)
    include_call_option = models.BooleanField(default=False)
    include_non_compete = models.BooleanField(default=True)
    include_confidentiality = models.BooleanField(default=True)
    include_dispute_resolution = models.BooleanField(default=True)
    include_shotgun_deadlock = models.BooleanField(default=True, help_text='Deadlock-breaking shotgun provision')

    # Valuation method for buy-sell
    valuation_method = models.CharField(max_length=30, default='fair_market_value', choices=[
        ('fair_market_value', 'Fair Market Value (FMV)'),
        ('formula', 'Formula / Multiple of EBITDA'),
        ('appraisal', 'Third-Party Appraisal'),
        ('book_value', 'Book Value'),
        ('agreed_value', 'Agreed Value (updated annually)'),
    ])
    valuation_formula = models.CharField(max_length=255, blank=True, help_text='e.g., "5× trailing 12-month EBITDA"')

    # Insurance / funding
    life_insurance_required = models.BooleanField(default=True)
    disability_insurance_required = models.BooleanField(default=False)
    funding_mechanism = models.CharField(max_length=30, default='corporate_redemption', choices=[
        ('corporate_redemption', 'Corporate Redemption'),
        ('cross_purchase', 'Cross-Purchase'),
        ('hybrid', 'Hybrid / Promissory Note'),
    ])

    # Board / governance
    board_seats = models.PositiveIntegerField(default=3)
    quorum_percentage = models.PositiveIntegerField(default=51)
    supermajority_threshold = models.PositiveIntegerField(default=75, help_text='% required for major decisions')
    restricted_matters = models.JSONField(default=list, blank=True, help_text='Decisions requiring supermajority or unanimity')

    # Dividend policy
    dividend_policy = models.TextField(blank=True, default='Dividends declared at discretion of Board of Directors, subject to solvency requirements under applicable corporate law.')

    # Transfer restrictions
    permitted_transfers = models.JSONField(default=list, blank=True, help_text='Transfers exempt from ROFR/ROFO (e.g., to family members)')
    lockup_period_months = models.PositiveIntegerField(default=0, help_text='Initial lockup period in months')

    # Exit provisions
    ipo_provisions = models.BooleanField(default=False)
    drag_threshold_percentage = models.PositiveIntegerField(default=66, help_text='% of shares needed to trigger drag-along')
    tag_threshold_percentage = models.PositiveIntegerField(default=10, help_text='Minimum % of shares to exercise tag-along')

    # Generated content
    generated_content = models.TextField(blank=True, help_text='Full generated agreement text')
    ai_model_used = models.CharField(max_length=50, blank=True)
    generation_cost = models.DecimalField(max_digits=8, decimal_places=4, default=0.0, help_text='API cost for generation')

    # Document
    pdf_generated = models.BooleanField(default=False)
    pdf_document = models.FileField(upload_to='shareholder_agreements/', null=True, blank=True)

    # Billing
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True)
    service_fee = models.DecimalField(max_digits=10, decimal_places=2, default=2499.00, help_text='Fee charged for agreement generation')

    # Signatures
    signed_by_all = models.BooleanField(default=False)
    signed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['firm', 'status']),
        ]
        verbose_name = 'Shareholder Agreement'
        verbose_name_plural = 'Shareholder Agreements'

    def __str__(self):
        return f"{self.title} — {self.client.name} ({self.get_status_display()})"

    def get_shareholder_list(self):
        return self.shareholder_names or []

    def build_prompt_context(self):
        """Build the context dict for AI prompt generation."""
        return {
            'corporation_name': self.corporation_name,
            'shareholders': self.shareholder_names,
            'governing_law': self.get_governing_law_display(),
            'authorized_shares': self.authorized_shares,
            'issued_shares': self.issued_shares,
            'clauses': {
                'ROFR': self.include_right_of_first_refusal,
                'Shotgun': self.include_shotgun_clause,
                'Drag-Along': self.include_drag_along,
                'Tag-Along': self.include_tag_along,
                'Put Option': self.include_put_option,
                'Call Option': self.include_call_option,
                'Non-Compete': self.include_non_compete,
                'Confidentiality': self.include_confidentiality,
                'Dispute Resolution': self.include_dispute_resolution,
            },
            'valuation': {
                'method': self.get_valuation_method_display(),
                'formula': self.valuation_formula,
            },
            'board': {
                'seats': self.board_seats,
                'quorum': self.quorum_percentage,
                'supermajority': self.supermajority_threshold,
            },
            'funding': self.get_funding_mechanism_display(),
            'drag_threshold': self.drag_threshold_percentage,
            'tag_threshold': self.tag_threshold_percentage,
        }


class AgreementTemplate(models.Model):
    """Reusable agreement template / precedent for the firm."""
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='agreement_templates')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    governing_law = models.CharField(max_length=20, choices=ShareholderAgreement._meta.get_field('governing_law').choices, default='ontario')
    content = models.TextField(help_text='Template content with {{ variable }} placeholders')
    is_ai_enhanced = models.BooleanField(default=False)
    use_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-use_count', 'name']
        verbose_name = 'Agreement Template'
        verbose_name_plural = 'Agreement Templates'

    def __str__(self):
        return f"{self.name} — {self.firm.name}"


class AgreementClause(models.Model):
    """Individual clause for composing shareholder agreements."""
    CLAUSE_TYPES = [
        ('definitions', 'Definitions'),
        ('board', 'Board of Directors'),
        ('transfer', 'Transfer Restrictions'),
        ('rofr', 'Right of First Refusal'),
        ('shotgun', 'Shotgun / Buy-Sell'),
        ('drag', 'Drag-Along Rights'),
        ('tag', 'Tag-Along Rights'),
        ('valuation', 'Valuation Mechanism'),
        ('funding', 'Funding / Insurance'),
        ('dividend', 'Dividend Policy'),
        ('non_compete', 'Non-Competition'),
        ('confidentiality', 'Confidentiality'),
        ('dispute', 'Dispute Resolution'),
        ('general', 'General Provisions'),
        ('signatures', 'Execution / Signatures'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='agreement_clauses', null=True, blank=True)
    clause_type = models.CharField(max_length=30, choices=CLAUSE_TYPES)
    title = models.CharField(max_length=255)
    content = models.TextField()
    jurisdiction = models.CharField(max_length=20, choices=ShareholderAgreement._meta.get_field('governing_law').choices, default='ontario')
    is_ai_generated = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    use_count = models.PositiveIntegerField(default=0)
    rating = models.PositiveIntegerField(default=0, help_text='User rating 1-5')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['clause_type', 'title']
        verbose_name = 'Agreement Clause'
        verbose_name_plural = 'Agreement Clauses'

    def __str__(self):
        return f"[{self.get_clause_type_display()}] {self.title}"
