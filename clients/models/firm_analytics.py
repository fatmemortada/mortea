"""
Firm Analytics + Benchmarking Dashboard.

Revenue per entity type, compliance trends, staff utilization,
practice area profitability. Anonymous industry benchmarking.
"""
from django.db import models
from .client import Firm


class FirmAnalyticsSnapshot(models.Model):
    """A periodic snapshot of firm metrics for trend analysis."""
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='analytics_snapshots')
    period = models.CharField(max_length=10, choices=[
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ])
    snapshot_date = models.DateField()

    # Client metrics
    total_clients = models.PositiveIntegerField(default=0)
    active_clients = models.PositiveIntegerField(default=0)
    new_clients_this_period = models.PositiveIntegerField(default=0)
    churned_clients_this_period = models.PositiveIntegerField(default=0)

    # Entity metrics
    total_entities = models.PositiveIntegerField(default=0)
    entities_by_jurisdiction = models.JSONField(default=dict, blank=True)
    incorporation_count = models.PositiveIntegerField(default=0)

    # Revenue metrics
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    recurring_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    one_time_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    average_revenue_per_client = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    subscription_mrr = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)

    # Service breakdown
    revenue_by_service = models.JSONField(default=dict, blank=True)

    # Compliance
    total_compliance_tasks = models.PositiveIntegerField(default=0)
    overdue_tasks = models.PositiveIntegerField(default=0)
    completed_tasks = models.PositiveIntegerField(default=0)
    average_compliance_score = models.PositiveIntegerField(default=0)

    # Billing
    total_invoiced = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    total_collected = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    outstanding_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    collection_rate = models.PositiveIntegerField(default=0)

    # Staff
    total_staff = models.PositiveIntegerField(default=0)
    total_billable_hours = models.DecimalField(max_digits=10, decimal_places=1, default=0.0)
    total_billed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    utilization_rate = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-snapshot_date']
        unique_together = ['firm', 'period', 'snapshot_date']
        verbose_name = 'Analytics Snapshot'
        verbose_name_plural = 'Analytics Snapshots'

    def __str__(self):
        return f"{self.firm.name} — {self.get_period_display()} {self.snapshot_date}"


class IndustryBenchmark(models.Model):
    """Anonymous aggregated industry benchmarks for comparison."""
    FIRM_SIZE_CHOICES = [
        ('solo', 'Solo Practitioner'),
        ('small', '2-5 Professionals'),
        ('medium', '6-20 Professionals'),
        ('large', '21-50 Professionals'),
        ('enterprise', '50+ Professionals'),
    ]
    FIRM_TYPE_CHOICES = [
        ('accounting', 'Accounting Firm'),
        ('law', 'Law Firm'),
        ('csp', 'Corporate Service Provider'),
        ('mixed', 'Mixed Practice'),
    ]

    firm_size = models.CharField(max_length=20, choices=FIRM_SIZE_CHOICES)
    firm_type = models.CharField(max_length=20, choices=FIRM_TYPE_CHOICES)
    period = models.CharField(max_length=10, default='monthly')

    # Aggregated anonymous data
    sample_size = models.PositiveIntegerField(default=0)

    avg_clients = models.PositiveIntegerField(default=0)
    avg_revenue_per_client = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    avg_revenue_per_entity = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    avg_compliance_score = models.PositiveIntegerField(default=0)
    avg_collection_rate = models.PositiveIntegerField(default=0)
    avg_utilization = models.PositiveIntegerField(default=0)

    # Percentiles
    p25_revenue_per_client = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    p50_revenue_per_client = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    p75_revenue_per_client = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    p90_revenue_per_client = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    revenue_by_service = models.JSONField(default=dict, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['firm_size', 'firm_type', 'period']
        verbose_name = 'Industry Benchmark'
        verbose_name_plural = 'Industry Benchmarks'

    def __str__(self):
        return f"Benchmark: {self.get_firm_type_display()} — {self.get_firm_size_display()}"


class KPI(models.Model):
    """A key performance indicator tracked by a firm."""
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='kpis')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=30, default='revenue', choices=[
        ('revenue', 'Revenue'), ('clients', 'Clients'), ('compliance', 'Compliance'),
        ('operations', 'Operations'), ('staff', 'Staff'), ('custom', 'Custom'),
    ])
    target_value = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    current_value = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    unit = models.CharField(max_length=20, default='$', choices=[
        ('$', '$'), ('%', '%'), ('#', '#'), ('hrs', 'Hours'),
    ])
    period = models.CharField(max_length=10, default='monthly', choices=[
        ('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('annual', 'Annual'),
    ])
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=7, default='#2563eb')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'category']
        verbose_name = 'KPI'
        verbose_name_plural = 'KPIs'

    def __str__(self):
        return f"{self.name} — {self.firm.name}"

    @property
    def progress_pct(self):
        if float(self.target_value) == 0:
            return 100
        return min(100, int((float(self.current_value) / float(self.target_value)) * 100))

    @property
    def is_on_track(self):
        return self.progress_pct >= 70
