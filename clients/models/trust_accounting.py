"""
Trust Accounting Module.

Full trust ledger, client trust balances, trust-to-general transfers,
three-way reconciliation, law society compliant reporting.
Once adopted, switching cost is existential — zero churn forever.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .client import Client, Firm


class TrustAccount(models.Model):
    """A trust account maintained by a firm for client funds."""
    ACCOUNT_TYPE_CHOICES = [
        ('general', 'General Trust Account'),
        ('separate', 'Separate Interest-Bearing Trust'),
        ('pooled', 'Pooled Trust Account'),
    ]
    CURRENCY_CHOICES = [
        ('CAD', 'Canadian Dollar'),
        ('USD', 'US Dollar'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='trust_accounts')
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='general')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='CAD')

    # Bank details
    bank_name = models.CharField(max_length=255, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_transit_number = models.CharField(max_length=20, blank=True)
    bank_institution_number = models.CharField(max_length=20, blank=True)

    # Balance tracking
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    reconciled_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    last_reconciled_at = models.DateTimeField(null=True, blank=True)
    last_reconciliation_date = models.DateField(null=True, blank=True)

    # Compliance
    is_active = models.BooleanField(default=True)
    minimum_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.0, help_text='Minimum balance to maintain')
    overdraft_protection = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Trust Account'
        verbose_name_plural = 'Trust Accounts'

    def __str__(self):
        return f"{self.name} — {self.firm.name} (${self.current_balance:,.2f})"


class TrustTransaction(models.Model):
    """A single trust transaction — deposit, withdrawal, or transfer."""
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'Deposit — Client Funds Received'),
        ('withdrawal', 'Withdrawal — Payment to Client/Beneficiary'),
        ('transfer_to_general', 'Transfer to General — Invoice Payment'),
        ('transfer_from_general', 'Transfer from General — Replenishment'),
        ('fee', 'Fee Deduction'),
        ('interest', 'Interest Earned'),
        ('adjustment', 'Adjustment / Correction'),
        ('reversal', 'Reversal'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('cleared', 'Cleared'),
        ('reconciled', 'Reconciled'),
        ('void', 'Void'),
    ]

    account = models.ForeignKey(TrustAccount, on_delete=models.CASCADE, related_name='transactions')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='trust_transactions')
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPE_CHOICES)

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='CAD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1.0)

    # References
    reference_number = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    wire_transfer_id = models.CharField(max_length=100, blank=True)

    # Dates
    transaction_date = models.DateField(default=timezone.now)
    value_date = models.DateField(null=True, blank=True)
    cleared_date = models.DateField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Linked entities
    related_invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='trust_transactions')
    related_matter = models.CharField(max_length=255, blank=True)

    # Approval
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_trust_txns')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_trust_txns')
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['account', 'status']),
            models.Index(fields=['client', 'transaction_date']),
            models.Index(fields=['transaction_date', 'status']),
        ]
        verbose_name = 'Trust Transaction'
        verbose_name_plural = 'Trust Transactions'

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Update account balance
        if is_new and self.status in ('cleared', 'reconciled'):
            self._update_balance()

    def _update_balance(self):
        """Update the trust account balance after this transaction."""
        account = self.account
        if self.transaction_type in ('deposit', 'transfer_from_general', 'interest'):
            account.current_balance = float(account.current_balance) + float(self.amount)
        elif self.transaction_type in ('withdrawal', 'transfer_to_general', 'fee'):
            account.current_balance = float(account.current_balance) - float(self.amount)
        # Adjustments can be positive or negative
        elif self.transaction_type == 'adjustment':
            account.current_balance = float(account.current_balance) + float(self.amount)
        elif self.transaction_type == 'reversal':
            account.current_balance = float(account.current_balance) - float(self.amount)
        account.save()

    def __str__(self):
        return f"{self.get_transaction_type_display()} — ${self.amount:,.2f} — {self.client.name}"


class TrustReconciliation(models.Model):
    """A trust account reconciliation record."""
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('reviewed', 'Reviewed'),
    ]

    account = models.ForeignKey(TrustAccount, on_delete=models.CASCADE, related_name='reconciliations')
    prepared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='prepared_recons')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_recons')

    # Period
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')

    # Balances
    book_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    bank_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    outstanding_deposits = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    outstanding_checks = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    reconciled_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    difference = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)

    # Client ledger summary
    total_client_balances = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    client_balance_matches = models.BooleanField(default=False)

    notes = models.TextField(blank=True)
    discrepancies_found = models.TextField(blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-period_end']
        verbose_name = 'Trust Reconciliation'
        verbose_name_plural = 'Trust Reconciliations'

    def __str__(self):
        return f"Reconciliation: {self.account.name} ({self.period_start} → {self.period_end})"

    @property
    def is_balanced(self):
        return abs(float(self.difference or 0)) < 0.01


class TrustClientLedger(models.Model):
    """Per-client trust balance tracking."""
    account = models.ForeignKey(TrustAccount, on_delete=models.CASCADE, related_name='client_ledgers')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='trust_ledger_entries')

    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    total_deposits = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    total_withdrawals = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    last_activity = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['account', 'client']
        ordering = ['client__name']
        verbose_name = 'Trust Client Ledger'
        verbose_name_plural = 'Trust Client Ledgers'

    def __str__(self):
        return f"{self.client.name} — ${self.current_balance:,.2f} in {self.account.name}"
