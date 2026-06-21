"""Trust Accounting views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
from django.db.models import Sum

from ..models import (
    Client, TrustAccount, TrustTransaction, TrustReconciliation,
    TrustClientLedger, Invoice, log_activity,
)
from ._helpers import _get_firm


@login_required
def trust_dashboard(request):
    """Trust accounting dashboard."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    accounts = TrustAccount.objects.filter(firm=firm, is_active=True)
    total_trust = sum(float(a.current_balance) for a in accounts)
    total_reconciled = sum(float(a.reconciled_balance) for a in accounts)

    # Recent transactions
    recent_txns = TrustTransaction.objects.filter(
        account__firm=firm
    ).select_related('account', 'client').order_by('-transaction_date')[:30]

    # Pending reconciliations
    pending_recons = TrustReconciliation.objects.filter(
        account__firm=firm, status='in_progress'
    ).select_related('account').order_by('-created_at')

    # Client balances
    client_ledgers = TrustClientLedger.objects.filter(
        account__firm=firm
    ).select_related('client', 'account').order_by('-current_balance')

    # Clients with trust funds
    clients_with_trust = Client.objects.filter(
        firm=firm, trust_ledger_entries__isnull=False
    ).distinct()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_account':
            name = request.POST.get('name', '').strip()
            acc_type = request.POST.get('account_type', 'general')
            if name:
                TrustAccount.objects.create(firm=firm, name=name, account_type=acc_type)
                messages.success(request, f'Trust account "{name}" created.')

        elif action == 'record_transaction':
            account_id = request.POST.get('account_id')
            client_id = request.POST.get('client_id')
            txn_type = request.POST.get('transaction_type')
            amount = request.POST.get('amount', 0)
            description = request.POST.get('description', '').strip()
            ref = request.POST.get('reference_number', '').strip()
            txn_date = request.POST.get('transaction_date', str(date.today()))

            account = get_object_or_404(TrustAccount, id=account_id, firm=firm)
            client = get_object_or_404(Client, id=client_id, firm=firm)

            txn = TrustTransaction.objects.create(
                account=account, client=client, transaction_type=txn_type,
                amount=amount, description=description, reference_number=ref,
                transaction_date=txn_date, status='cleared', created_by=request.user,
            )

            # Update client ledger
            ledger, _ = TrustClientLedger.objects.get_or_create(
                account=account, client=client,
                defaults={'opening_balance': 0, 'current_balance': 0},
            )
            if txn_type in ('deposit', 'transfer_from_general', 'interest'):
                ledger.current_balance = float(ledger.current_balance) + float(amount)
                ledger.total_deposits = float(ledger.total_deposits) + float(amount)
            elif txn_type in ('withdrawal', 'transfer_to_general', 'fee'):
                ledger.current_balance = float(ledger.current_balance) - float(amount)
                ledger.total_withdrawals = float(ledger.total_withdrawals) + float(amount)
            ledger.last_activity = timezone.now()
            ledger.save()

            log_activity(client, f'Trust {txn.get_transaction_type_display()}: ${float(amount):,.2f}', request.user)
            messages.success(request, f'Transaction recorded: {txn.get_transaction_type_display()} ${float(amount):,.2f}')

        elif action == 'transfer_to_general':
            client_id = request.POST.get('client_id')
            invoice_id = request.POST.get('invoice_id')
            amount = request.POST.get('amount', 0)
            account_id = request.POST.get('account_id')

            account = get_object_or_404(TrustAccount, id=account_id, firm=firm)
            client = get_object_or_404(Client, id=client_id, firm=firm)
            invoice = Invoice.objects.filter(id=invoice_id, client=client).first()

            # Record trust withdrawal
            txn = TrustTransaction.objects.create(
                account=account, client=client,
                transaction_type='transfer_to_general',
                amount=amount, description=f'Transfer to general for invoice {invoice.invoice_number if invoice else ""}',
                transaction_date=date.today(), status='cleared',
                related_invoice=invoice, created_by=request.user,
            )

            # Update ledger
            ledger = TrustClientLedger.objects.get(account=account, client=client)
            ledger.current_balance = float(ledger.current_balance) - float(amount)
            ledger.total_withdrawals = float(ledger.total_withdrawals) + float(amount)
            ledger.last_activity = timezone.now()
            ledger.save()

            # Mark invoice as paid
            if invoice:
                invoice.mark_paid()

            log_activity(client, f'Trust transfer to general: ${float(amount):,.2f} for invoice {invoice.invoice_number if invoice else ""}', request.user)
            messages.success(request, f'Transferred ${float(amount):,.2f} from trust to general.')

        elif action == 'start_reconciliation':
            account_id = request.POST.get('account_id')
            account = get_object_or_404(TrustAccount, id=account_id, firm=firm)
            period_end = request.POST.get('period_end', str(date.today()))
            period_start = request.POST.get('period_start', str(date.today().replace(day=1)))

            recon = TrustReconciliation.objects.create(
                account=account, prepared_by=request.user,
                period_start=period_start, period_end=period_end,
                book_balance=account.current_balance,
                bank_balance=float(request.POST.get('bank_balance', 0)),
                outstanding_deposits=float(request.POST.get('outstanding_deposits', 0)),
                outstanding_checks=float(request.POST.get('outstanding_checks', 0)),
            )
            recon.reconciled_balance = float(recon.bank_balance) + float(recon.outstanding_deposits) - float(recon.outstanding_checks)
            recon.difference = float(recon.book_balance) - float(recon.reconciled_balance)

            # Calculate total client balances
            total = TrustClientLedger.objects.filter(account=account).aggregate(
                t=Sum('current_balance')
            )['t'] or 0
            recon.total_client_balances = total
            recon.client_balance_matches = abs(float(account.current_balance) - float(total)) < 0.01
            recon.status = 'completed'
            recon.completed_at = timezone.now()
            recon.save()

            account.reconciled_balance = recon.reconciled_balance
            account.last_reconciled_at = timezone.now()
            account.last_reconciliation_date = period_end
            account.save()

            log_activity(None, f'Trust reconciliation completed: {account.name} — ${float(recon.difference):,.2f} difference', request.user)
            messages.success(request, f'Reconciliation complete. Difference: ${float(recon.difference):,.2f}')

        elif action == 'mark_reconciled':
            txn_id = request.POST.get('transaction_id')
            txn = get_object_or_404(TrustTransaction, id=txn_id, account__firm=firm)
            txn.status = 'reconciled'
            txn.save()

        return redirect('trust_dashboard')

    return render(request, 'clients/trust_dashboard.html', {
        'firm': firm, 'accounts': accounts,
        'total_trust': total_trust, 'total_reconciled': total_reconciled,
        'recent_txns': recent_txns, 'pending_recons': pending_recons,
        'client_ledgers': client_ledgers, 'clients_with_trust': clients_with_trust,
        'clients': Client.objects.filter(firm=firm),
        'invoices': Invoice.objects.filter(client__firm=firm, status__in=['sent', 'overdue']),
        'today': date.today(),
    })
