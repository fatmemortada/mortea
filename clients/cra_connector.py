"""
CRA / Revenu Québec Connector Framework.

Tracks and syncs government account balances:
  - GST/HST balance
  - Payroll (source deduction) balance
  - Corporate tax balance and installment status
  - QST balance (Québec)

Infrastructure is ready for API integration when available.
Currently uses manual entry with auto-reminders to update.
"""
from django.db import models
from django.utils import timezone
from .models.client import Client, Firm


class CRAAccount(models.Model):
    """A CRA or Revenu Québec account linked to a client."""

    ACCOUNT_TYPES = [
        ('gst_hst', 'GST/HST Account'),
        ('payroll', 'Payroll / Source Deductions'),
        ('corporate_tax', 'Corporate Tax Account'),
        ('qst', 'QST Account (Revenu Québec)'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='cra_accounts')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='cra_accounts')
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    account_number = models.CharField(max_length=30, blank=True, help_text='CRA business number + account suffix')

    # Latest known balances
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                          help_text='Positive = owing, negative = credit')
    last_known_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_as_of = models.DateField(null=True, blank=True)

    # Filing status
    next_filing_due = models.DateField(null=True, blank=True)
    last_filed_date = models.DateField(null=True, blank=True)
    filing_status = models.CharField(max_length=20, default='unknown', choices=[
        ('unknown', 'Unknown'),
        ('up_to_date', 'Up to Date'),
        ('due_soon', 'Due Soon'),
        ('overdue', 'Overdue'),
        ('filed', 'Filed'),
    ])

    # Installment status
    installments_required = models.BooleanField(default=False)
    next_installment_date = models.DateField(null=True, blank=True)
    next_installment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Sync
    last_synced = models.DateTimeField(null=True, blank=True)
    sync_method = models.CharField(max_length=20, default='manual', choices=[
        ('manual', 'Manual Entry'),
        ('api', 'CRA API'),
        ('estimated', 'Estimated from filings'),
    ])

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['client', 'account_type']
        ordering = ['account_type']

    def __str__(self):
        return f'{self.client.name} — {self.get_account_type_display()}'

    @property
    def is_overdue(self):
        if self.current_balance > 0 and self.balance_as_of:
            return (timezone.now().date() - self.balance_as_of).days > 0
        return False

    @property
    def requires_attention(self):
        return self.is_overdue or self.filing_status in ['overdue', 'due_soon']


def get_or_create_cra_accounts(client, firm):
    """Ensure all 4 CRA/RQ account types exist for a client."""
    accounts = []
    for acct_type, _ in CRAAccount.ACCOUNT_TYPES:
        account, _ = CRAAccount.objects.get_or_create(
            client=client,
            account_type=acct_type,
            defaults={'firm': firm, 'sync_method': 'estimated'},
        )
        accounts.append(account)
    return accounts


def estimate_balances_from_filings(client):
    """
    Estimate CRA account balances from Mortacc filing data.
    Updates CRAAccount records with best available estimates.

    This would be replaced by actual CRA API calls when available.
    """
    from .models import T2Return, BookkeepingTask, Invoice
    from datetime import date

    today = date.today()
    updated = []

    accounts = {a.account_type: a for a in CRAAccount.objects.filter(client=client)}

    # ── Corporate Tax ──────────────────────────────────────────────
    ct = accounts.get('corporate_tax')
    if ct:
        t2 = T2Return.objects.filter(client=client).order_by('-tax_year').first()
        if t2 and t2.status not in ['filed', 'accepted']:
            ct.current_balance = t2.net_tax_owing or 0
            ct.balance_as_of = today
            ct.filing_status = 'overdue' if t2.fiscal_year_end and (today - t2.fiscal_year_end).days > 180 else 'due_soon'
            ct.next_filing_due = (t2.fiscal_year_end + timezone.timedelta(days=180)) if t2.fiscal_year_end else None
            if float(t2.net_tax_owing or 0) > 3000:
                ct.installments_required = True
                ct.next_installment_date = today.replace(day=15)
            ct.sync_method = 'estimated'
            ct.last_synced = timezone.now()
            ct.save()
            updated.append('corporate_tax')

    # ── GST/HST ────────────────────────────────────────────────────
    gst = accounts.get('gst_hst')
    if gst:
        bk = BookkeepingTask.objects.filter(client=client).order_by('-year', '-id').first()
        if bk:
            gst.balance_as_of = today
            gst.last_filed_date = today.replace(day=1) if bk.hst_status == 'filed' else None
            gst.filing_status = 'filed' if bk.hst_status == 'filed' else ('overdue' if bk.hst_status == 'pending' else 'unknown')
            gst.sync_method = 'estimated'
            gst.last_synced = timezone.now()
            gst.save()
            updated.append('gst_hst')

    # ── Payroll ────────────────────────────────────────────────────
    payroll = accounts.get('payroll')
    if payroll:
        payroll.balance_as_of = today
        payroll.sync_method = 'estimated'
        payroll.last_synced = timezone.now()
        payroll.save()
        updated.append('payroll')

    # ── QST (Québec only) ──────────────────────────────────────────
    qst = accounts.get('qst')
    if qst:
        cp = getattr(client, 'corporate_profile', None)
        if cp and cp.jurisdiction == 'quebec':
            qst.balance_as_of = today
            qst.sync_method = 'estimated'
            qst.last_synced = timezone.now()
            qst.save()
            updated.append('qst')

    return updated


def sync_all_firm_accounts(firm):
    """Sync CRA/RQ account estimates for all entities in a firm."""
    from .models import Client

    clients = Client.objects.filter(firm=firm)
    total_updated = 0

    for client in clients:
        get_or_create_cra_accounts(client, firm)
        updated = estimate_balances_from_filings(client)
        total_updated += len(updated)

    return {
        'entities_checked': clients.count(),
        'accounts_updated': total_updated,
        'synced_at': timezone.now().isoformat(),
    }


def get_firm_cra_summary(firm):
    """Get a summary of all CRA/RQ balances across the firm."""
    accounts = CRAAccount.objects.filter(firm=firm).select_related('client')

    summary = {
        'total_owing': sum(float(a.current_balance) for a in accounts if float(a.current_balance) > 0),
        'total_credit': sum(abs(float(a.current_balance)) for a in accounts if float(a.current_balance) < 0),
        'overdue_count': sum(1 for a in accounts if a.filing_status == 'overdue'),
        'due_soon_count': sum(1 for a in accounts if a.filing_status == 'due_soon'),
        'installment_entities': sum(1 for a in accounts if a.installments_required),
        'accounts': [],
    }

    for a in accounts.order_by('client__name', 'account_type'):
        summary['accounts'].append({
            'client_name': a.client.name,
            'client_id': a.client.id,
            'account_type': a.get_account_type_display(),
            'balance': float(a.current_balance),
            'status': a.filing_status,
            'next_due': a.next_filing_due.isoformat() if a.next_filing_due else None,
            'installments': a.installments_required,
            'needs_attention': a.requires_attention,
        })

    return summary
