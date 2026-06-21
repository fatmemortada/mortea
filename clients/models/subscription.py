"""
Entity subscription plans — per-entity/month pricing engine.

This is the recurring revenue foundation of Mortacc.
Firms subscribe clients' entities to plans that automate annual maintenance,
compliance monitoring, and document generation.
"""
from django.db import models
from django.utils import timezone
from .client import Client, Firm


class SubscriptionPlan(models.Model):
    """
    A subscription plan template that firms can assign to entities.

    Plans define what's included: compliance monitoring, document generation,
    annual return filing, registered agent service, etc.
    """
    PLAN_TIER_CHOICES = [
        ('basic', 'Basic'),
        ('standard', 'Standard'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
    ]
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
    ]

    name = models.CharField(max_length=100)
    tier = models.CharField(max_length=20, choices=PLAN_TIER_CHOICES, default='standard')
    description = models.TextField(blank=True)

    # Pricing — in cents to avoid float issues
    price_monthly = models.PositiveIntegerField(default=0, help_text='Price in cents')
    price_quarterly = models.PositiveIntegerField(default=0, help_text='Price in cents')
    price_annual = models.PositiveIntegerField(default=0, help_text='Price in cents')

    # Feature flags
    includes_compliance_monitoring = models.BooleanField(default=True)
    includes_document_generation = models.BooleanField(default=False, help_text='Auto-generate annual resolutions, minutes')
    includes_annual_return_filing = models.BooleanField(default=False)
    includes_registered_agent = models.BooleanField(default=False)
    includes_ubo_monitoring = models.BooleanField(default=False, help_text='Beneficial ownership monitoring')
    includes_ai_drafting = models.BooleanField(default=False, help_text='AI-powered document drafting')
    includes_api_access = models.BooleanField(default=False)
    max_documents_per_month = models.PositiveIntegerField(default=0, help_text='0 = unlimited')
    max_entities = models.PositiveIntegerField(default=1, help_text='Max entities covered by this plan')

    # Display
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=7, default='#2563eb', help_text='Hex color for UI badge')
    icon = models.CharField(max_length=50, default='building', help_text='Icon name for UI')

    # Stripe integration
    stripe_price_id_monthly = models.CharField(max_length=100, blank=True, help_text='Stripe Price ID for monthly billing')
    stripe_price_id_annual = models.CharField(max_length=100, blank=True, help_text='Stripe Price ID for annual billing')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'tier']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'

    def __str__(self):
        return f"{self.name} (${self.price_monthly/100:.2f}/mo)"

    def price_for_cycle(self, cycle):
        """Return the price in dollars for the given billing cycle."""
        mapping = {
            'monthly': self.price_monthly,
            'quarterly': self.price_quarterly,
            'annual': self.price_annual,
        }
        return (mapping.get(cycle, self.price_monthly) or 0) / 100

    @property
    def display_price(self):
        """Human-readable price string."""
        if self.price_monthly:
            return f"${self.price_monthly/100:.2f}/mo"
        return 'Free'


class EntitySubscription(models.Model):
    """
    Links a Client entity to a SubscriptionPlan with billing details.

    This is the core recurring revenue record. Each subscribed entity
    generates recurring revenue for Mortacc.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('trialing', 'Trialing'),
        ('paused', 'Paused'),
    ]
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
    ]

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='subscriptions'
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions'
    )
    firm = models.ForeignKey(
        Firm, on_delete=models.CASCADE, related_name='entity_subscriptions'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES, default='annual')

    # Billing dates
    current_period_start = models.DateField(null=True, blank=True)
    current_period_end = models.DateField(null=True, blank=True)
    next_billing_date = models.DateField(null=True, blank=True)
    trial_end_date = models.DateField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    # Custom pricing (override plan defaults)
    custom_price_override = models.PositiveIntegerField(null=True, blank=True, help_text='Override price in cents')

    # Stripe subscription ID for this entity
    stripe_subscription_id = models.CharField(max_length=100, blank=True)

    # Auto-renewal
    auto_renew = models.BooleanField(default=True)

    # What's actually being provided
    services_included = models.JSONField(default=dict, blank=True, help_text='Custom service overrides per entity')

    # Notes
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['firm', 'status']),
            models.Index(fields=['next_billing_date']),
            models.Index(fields=['status', 'next_billing_date']),
        ]
        verbose_name = 'Entity Subscription'
        verbose_name_plural = 'Entity Subscriptions'

    def __str__(self):
        return f"{self.client.name} — {self.plan.name} ({self.get_status_display()})"

    @property
    def monthly_revenue(self):
        """Effective monthly revenue from this subscription."""
        price = self.custom_price_override or self.plan.price_monthly
        if self.billing_cycle == 'annual':
            price = self.custom_price_override or self.plan.price_annual
            return price / 12
        elif self.billing_cycle == 'quarterly':
            price = self.custom_price_override or self.plan.price_quarterly
            return price / 3
        return price

    @property
    def is_active(self):
        return self.status in ('active', 'trialing')

    def cancel(self, reason=''):
        """Cancel this subscription."""
        self.status = 'canceled'
        self.canceled_at = timezone.now()
        self.cancellation_reason = reason
        self.auto_renew = False
        self.save()

    def change_plan(self, new_plan, new_cycle=None):
        """Change to a new plan at the next billing date."""
        self.plan = new_plan
        if new_cycle:
            self.billing_cycle = new_cycle
        self.save()


class SubscriptionInvoice(models.Model):
    """
    Invoice generated for an entity subscription billing cycle.
    Links the subscription to the actual invoice record.
    """
    subscription = models.ForeignKey(
        EntitySubscription, on_delete=models.CASCADE, related_name='subscription_invoices'
    )
    invoice = models.OneToOneField(
        'Invoice', on_delete=models.CASCADE, related_name='subscription_invoice'
    )
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    amount_charged = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_invoice_id = models.CharField(max_length=100, blank=True)
    stripe_invoice_url = models.URLField(blank=True)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', 'is_paid']),
        ]

    def __str__(self):
        return f"Subscription Invoice #{self.id} — {self.subscription.client.name}"


# ─── Built-in default plans ───────────────────────────────────────────────────

DEFAULT_PLANS = [
    {
        'name': 'Basic Compliance',
        'tier': 'basic',
        'description': 'Essential compliance monitoring and deadline tracking for a single entity.',
        'price_monthly': 2900,   # $29/mo
        'price_annual': 29000,   # $290/yr (save ~17%)
        'includes_compliance_monitoring': True,
        'includes_document_generation': False,
        'includes_annual_return_filing': False,
        'includes_registered_agent': False,
        'includes_ubo_monitoring': False,
        'includes_ai_drafting': False,
        'max_documents_per_month': 5,
        'color': '#6b7280',
        'icon': 'shield-check',
        'sort_order': 1,
    },
    {
        'name': 'Standard',
        'tier': 'standard',
        'description': 'Full compliance + document generation for active entities. Best for most small businesses.',
        'price_monthly': 7900,   # $79/mo
        'price_annual': 79000,   # $790/yr
        'includes_compliance_monitoring': True,
        'includes_document_generation': True,
        'includes_annual_return_filing': True,
        'includes_registered_agent': False,
        'includes_ubo_monitoring': True,
        'includes_ai_drafting': False,
        'max_documents_per_month': 20,
        'color': '#2563eb',
        'icon': 'star',
        'sort_order': 2,
    },
    {
        'name': 'Premium',
        'tier': 'premium',
        'description': 'Everything included — AI drafting, registered agent, priority support. For complex entities.',
        'price_monthly': 19900,  # $199/mo
        'price_annual': 199000,  # $1,990/yr
        'includes_compliance_monitoring': True,
        'includes_document_generation': True,
        'includes_annual_return_filing': True,
        'includes_registered_agent': True,
        'includes_ubo_monitoring': True,
        'includes_ai_drafting': True,
        'max_documents_per_month': 0,  # unlimited
        'color': '#7c3aed',
        'icon': 'sparkles',
        'sort_order': 3,
    },
    {
        'name': 'Enterprise',
        'tier': 'enterprise',
        'description': 'Bulk entity management. Volume pricing. API access. Dedicated support. For CSPs and large firms.',
        'price_monthly': 49900,  # $499/mo
        'price_annual': 499000,  # $4,990/yr
        'includes_compliance_monitoring': True,
        'includes_document_generation': True,
        'includes_annual_return_filing': True,
        'includes_registered_agent': True,
        'includes_ubo_monitoring': True,
        'includes_ai_drafting': True,
        'includes_api_access': True,
        'max_entities': 50,
        'max_documents_per_month': 0,
        'color': '#dc2626',
        'icon': 'building-office',
        'sort_order': 4,
    },
]


def seed_default_plans():
    """Create default subscription plans if they don't exist."""
    from django.db import transaction

    created_count = 0
    with transaction.atomic():
        for plan_data in DEFAULT_PLANS:
            _, created = SubscriptionPlan.objects.get_or_create(
                name=plan_data['name'],
                defaults=plan_data,
            )
            if created:
                created_count += 1
    return created_count
