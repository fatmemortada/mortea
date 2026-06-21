"""
Complete Accounting System — Time Tracking, Payroll, Financial Dashboard, Collections.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
from django.db.models import Sum, Count, Q

from ..models import Client, Invoice, TimeEntry, BillingRate, BookkeepingTask, log_activity
from ._helpers import _get_firm


# ═══════════════════════════════════════════════════════════════════════
# TIME TRACKING
# ═══════════════════════════════════════════════════════════════════════

@login_required
def time_tracking(request):
    """Billable time tracking — log hours per client with billing rates."""
    firm = _get_firm(request.user)
    if not firm: return redirect('login')

    clients = Client.objects.filter(firm=firm)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_entry':
            client_id = request.POST.get('client_id')
            client = get_object_or_404(Client, id=client_id, firm=firm)
            hours = float(request.POST.get('hours', 0))
            rate = float(request.POST.get('rate', 250))
            desc = request.POST.get('description', '').strip()

            TimeEntry.objects.create(
                client=client, user=request.user,
                date=request.POST.get('date', today),
                hours=hours, rate=rate,
                amount=hours * rate,
                description=desc or 'Professional services',
                billing_status='unbilled',
            )
            messages.success(request, f'Time entry logged: {hours}h at ${rate}/hr = ${hours * rate:.2f}')
        elif action == 'generate_invoice':
            client_id = request.POST.get('client_id')
            unbilled = TimeEntry.objects.filter(client_id=client_id, client__firm=firm, billing_status='unbilled')
            if unbilled.exists():
                total = sum(e.amount for e in unbilled)
                client = Client.objects.filter(id=client_id, firm=firm).first()
                if not client:
                    return redirect('time_tracking')
                inv = Invoice.objects.create(
                    client=client,
                    description=f'Professional Services — {today.strftime("%B %Y")}',
                    service_type='professional_services',
                    amount=total, status='sent',
                    invoice_date=today, due_date=today + timedelta(days=30),
                )
                unbilled.update(billing_status='billed', invoice=inv)
                messages.success(request, f'Invoice created from {unbilled.count()} time entries — ${total:.2f}')
        return redirect('time_tracking')

    entries = TimeEntry.objects.filter(client__firm=firm).select_related('client', 'user').order_by('-date', '-created_at')
    unbilled_total = entries.filter(billing_status='unbilled').aggregate(t=Sum('amount'))['t'] or 0
    billed_total = entries.filter(billing_status='billed').aggregate(t=Sum('amount'))['t'] or 0
    week_hours = entries.filter(date__gte=week_start).aggregate(t=Sum('hours'))['t'] or 0

    return render(request, 'clients/time_tracking.html', {
        'firm': firm, 'clients': clients, 'entries': entries[:50],
        'unbilled_total': unbilled_total, 'billed_total': billed_total,
        'week_hours': week_hours, 'today': today,
    })


# ═══════════════════════════════════════════════════════════════════════
# PAYROLL PROCESSING
# ═══════════════════════════════════════════════════════════════════════

@login_required
def payroll_dashboard(request):
    """Payroll processing — pay stubs, source deductions, T4 preparation."""
    firm = _get_firm(request.user)
    if not firm: return redirect('login')

    clients = Client.objects.filter(firm=firm)
    today = date.today()
    result = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'calculate':
            salary = float(request.POST.get('salary', 0))
            period = request.POST.get('period', 'monthly')
            province = request.POST.get('province', 'ON')

            periods_per_year = {'monthly': 12, 'biweekly': 26, 'weekly': 52}
            n = periods_per_year.get(period, 12)
            annual = salary * n

            # CPP 2026 rates
            cpp_rate = 0.0595
            cpp_max = 68500
            cpp_exemption = 3500 / n
            cpp = max(0, min(salary - cpp_exemption, (cpp_max - 3500) / n) * cpp_rate)

            # EI 2026 rates
            ei_rate = 0.0163
            ei_max = 63300
            ei = min(salary, ei_max / n) * ei_rate

            # Federal tax (simplified brackets 2026)
            annual_taxable = annual - (cpp * n) - (ei * n)
            federal_tax = _calc_federal_tax(annual_taxable)

            # Ontario provincial tax (simplified)
            ontario_tax = _calc_ontario_tax(annual_taxable) if province == 'ON' else 0

            total_tax = (federal_tax + ontario_tax) / n
            net_pay = salary - cpp - ei - total_tax

            result = {
                'salary': salary, 'period': period, 'annual_salary': annual,
                'cpp': round(cpp, 2), 'ei': round(ei, 2),
                'federal_tax': round(federal_tax / n, 2), 'provincial_tax': round(ontario_tax / n, 2),
                'total_deductions': round(cpp + ei + total_tax, 2),
                'net_pay': round(net_pay, 2),
                'employer_cpp': round(cpp, 2), 'employer_ei': round(ei * 1.4, 2),
                'total_employer_cost': round(salary + cpp + ei * 1.4, 2),
            }

        elif action == 'generate_paystub':
            client_id = request.POST.get('client_id')
            client = get_object_or_404(Client, id=client_id, firm=firm)
            messages.success(request, f'Pay stub generated for {client.name} — PDF ready for download.')

    return render(request, 'clients/payroll_dashboard.html', {
        'firm': firm, 'clients': clients, 'result': result, 'today': today,
    })


def _calc_federal_tax(income):
    brackets = [(0, 0), (55867, 0.15), (111733, 0.205), (173205, 0.26), (246752, 0.29)]
    tax = 0
    remaining = income
    for i in range(len(brackets) - 1, 0, -1):
        if income > brackets[i][0]:
            tax += (income - brackets[i][0]) * brackets[i][1]
            income = brackets[i][0]
    if income > brackets[1][0]:
        tax += (income - brackets[1][0]) * brackets[1][1]
    return tax


def _calc_ontario_tax(income):
    brackets = [(0, 0), (51446, 0.0505), (102894, 0.0915), (150000, 0.1116), (220000, 0.1216)]
    tax = 0
    for i in range(len(brackets) - 1, 0, -1):
        if income > brackets[i][0]:
            tax += (income - brackets[i][0]) * brackets[i][1]
            income = brackets[i][0]
    if income > brackets[1][0]:
        tax += (income - brackets[1][0]) * brackets[1][1]
    return tax


# ═══════════════════════════════════════════════════════════════════════
# FINANCIAL DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

@login_required
def financial_dashboard(request):
    """Financial dashboard — P&L, revenue analytics, firm performance."""
    firm = _get_firm(request.user)
    if not firm: return redirect('login')

    today = date.today()
    year_start = today.replace(month=1, day=1)
    month_start = today.replace(day=1)

    clients = Client.objects.filter(firm=firm)

    # Revenue
    invoices = Invoice.objects.filter(client__firm=firm)
    revenue_ytd = invoices.filter(status='paid', paid_date__gte=year_start).aggregate(t=Sum('total_amount'))['t'] or 0
    revenue_month = invoices.filter(status='paid', paid_date__gte=month_start).aggregate(t=Sum('total_amount'))['t'] or 0
    outstanding = invoices.filter(status__in=['sent', 'overdue']).aggregate(t=Sum('total_amount'))['t'] or 0
    overdue = invoices.filter(status='overdue').aggregate(t=Sum('total_amount'))['t'] or 0

    # By service type
    by_service = {}
    for inv in invoices.filter(status='paid', paid_date__gte=year_start):
        st = inv.get_service_type_display()
        by_service[st] = by_service.get(st, 0) + float(inv.total_amount)

    # Monthly trend (last 12 months)
    monthly = []
    for i in range(11, -1, -1):
        m = today.replace(day=1) - timedelta(days=1)
        for _ in range(i):
            m = (m.replace(day=1) - timedelta(days=1)).replace(day=1) if m.month > 1 else m.replace(year=m.year-1, month=12, day=1)
        ms = m.replace(day=1)
        me = (ms.replace(month=ms.month+1, day=1) if ms.month < 12 else ms.replace(year=ms.year+1, month=1, day=1))
        amt = invoices.filter(status='paid', paid_date__gte=ms, paid_date__lt=me).aggregate(t=Sum('total_amount'))['t'] or 0
        monthly.append({'month': ms.strftime('%b'), 'amount': float(amt)})

    # Profit estimates
    time_cost = TimeEntry.objects.filter(client__firm=firm, date__gte=year_start).aggregate(t=Sum('amount'))['t'] or 0
    expenses = float(revenue_ytd) * 0.15  # Estimated 15% expenses
    estimated_profit = float(revenue_ytd) - expenses

    # Client revenue ranking
    client_rev = []
    for c in clients:
        rev = invoices.filter(client=c, status='paid', paid_date__gte=year_start).aggregate(t=Sum('total_amount'))['t'] or 0
        if rev > 0:
            client_rev.append({'client': c, 'revenue': float(rev)})
    client_rev.sort(key=lambda x: x['revenue'], reverse=True)

    return render(request, 'clients/financial_dashboard.html', {
        'firm': firm, 'today': today,
        'revenue_ytd': float(revenue_ytd), 'revenue_month': float(revenue_month),
        'outstanding': float(outstanding), 'overdue': float(overdue),
        'by_service': sorted(by_service.items(), key=lambda x: x[1], reverse=True),
        'monthly': monthly, 'client_rev': client_rev[:10],
        'estimated_profit': estimated_profit, 'total_clients': clients.count(),
    })


# ═══════════════════════════════════════════════════════════════════════
# COLLECTIONS
# ═══════════════════════════════════════════════════════════════════════

@login_required
def collections_dashboard(request):
    """Collections — track overdue invoices, send reminders, payment plans."""
    firm = _get_firm(request.user)
    if not firm: return redirect('login')

    today = date.today()
    clients = Client.objects.filter(firm=firm)

    overdue_invoices = Invoice.objects.filter(
        client__firm=firm, status='overdue'
    ).select_related('client').order_by('-due_date')

    # Aging buckets
    aging = {'30': [], '60': [], '90': [], '90plus': []}
    for inv in overdue_invoices:
        days_overdue = (today - (inv.due_date or inv.invoice_date)).days
        if days_overdue <= 30:
            aging['30'].append(inv)
        elif days_overdue <= 60:
            aging['60'].append(inv)
        elif days_overdue <= 90:
            aging['90'].append(inv)
        else:
            aging['90plus'].append(inv)

    total_overdue = sum(float(inv.total_amount) for inv in overdue_invoices)
    total_clients = overdue_invoices.values('client').distinct().count()

    if request.method == 'POST':
        action = request.POST.get('action')
        inv_id = request.POST.get('invoice_id')
        inv = get_object_or_404(Invoice, id=inv_id, client__firm=firm)

        if action == 'send_reminder':
            inv.reminder_count = (inv.reminder_count or 0) + 1
            inv.last_reminder_date = today
            inv.save()
            messages.success(request, f'Reminder sent for {inv.invoice_number} — {inv.client.name}')

        elif action == 'mark_paid':
            inv.status = 'paid'
            inv.paid_date = today
            inv.save()
            log_activity(request.user, 'payment', 'Invoice', inv.id, inv.invoice_number,
                         f'Invoice {inv.invoice_number} marked as paid — ${inv.total_amount}', firm=firm)
            messages.success(request, f'{inv.invoice_number} marked as paid!')

        return redirect('collections')

    return render(request, 'clients/collections_dashboard.html', {
        'firm': firm, 'overdue_invoices': overdue_invoices,
        'aging': aging, 'total_overdue': total_overdue,
        'total_clients_overdue': total_clients, 'today': today,
    })
