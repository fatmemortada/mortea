"""Dividend Resolution + T5 Generator views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date, timedelta

from ..models import (
    Client, Shareholder, DividendDeclaration, DividendRecipient,
    DividendHistory, Invoice, log_activity,
)
from ._helpers import _get_firm


@login_required
def dividend_dashboard(request, client_id=None):
    """View dividend declarations for a client or all clients."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)
        declarations = DividendDeclaration.objects.filter(client=client).prefetch_related('recipients').order_by('-declaration_date')
    else:
        client = None
        declarations = DividendDeclaration.objects.filter(client__firm=firm).select_related('client').prefetch_related('recipients').order_by('-declaration_date')

    total_declared = sum(float(d.total_amount) for d in declarations)
    total_paid = sum(float(d.total_amount) for d in declarations if d.status == 'paid')

    return render(request, 'clients/dividend_dashboard.html', {
        'firm': firm, 'client': client, 'declarations': declarations,
        'total_declared': total_declared, 'total_paid': total_paid,
    })


@login_required
def dividend_create(request, client_id):
    """Create a new dividend declaration."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    shareholders = Shareholder.objects.filter(client=client)
    today = date.today()

    if request.method == 'POST':
        dividend_type = request.POST.get('dividend_type', 'non_eligible')
        total_amount = request.POST.get('total_amount', 0)
        declaration_date = request.POST.get('declaration_date', str(today))
        fiscal_year = request.POST.get('fiscal_year', today.year)

        declaration = DividendDeclaration.objects.create(
            client=client, declared_by=request.user,
            dividend_type=dividend_type,
            total_amount=total_amount,
            declaration_date=declaration_date,
            fiscal_year=fiscal_year,
            tax_year=fiscal_year,
        )

        # Create recipients from shareholder list
        for s in shareholders:
            if s.num_shares <= 0:
                continue
            # Calculate proportional share
            total_shares = sum(sh.num_shares for sh in shareholders)
            proportion = s.num_shares / max(total_shares, 1)
            gross = float(total_amount) * proportion

            # Determine eligible vs non-eligible split
            if dividend_type == 'eligible':
                eligible = gross
                non_eligible = 0
            elif dividend_type == 'capital':
                eligible = 0
                non_eligible = 0
                capital = gross
            else:
                eligible = 0
                non_eligible = gross
                capital = 0

            DividendRecipient.objects.create(
                declaration=declaration,
                shareholder_name=s.full_name,
                shareholder_address=s.address,
                gross_amount=gross,
                shares_owned=s.num_shares,
                dividend_per_share=float(total_amount) / max(total_shares, 1) if total_shares > 0 else 0,
                eligible_dividend_amount=eligible,
                non_eligible_dividend_amount=non_eligible,
                capital_dividend_amount=capital if dividend_type == 'capital' else 0,
            )

        # Generate invoice for dividend resolution service
        invoice = Invoice.objects.create(
            client=client,
            description=f'Dividend Resolution Package — ${float(total_amount):,.2f} {declaration.get_dividend_type_display()}',
            service_type='other',
            amount=299,  # Fixed fee for dividend resolution service
            status='sent',
            invoice_date=today,
            due_date=today + timedelta(days=30),
        )

        declaration.resolution_generated = True
        declaration.save()

        log_activity(client, f'Dividend declared: ${float(total_amount):,.2f} ({dividend_type})', request.user)
        messages.success(request, f'Dividend of ${float(total_amount):,.2f} declared for {client.name}!')

        return redirect('dividend_detail', declaration_id=declaration.id)

    return render(request, 'clients/dividend_create.html', {
        'firm': firm, 'client': client, 'shareholders': shareholders, 'today': today,
    })


@login_required
def dividend_detail(request, declaration_id):
    """View dividend declaration details and manage recipients."""
    firm = _get_firm(request.user)
    declaration = get_object_or_404(
        DividendDeclaration.objects.select_related('client').prefetch_related('recipients'),
        id=declaration_id, client__firm=firm
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'mark_paid':
            declaration.mark_paid()
            # Update dividend history
            for recipient in declaration.recipients.all():
                hist, _ = DividendHistory.objects.get_or_create(
                    client=declaration.client,
                    shareholder_name=recipient.shareholder_name,
                    fiscal_year=declaration.fiscal_year or date.today().year,
                    defaults={'total_dividends': 0, 'eligible_dividends': 0,
                              'non_eligible_dividends': 0, 'capital_dividends': 0},
                )
                hist.total_dividends = float(hist.total_dividends) + float(recipient.gross_amount)
                hist.eligible_dividends = float(hist.eligible_dividends) + float(recipient.eligible_dividend_amount or 0)
                hist.non_eligible_dividends = float(hist.non_eligible_dividends) + float(recipient.non_eligible_dividend_amount or 0)
                hist.capital_dividends = float(hist.capital_dividends) + float(recipient.capital_dividend_amount or 0)
                hist.save()
            log_activity(declaration.client, f'Dividend marked as paid: ${float(declaration.total_amount):,.2f}', request.user)
            messages.success(request, 'Dividend marked as paid and history updated.')

        elif action == 'add_recipient':
            DividendRecipient.objects.create(
                declaration=declaration,
                shareholder_name=request.POST.get('shareholder_name', ''),
                gross_amount=float(request.POST.get('gross_amount', 0)),
                eligible_dividend_amount=float(request.POST.get('eligible_amount', 0)),
                non_eligible_dividend_amount=float(request.POST.get('non_eligible_amount', 0)),
            )

        return redirect('dividend_detail', declaration_id=declaration.id)

    # T5 summary data
    total_t5_eligible = sum(float(r.eligible_dividend_amount or 0) for r in declaration.recipients.all())
    total_t5_non_eligible = sum(float(r.non_eligible_dividend_amount or 0) for r in declaration.recipients.all())
    total_t5_capital = sum(float(r.capital_dividend_amount or 0) for r in declaration.recipients.all())

    return render(request, 'clients/dividend_detail.html', {
        'firm': firm, 'declaration': declaration,
        'total_t5_eligible': total_t5_eligible,
        'total_t5_non_eligible': total_t5_non_eligible,
        'total_t5_capital': total_t5_capital,
    })


@login_required
def dividend_history_view(request, client_id=None):
    """View dividend history per entity or firm-wide."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)
        history = DividendHistory.objects.filter(client=client).order_by('-fiscal_year', 'shareholder_name')
    else:
        client = None
        history = DividendHistory.objects.filter(client__firm=firm).select_related('client').order_by('-fiscal_year', 'shareholder_name')

    # Summaries by year
    by_year = {}
    for h in history:
        yr = h.fiscal_year
        if yr not in by_year:
            by_year[yr] = {'total': 0, 'eligible': 0, 'non_eligible': 0, 'capital': 0, 'count': 0}
        by_year[yr]['total'] += float(h.total_dividends)
        by_year[yr]['eligible'] += float(h.eligible_dividends)
        by_year[yr]['non_eligible'] += float(h.non_eligible_dividends)
        by_year[yr]['capital'] += float(h.capital_dividends)
        by_year[yr]['count'] += 1

    return render(request, 'clients/dividend_history.html', {
        'firm': firm, 'client': client, 'history': history, 'by_year': by_year,
    })
