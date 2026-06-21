"""
AI Corporate Structure Advisor.

AI reasons about corporate law + tax together.
"How do I extract $500K tax-efficiently from this holding company?"
Cites legislation, drafts resolution packages, models scenarios.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Client, Firm


class TaxStrategy(models.Model):
    """A tax planning strategy / scenario for a corporate structure."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('analyzing', 'AI Analyzing'),
        ('completed', 'Analysis Complete'),
        ('implemented', 'Implemented'),
        ('archived', 'Archived'),
    ]
    STRATEGY_TYPE_CHOICES = [
        ('dividend', 'Dividend Extraction'),
        ('capital_gain', 'Capital Gain / Sale'),
        ('estate_freeze', 'Estate Freeze'),
        ('reorganization', 'Corporate Reorganization'),
        ('butterfly', 'Butterfly Transaction'),
        ('amalgamation', 'Amalgamation'),
        ('windup', 'Voluntary Dissolution / Wind-Up'),
        ('pipeline', 'Pipeline Transaction'),
        ('surplus_strip', 'Surplus Stripping'),
        ('intercompany', 'Inter-Company Transfer'),
        ('salary_vs_dividend', 'Salary vs. Dividend Optimization'),
        ('holding_company', 'Holding Company Structure'),
        ('trust', 'Family Trust Planning'),
        ('estate', 'Estate / Succession Planning'),
        ('other', 'Other'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='tax_strategies')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='tax_strategies')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    name = models.CharField(max_length=255, help_text='e.g., "Extract $500K from HoldCo for retirement"')
    strategy_type = models.CharField(max_length=30, choices=STRATEGY_TYPE_CHOICES, default='dividend')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Scenario parameters
    goal_description = models.TextField(blank=True, help_text='What the client wants to achieve')
    target_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    time_horizon = models.CharField(max_length=50, default='current_year', choices=[
        ('current_year', 'Current Tax Year'), ('next_year', 'Next Tax Year'),
        ('1_3_years', '1-3 Years'), ('3_5_years', '3-5 Years'), ('5_plus', '5+ Years'),
    ])
    client_priorities = models.JSONField(default=list, blank=True, help_text='e.g., ["minimize_tax", "simplicity", "speed"]')

    # Entity structure snapshot
    entity_structure = models.JSONField(default=dict, blank=True, help_text='Snapshot of entity ownership at time of analysis')
    retained_earnings = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    capital_dividend_account = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    paid_up_capital = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    shareholder_loan_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)

    # AI Analysis
    ai_recommendation = models.TextField(blank=True, help_text='Full AI-written recommendation')
    ai_recommendation_summary = models.TextField(blank=True)
    tax_savings_estimate = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    tax_rate_comparison = models.JSONField(default=dict, blank=True)
    risk_level = models.CharField(max_length=20, default='medium', choices=[
        ('low', 'Low — Straightforward'), ('medium', 'Medium — Standard complexity'),
        ('high', 'High — Complex'), ('very_high', 'Very High — Requires legal opinion'),
    ])
    cited_legislation = models.JSONField(default=list, blank=True, help_text='Sections of ITA, CBCA, etc.')
    implementation_steps = models.JSONField(default=list, blank=True)
    alternative_strategies = models.JSONField(default=list, blank=True)

    # Generated documents
    resolution_generated = models.BooleanField(default=False)
    resolution_document_id = models.PositiveIntegerField(null=True, blank=True)
    supporting_documents = models.JSONField(default=list, blank=True)

    # Billing
    analysis_fee = models.DecimalField(max_digits=10, decimal_places=2, default=1500.00)
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['firm', 'strategy_type']),
        ]
        verbose_name = 'Tax Strategy'
        verbose_name_plural = 'Tax Strategies'

    def __str__(self):
        return f"{self.name} — {self.client.name} ({self.get_strategy_type_display()})"


class StrategyScenario(models.Model):
    """A single what-if scenario within a tax strategy analysis."""
    strategy = models.ForeignKey(TaxStrategy, on_delete=models.CASCADE, related_name='scenarios')
    name = models.CharField(max_length=255, help_text='e.g., "Option A: Salary", "Option B: Dividend"')
    description = models.TextField(blank=True)

    # Financial modeling
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    corporate_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    personal_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    integration_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, help_text='Combined effective rate')
    net_to_shareholder = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    total_tax_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)

    # Comparison
    is_recommended = models.BooleanField(default=False)
    pros = models.JSONField(default=list, blank=True)
    cons = models.JSONField(default=list, blank=True)
    risk_factors = models.JSONField(default=list, blank=True)
    required_filings = models.JSONField(default=list, blank=True)

    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', '-is_recommended']
        verbose_name = 'Strategy Scenario'
        verbose_name_plural = 'Strategy Scenarios'

    def __str__(self):
        return f"{self.name} — Net: ${self.net_to_shareholder:,.2f}"


class TaxQuestion(models.Model):
    """A question posed to the AI tax advisor. Used for training and common Q&A."""
    question = models.TextField()
    answer = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=TaxStrategy.STRATEGY_TYPE_CHOICES, default='other')
    jurisdiction = models.CharField(max_length=30, default='federal')
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    use_count = models.PositiveIntegerField(default=0)
    helpful_count = models.PositiveIntegerField(default=0)
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, null=True, blank=True, related_name='tax_questions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-use_count']
        verbose_name = 'Tax Question'
        verbose_name_plural = 'Tax Questions'

    def __str__(self):
        return self.question[:100]
