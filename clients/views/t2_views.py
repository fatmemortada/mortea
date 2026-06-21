"""T2 Corporate Tax Return — Complete filing system views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from datetime import date, timedelta

from ..models import Client, T2Return, Invoice, log_activity
from ._helpers import _get_firm


@login_required
def t2_dashboard(request):
    """T2 Filing Dashboard — status overview for all entities."""
    firm = _get_firm(request.user)
    if not firm: return redirect('login')

    clients = Client.objects.filter(firm=firm)
    today = date.today()

    # Get or prepare T2 returns for current and prior year
    t2_returns = T2Return.objects.filter(firm=firm).select_related('client').order_by('-tax_year', 'client__name')

    # Stats
    total = t2_returns.count()
    filed = t2_returns.filter(status__in=['filed','accepted']).count()
    in_progress = t2_returns.filter(status__in=['preparing','review','client_approval','ready_to_file']).count()
    not_started = t2_returns.filter(status='not_started').count()
    total_tax = t2_returns.filter(status__in=['filed','accepted']).aggregate(t=Sum('net_tax_owing'))['t'] or 0

    return render(request, 'clients/t2_dashboard.html', {
        'firm': firm, 'clients': clients, 't2_returns': t2_returns,
        'total': total, 'filed': filed, 'in_progress': in_progress,
        'not_started': not_started, 'total_tax': float(total_tax),
        'current_year': today.year,
    })


@login_required
def t2_prepare(request, client_id=None):
    """Prepare a T2 return for a specific entity — pre-fill with entity data."""
    firm = _get_firm(request.user)
    if not firm: return redirect('login')

    clients = Client.objects.filter(firm=firm)
    t2 = None
    prior_t2 = None

    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)
        today = date.today()
        tax_year = int(request.GET.get('year', today.year - 1))
        fy_end = date(tax_year, 12, 31)
        fy_start = date(tax_year, 1, 1)

        # Get or create T2
        t2, created = T2Return.objects.get_or_create(
            client=client, tax_year=tax_year,
            defaults={
                'firm': firm, 'created_by': request.user,
                'fiscal_year_start': fy_start,
                'fiscal_year_end': fy_end,
                'status': 'preparing',
                'sbd_eligible_income': 500000,
            }
        )
        if created:
            # Pre-fill from entity data
            t2.prefill_from_entity_data()
            log_activity(request.user, 'create', 'T2Return', t2.id, str(t2),
                         f'T2 {tax_year} created for {client.name}', firm=firm)

        # Prior year
        prior_t2 = T2Return.objects.filter(client=client, tax_year=tax_year - 1).first()

        # Check for invoices to pre-fill revenue
        inv_total = Invoice.objects.filter(
            client=client, status='paid',
            invoice_date__gte=fy_start, invoice_date__lte=fy_end
        ).aggregate(t=Sum('total_amount'))['t'] or 0
        if float(t2.total_revenue) == 0 and float(inv_total) > 0:
            t2.active_business_revenue = inv_total
            t2.save()

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, id=client_id, firm=firm)
        tax_year = int(request.POST.get('tax_year', today.year - 1))

        t2, created = T2Return.objects.get_or_create(
            client=client, tax_year=tax_year,
            defaults={'firm': firm, 'created_by': request.user,
                      'fiscal_year_start': date(tax_year, 1, 1),
                      'fiscal_year_end': date(tax_year, 12, 31)}
        )

        # Update all fields from POST
        fields = [
            'net_income_per_books', 'active_business_revenue', 'investment_income', 'capital_gains',
            'salaries_wages', 'rent', 'professional_fees', 'office_expenses', 'insurance',
            'advertising', 'interest_expense', 'other_expenses',
            'depreciation_addback', 'meals_entertainment_addback', 'golf_club_addback',
            'penalties_addback', 'life_insurance_addback', 'political_donations_addback', 'other_addbacks',
            'cca_class_1', 'cca_class_8', 'cca_class_10', 'cca_class_50', 'cca_class_14',
            'capital_gains_deduction', 'other_deductions',
            'dividend_tax_credit', 'foreign_tax_credit', 'investment_tax_credit',
            'sbd_eligible_income',
        ]
        for field in fields:
            val = request.POST.get(field, '')
            if val:
                try:
                    setattr(t2, field, float(val))
                except (ValueError, TypeError):
                    pass

        t2.status = request.POST.get('status', 'preparing')
        t2.notes = request.POST.get('notes', '')
        t2.save()  # save() triggers calculate_tax()

        log_activity(request.user, 'update', 'T2Return', t2.id, str(t2),
                     f'T2 {tax_year} updated for {client.name}', firm=firm)

        messages.success(request, f'T2 {tax_year} updated. Tax calculated: ${float(t2.net_tax_owing):,.2f} owing.')
        return redirect('t2_prepare_client', client_id=client.id)

    return render(request, 'clients/t2_prepare.html', {
        'firm': firm, 'clients': clients, 't2': t2, 'prior_t2': prior_t2,
        'client': Client.objects.filter(id=client_id, firm=firm).first() if client_id else None,
    })


@login_required
def t2_auto_prepare(request, client_id):
    """One-click deep auto-prepare — fills every T2 field from all available data sources."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    from datetime import date

    client = get_object_or_404(Client, id=client_id, firm=firm)
    today = date.today()
    tax_year = int(request.GET.get('year', today.year - 1))

    # Get or create T2
    t2, created = T2Return.objects.get_or_create(
        client=client, tax_year=tax_year,
        defaults={
            'firm': firm, 'created_by': request.user,
            'fiscal_year_start': date(tax_year, 1, 1),
            'fiscal_year_end': date(tax_year, 12, 31),
            'status': 'preparing',
            'sbd_eligible_income': 500000,
        }
    )

    # Run deep prefill
    report = t2.deep_prefill()

    # Build detailed success message
    filled_count = len(report['filled'])
    estimated_count = len(report['estimated'])
    missing_count = len(report['missing'])

    messages.success(request,
        f'⚡ T2 {tax_year} auto-prepared for {client.name}! '
        f'Score: {report["score"]}% · '
        f'{filled_count} data sources used, {estimated_count} estimated, {missing_count} gaps.'
    )

    if report['missing']:
        for m in report['missing'][:2]:
            messages.warning(request, f'⚠ {m}')

    log_activity(request.user, 'update', 'T2Return', t2.id, str(t2),
                 f'T2 {tax_year} auto-prepared — score {report["score"]}%', firm=firm)

    return redirect('t2_prepare_client', client_id=client.id)
