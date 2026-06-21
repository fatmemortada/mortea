"""
AI Full Document Suite.

AI drafting for 15+ corporate document types beyond basic
resolutions: amalgamations, continuances, dissolutions,
estate freezes, butterfly transactions, asset/share purchases,
professional corporation setup, and more.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client, Firm


class AIDocument(models.Model):
    """An AI-generated corporate document."""
    DOCUMENT_TYPES = [
        # Existing types expanded
        ('articles_amalgamation', 'Articles of Amalgamation'),
        ('articles_continuance', 'Articles of Continuance'),
        ('articles_dissolution', 'Articles of Dissolution'),
        ('articles_revival', 'Articles of Revival'),
        ('articles_amendment', 'Articles of Amendment'),
        # Reorganizations
        ('estate_freeze', 'Estate Freeze Package'),
        ('butterfly', 'Butterfly Transaction Documents'),
        ('section85_rollover', 'Section 85 Rollover Agreement'),
        ('section86_exchange', 'Section 86 Share Exchange'),
        # Transactions
        ('asset_purchase', 'Asset Purchase Agreement'),
        ('share_purchase', 'Share Purchase Agreement'),
        ('amalgamation_agreement', 'Amalgamation Agreement'),
        # Governance
        ('unanimous_sha', 'Unanimous Shareholder Agreement'),
        ('limited_partnership', 'Limited Partnership Agreement'),
        ('joint_venture', 'Joint Venture Agreement'),
        ('voting_trust', 'Voting Trust Agreement'),
        # Tax
        ('t2057_election', 'T2057 Election Form'),
        ('t2058_election', 'T2058 Election Form'),
        ('capital_dividend_election', 'Capital Dividend Election'),
        # Special
        ('professional_corp', 'Professional Corporation Setup Package'),
        ('not_for_profit', 'Not-For-Profit Incorporation Package'),
        ('offshore_setup', 'Offshore/International Structure'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'), ('generated', 'Generated'), ('reviewed', 'Reviewed'),
        ('final', 'Final'), ('signed', 'Signed'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='ai_documents')
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='ai_documents')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Context for AI generation
    context_data = models.JSONField(default=dict, blank=True, help_text='Variables for template population')
    generated_content = models.TextField(blank=True)
    generation_prompt = models.TextField(blank=True)
    ai_model = models.CharField(max_length=50, default='claude')

    # Output
    pdf_file = models.FileField(upload_to='ai_documents/', null=True, blank=True)
    word_file = models.FileField(upload_to='ai_documents/', null=True, blank=True)

    # Billing
    document_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'document_type']),
            models.Index(fields=['firm', 'status']),
        ]
        verbose_name = 'AI Document'
        verbose_name_plural = 'AI Documents'

    def __str__(self):
        return f"{self.get_document_type_display()} — {self.client.name}"


# Document type metadata: pricing, complexity, required context
DOCUMENT_REGISTRY = {
    'articles_amalgamation': {
        'name': 'Articles of Amalgamation',
        'fee': 2499, 'complexity': 'high',
        'description': 'Merges two or more corporations into one. Requires approval from each board and shareholders.',
        'required_context': ['amalgamating_entities', 'share_exchange_ratio', 'new_name'],
    },
    'articles_continuance': {
        'name': 'Articles of Continuance',
        'fee': 1999, 'complexity': 'high',
        'description': 'Continues a corporation from one jurisdiction to another while preserving its legal identity.',
        'required_context': ['current_jurisdiction', 'target_jurisdiction', 'entity_name'],
    },
    'articles_dissolution': {
        'name': 'Articles of Dissolution',
        'fee': 1499, 'complexity': 'medium',
        'description': 'Voluntarily dissolves a corporation. Requires clearance certificates, final tax returns.',
        'required_context': ['entity_name', 'reason', 'asset_distribution_plan'],
    },
    'estate_freeze': {
        'name': 'Estate Freeze Package',
        'fee': 3499, 'complexity': 'very_high',
        'description': 'Locks in current value via preferred shares. New common shares to next generation. Includes S.86 election.',
        'required_context': ['current_fmv', 'freeze_shareholders', 'growth_shareholders', 'valuation_method'],
    },
    'butterfly': {
        'name': 'Butterfly Transaction Documents',
        'fee': 4999, 'complexity': 'very_high',
        'description': 'Tax-deferred division of corporation between shareholders. Highly technical CRA requirements.',
        'required_context': ['entity_name', 'division_type', 'shareholder_groups', 'asset_allocation'],
    },
    'section85_rollover': {
        'name': 'Section 85 Rollover Agreement',
        'fee': 1499, 'complexity': 'medium',
        'description': 'Tax-deferred transfer of assets to a corporation in exchange for shares.',
        'required_context': ['transferor', 'assets', 'consideration', 'elected_amount'],
    },
    'asset_purchase': {
        'name': 'Asset Purchase Agreement',
        'fee': 2499, 'complexity': 'high',
        'description': 'Purchase of business assets rather than shares. Includes bulk sales compliance.',
        'required_context': ['purchaser', 'vendor', 'assets', 'purchase_price', 'allocation'],
    },
    'share_purchase': {
        'name': 'Share Purchase Agreement',
        'fee': 2999, 'complexity': 'high',
        'description': 'Purchase of shares directly from shareholders. Includes representations and warranties.',
        'required_context': ['purchaser', 'vendor', 'shares', 'price_per_share', 'closing_date'],
    },
    'professional_corp': {
        'name': 'Professional Corporation Setup',
        'fee': 1999, 'complexity': 'medium',
        'description': 'Setup package for regulated professionals (doctors, lawyers, accountants, etc.).',
        'required_context': ['professional_name', 'governing_body', 'license_number', 'jurisdiction'],
    },
    'not_for_profit': {
        'name': 'Not-For-Profit Incorporation',
        'fee': 1799, 'complexity': 'medium',
        'description': 'Incorporation of a non-profit organization or charity under the CNCA or provincial equivalent.',
        'required_context': ['organization_name', 'purpose', 'directors', 'membership_structure'],
    },
    'limited_partnership': {
        'name': 'Limited Partnership Agreement',
        'fee': 2499, 'complexity': 'high',
        'description': 'Agreement between general partner and limited partners. Profit/loss allocation, management rights.',
        'required_context': ['gp_name', 'lp_names', 'capital_contributions', 'profit_split'],
    },
    'joint_venture': {
        'name': 'Joint Venture Agreement',
        'fee': 2999, 'complexity': 'high',
        'description': 'Two or more parties collaborate on specific project. Not a partnership. Shared costs and revenues.',
        'required_context': ['parties', 'project_description', 'contributions', 'revenue_split', 'term'],
    },
}
