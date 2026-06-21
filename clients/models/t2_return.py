"""
T2 Corporate Tax Return — Complete filing system.
Stores all schedule data, calculates tax, tracks filing status.
"""
from django.db import models
from django.contrib.auth.models import User
from .client import Firm, Client


class T2Return(models.Model):
    """A T2 Corporate Tax Return for one entity and tax year."""
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('preparing', 'Preparing'),
        ('review', 'Under Review'),
        ('client_approval', 'Awaiting Client Approval'),
        ('ready_to_file', 'Ready to File'),
        ('filed', 'Filed with CRA'),
        ('accepted', 'Accepted by CRA'),
        ('rejected', 'Rejected / Needs Revision'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='t2_returns')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='t2_returns')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='prepared_t2_returns')

    tax_year = models.PositiveIntegerField(help_text='Tax year (e.g. 2025 for the 2025 tax year)')
    fiscal_year_start = models.DateField()
    fiscal_year_end = models.DateField()

    # ── Schedule 1 — Net Income Reconciliation ─────────────────────────
    net_income_per_books = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # Add-backs (non-deductible expenses)
    depreciation_addback = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    meals_entertainment_addback = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    golf_club_addback = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    penalties_addback = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    life_insurance_addback = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    political_donations_addback = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_addbacks = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Deductions
    cca_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    capital_gains_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Result
    net_income_for_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # ── Schedule 8 — Capital Cost Allowance ────────────────────────────
    cca_class_1 = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Buildings (4% declining)')
    cca_class_8 = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Furniture & Equipment (20%)')
    cca_class_10 = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Vehicles (30%)')
    cca_class_50 = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Computers (55%)')
    cca_class_14 = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Intangible assets')
    total_cca_claimed = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ── Revenue Breakdown ──────────────────────────────────────────────
    active_business_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    investment_income = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    capital_gains = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # ── Expenses ───────────────────────────────────────────────────────
    salaries_wages = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    professional_fees = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    office_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advertising = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest_expense = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_expenses = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # ── Tax Calculation ────────────────────────────────────────────────
    taxable_income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sbd_eligible_income = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Income eligible for Small Business Deduction')
    sbd_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0900, help_text='SBD rate (9% federal for 2025+)')
    general_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.1500, help_text='General corporate rate (15% federal)')
    federal_tax_part1 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    provincial_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Credits
    dividend_tax_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    foreign_tax_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    investment_tax_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_credits = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_tax_owing = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ── Filing ─────────────────────────────────────────────────────────
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    prepared_by = models.CharField(max_length=255, blank=True)
    reviewed_by = models.CharField(max_length=255, blank=True)
    filing_method = models.CharField(max_length=20, default='efile', choices=[('efile','CRA E-File'),('netfile','NetFile'),('paper','Paper')])
    cra_confirmation = models.CharField(max_length=50, blank=True, help_text='CRA confirmation number')
    filed_date = models.DateField(null=True, blank=True)
    accepted_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tax_year', '-created_at']
        unique_together = [('client', 'tax_year')]
        indexes = [
            models.Index(fields=['firm', '-tax_year']),
            models.Index(fields=['client', '-tax_year']),
            models.Index(fields=['status']),
        ]

    def calculate_tax(self):
        """Calculate all tax fields based on entered data."""
        # Total addbacks
        total_addbacks = (
            self.depreciation_addback + self.meals_entertainment_addback +
            self.golf_club_addback + self.penalties_addback +
            self.life_insurance_addback + self.political_donations_addback +
            self.other_addbacks
        )
        # Total deductions
        total_deductions = self.cca_deduction + self.capital_gains_deduction + self.other_deductions

        # Net income for tax
        self.net_income_for_tax = self.net_income_per_books + total_addbacks - total_deductions

        # Total revenue & expenses
        self.total_revenue = self.active_business_revenue + self.investment_income + self.capital_gains
        self.total_expenses = sum([
            self.salaries_wages, self.rent, self.professional_fees,
            self.office_expenses, self.insurance, self.advertising,
            self.interest_expense, self.other_expenses
        ])

        # Taxable income
        self.taxable_income = max(0, self.net_income_for_tax)

        # Federal tax — SBD portion vs general
        sbd_income = min(self.taxable_income, self.sbd_eligible_income)
        general_income = max(0, self.taxable_income - sbd_income)
        self.federal_tax_part1 = (float(sbd_income) * float(self.sbd_rate) +
                                   float(general_income) * float(self.general_rate))

        # Provincial tax (simplified — using Ontario 3.2% SBD, 11.5% general)
        prov_sbd_rate = 0.032
        prov_general_rate = 0.115
        self.provincial_tax = (float(sbd_income) * prov_sbd_rate +
                                float(general_income) * prov_general_rate)

        # Total
        self.total_tax = self.federal_tax_part1 + self.provincial_tax
        self.total_credits = self.dividend_tax_credit + self.foreign_tax_credit + self.investment_tax_credit
        self.net_tax_owing = max(0, self.total_tax - self.total_credits)

        self.total_cca_claimed = sum([
            self.cca_class_1, self.cca_class_8, self.cca_class_10,
            self.cca_class_50, self.cca_class_14
        ])
        self.cca_deduction = self.total_cca_claimed

    def save(self, *args, **kwargs):
        if not self.fiscal_year_end:
            from datetime import date
            self.fiscal_year_end = date(self.tax_year, 12, 31)
        if not self.fiscal_year_start:
            from datetime import date
            self.fiscal_year_start = date(self.tax_year, 1, 1)
        self.calculate_tax()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"T2 {self.tax_year} — {self.client.name} ({self.get_status_display()})"

    @property
    def effective_tax_rate(self):
        if float(self.taxable_income) > 0:
            return round(float(self.total_tax) / float(self.taxable_income) * 100, 1)
        return 0

    @property
    def progress_pct(self):
        stages = ['not_started','preparing','review','client_approval','ready_to_file','filed','accepted']
        try:
            idx = stages.index(self.status)
            return int((idx + 1) / len(stages) * 100)
        except ValueError:
            return 0

    def prefill_from_entity_data(self):
        """Pre-fill T2 with available entity data. Called from both views and scheduler."""
        from .billing import Invoice
        from django.db.models import Sum

        client = self.client

        # Revenue from paid invoices
        inv = Invoice.objects.filter(client=client, status='paid').aggregate(t=Sum('total_amount'))['t'] or 0
        if inv > 0:
            self.active_business_revenue = inv

        # Check prior year for common expenses
        prior = T2Return.objects.filter(client=client, tax_year=self.tax_year - 1).first()
        if prior:
            self.net_income_per_books = prior.net_income_per_books
            self.salaries_wages = prior.salaries_wages
            self.rent = prior.rent
            self.office_expenses = prior.office_expenses

        self.status = 'preparing'
        self.save()

    def deep_prefill(self):
        """
        Comprehensive auto-prepare using ALL available data sources.
        Returns dict with details of what was filled and a completeness score.
        """
        from .billing import Invoice
        from .bookkeeping import BookkeepingTask
        from django.db.models import Sum
        from datetime import date

        client = self.client
        today = date.today()
        report = {'filled': [], 'estimated': [], 'missing': [], 'score': 0}

        # ── 1. Revenue from paid invoices in the fiscal year ──────────
        fy_invoices = Invoice.objects.filter(
            client=client,
            status='paid',
            paid_date__gte=self.fiscal_year_start,
            paid_date__lte=self.fiscal_year_end,
        )
        fy_revenue = fy_invoices.aggregate(t=Sum('total_amount'))['t'] or 0
        if float(fy_revenue) > 0:
            self.active_business_revenue = fy_revenue
            self.total_revenue = fy_revenue
            report['filled'].append(f'Revenue: ${float(fy_revenue):,.2f} from {fy_invoices.count()} paid invoices')
        else:
            # Fall back to all paid invoices
            all_inv = Invoice.objects.filter(client=client, status='paid').aggregate(t=Sum('total_amount'))['t'] or 0
            if float(all_inv) > 0:
                self.active_business_revenue = all_inv
                self.total_revenue = all_inv
                report['estimated'].append(f'Revenue (all-time): ${float(all_inv):,.2f} — refine to fiscal year')

        # ── 2. Prior-year carry-forward ──────────────────────────────
        prior = T2Return.objects.filter(client=client, tax_year=self.tax_year - 1).first()
        if prior:
            carried = []
            for field in ['net_income_per_books', 'salaries_wages', 'rent', 'professional_fees',
                         'office_expenses', 'insurance', 'advertising', 'interest_expense',
                         'depreciation_addback', 'meals_entertainment_addback', 'other_addbacks',
                         'cca_class_1', 'cca_class_8', 'cca_class_10', 'cca_class_50', 'cca_class_14',
                         'investment_income', 'capital_gains', 'dividend_tax_credit',
                         'foreign_tax_credit', 'investment_tax_credit']:
                prior_val = float(getattr(prior, field) or 0)
                if prior_val > 0:
                    setattr(self, field, prior_val)
                    carried.append(field.replace('_', ' ').title())
            if carried:
                report['estimated'].append(f'Prior-year carry: {len(carried)} fields')
            self.net_income_per_books = prior.net_income_per_books
            self.sbd_eligible_income = prior.sbd_eligible_income
        else:
            report['missing'].append('No prior-year T2 — all fields need manual entry')
            # Default SBD to active business revenue (common for small biz)
            if float(self.active_business_revenue) > 0:
                self.sbd_eligible_income = min(float(self.active_business_revenue), 500000)

        # ── 3. Bookkeeping data ──────────────────────────────────────
        fy_year = self.fiscal_year_end.year
        bk_tasks = BookkeepingTask.objects.filter(
            client=client,
            year=fy_year,
        )
        bk_count = bk_tasks.count()
        if bk_count > 0:
            report['filled'].append(f'Bookkeeping: {bk_count} monthly task(s) linked')
            # If bookkeeping is completed, estimate expenses proportionally
            completed_bk = bk_tasks.filter(status='completed').count()
            if completed_bk > 0 and float(self.active_business_revenue) > 0:
                # Use a rough 60% expense ratio as baseline for small businesses
                est_expenses = float(self.active_business_revenue) * 0.60
                if float(self.total_expenses) == 0:
                    self.total_expenses = est_expenses
                    report['estimated'].append(f'Expenses estimated at 60% of revenue: ${est_expenses:,.2f}')
        else:
            report['missing'].append('No bookkeeping tasks — run monthly bookkeeping for better data')

        # ── 4. SBD Eligibility Check ─────────────────────────────────
        # Small Business Deduction: 9% on first $500K active business income
        # Phase-out starts at $10M taxable capital
        if float(self.sbd_eligible_income) == 0 and float(self.active_business_revenue) > 0:
            abr = float(self.active_business_revenue)
            self.sbd_eligible_income = min(abr, 500000)
            report['filled'].append(f'SBD eligible: ${float(self.sbd_eligible_income):,.2f}')
        elif float(self.sbd_eligible_income) > 500000:
            report['estimated'].append('SBD income > $500K — phase-out may apply')

        # ── 5. Corporate structure checks ───────────────────────────
        if hasattr(client, 'corporate_profile') and client.corporate_profile:
            cp = client.corporate_profile
            if cp.jurisdiction:
                report['filled'].append(f'Jurisdiction: {cp.get_jurisdiction_display()}')
            if cp.fiscal_year_end:
                report['filled'].append(f'FYE: {cp.fiscal_year_end}')

        # ── 6. Completeness score ────────────────────────────────────
        total_fields = 30  # approximate number of fillable fields
        filled = len(report['filled']) + len(report['estimated'])
        missing = len(report['missing'])
        report['score'] = min(95, int((filled / max(1, filled + missing)) * 100))

        # ── 7. Status update ─────────────────────────────────────────
        if report['score'] >= 60:
            self.status = 'preparing'
        if report['score'] >= 80:
            self.status = 'review'
        self.notes = (self.notes or '') + f'\n[Auto-prepare {today}] Score: {report["score"]}%'
        self.save()

        return report
