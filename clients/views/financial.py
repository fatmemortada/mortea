"""
Unified Entity Financial Dashboard.

No competitor has this — connects entity data to financial reality.
Shows real-time P&L per entity, inter-entity relationships,
consolidated views for holding company groups.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import date, timedelta

from ..models import (
    Client, Invoice, EntitySubscription, ComplianceTask,
    CorporateProfile, Shareholder, Director, AnnualFiling,
    TimeEntry, log_activity,
)
from ._helpers import _get_firm, compute_health_score


@login_required
def entity_financial_dashboard(request, client_id=None):
    """
    Financial dashboard for a specific entity or consolidated view
    of all entities for the firm.
    """
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    if client_id:
        # Single entity view
        client = Client.objects.filter(id=client_id, firm=firm).first()
        if not client:
            return redirect('financial_dashboard')
        entities = [client]
        is_consolidated = False
    else:
        # Consolidated view
        entities = Client.objects.filter(firm=firm)
        is_consolidated = True

    entity_data = []
    total_revenue_ytd = 0
    total_outstanding = 0
    total_mrr = 0
    total_compliance_score = 0

    for entity in entities:
        # Revenue
        invoices = Invoice.objects.filter(client=entity)
        paid_ytd = invoices.filter(
            status='paid', paid_date__gte=year_start
        ).aggregate(t=Sum('total_amount'))['t'] or 0
        outstanding = invoices.filter(
            status__in=['sent', 'overdue']
        ).aggregate(t=Sum('total_amount'))['t'] or 0
        overdue = invoices.filter(
            status='overdue'
        ).aggregate(t=Sum('total_amount'))['t'] or 0
        paid_lifetime = invoices.filter(
            status='paid'
        ).aggregate(t=Sum('total_amount'))['t'] or 0

        # Subscription MRR
        subs = EntitySubscription.objects.filter(client=entity, status='active')
        entity_mrr = sum(s.monthly_revenue for s in subs) / 100

        # Compliance
        profile = getattr(entity, 'corporate_profile', None)
        tasks = ComplianceTask.objects.filter(client=entity)
        total_tasks = tasks.count()
        completed = tasks.filter(status='completed').count()
        overdue_count = tasks.filter(
            Q(status='overdue') | Q(status='pending', due_date__lt=today)
        ).count()
        compliance_pct = int((completed / max(total_tasks, 1)) * 100)

        # Health score
        health = compute_health_score(entity)

        # Time entries
        time_entries = TimeEntry.objects.filter(client=entity)
        unbilled_hours = time_entries.filter(billing_status='unbilled').aggregate(
            t=Sum('hours')
        )['t'] or 0
        billed_hours = time_entries.filter(billing_status='billed').aggregate(
            t=Sum('hours')
        )['t'] or 0

        # Entity structure
        directors_count = Director.objects.filter(client=entity, resignation_date__isnull=True).count()
        shareholders_count = Shareholder.objects.filter(client=entity).count()
        has_profile = profile and profile.incorporation_date

        entity_data.append({
            'client': entity,
            'profile': profile,
            'paid_ytd': float(paid_ytd),
            'outstanding': float(outstanding),
            'overdue': float(overdue),
            'paid_lifetime': float(paid_lifetime),
            'mrr': entity_mrr,
            'compliance_pct': compliance_pct,
            'overdue_tasks': overdue_count,
            'total_tasks': total_tasks,
            'completed_tasks': completed,
            'health': health,
            'unbilled_hours': float(unbilled_hours),
            'billed_hours': float(billed_hours),
            'directors_count': directors_count,
            'shareholders_count': shareholders_count,
            'has_profile': has_profile,
        })

        total_revenue_ytd += float(paid_ytd)
        total_outstanding += float(outstanding)
        total_mrr += entity_mrr
        total_compliance_score += compliance_pct

    entity_count = len(entities)
    avg_compliance = int(total_compliance_score / max(entity_count, 1))
    avg_health = int(sum(e['health']['score'] for e in entity_data) / max(entity_count, 1))

    # Revenue trend (last 6 months)
    revenue_trend = []
    for i in range(5, -1, -1):
        d = today - timedelta(days=30 * i)
        m_start = d.replace(day=1)
        if m_start.month == 12:
            m_end = m_start.replace(year=m_start.year + 1, month=1, day=1)
        else:
            m_end = m_start.replace(month=m_start.month + 1, day=1)
        amt = Invoice.objects.filter(
            client__firm=firm, status='paid',
            paid_date__gte=m_start, paid_date__lt=m_end
        ).aggregate(t=Sum('total_amount'))['t'] or 0
        revenue_trend.append({
            'month': m_start.strftime('%b %Y'),
            'amount': float(amt),
            'is_current': i == 0,
        })

    # Projected revenue (next 12 months from subscriptions)
    projected_annual = total_mrr * 12

    # Top entities by revenue
    top_entities = sorted(entity_data, key=lambda x: x['paid_ytd'], reverse=True)[:10]

    max_trend = max((b['amount'] for b in revenue_trend), default=1) or 1

    return render(request, 'clients/financial_dashboard.html', {
        'firm': firm,
        'entity_data': entity_data,
        'is_consolidated': is_consolidated,
        'total_revenue_ytd': total_revenue_ytd,
        'total_outstanding': total_outstanding,
        'total_mrr': total_mrr,
        'projected_annual': projected_annual,
        'entity_count': entity_count,
        'avg_compliance': avg_compliance,
        'avg_health': avg_health,
        'revenue_trend': revenue_trend,
        'revenue_trend_max': max_trend,
        'top_entities': top_entities,
        'today': today,
    })


@login_required
def time_tracking_view(request):
    """View and manage time entries for billing."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    today = date.today()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_entry':
            client_id = request.POST.get('client_id')
            description = request.POST.get('description', '').strip()
            entry_date = request.POST.get('date', str(today))
            hours = request.POST.get('hours', '0')
            rate = request.POST.get('hourly_rate', '0')
            category = request.POST.get('category', 'other')

            client = Client.objects.filter(id=client_id, firm=firm).first()
            if client and description and float(hours) > 0:
                TimeEntry.objects.create(
                    client=client,
                    user=request.user,
                    description=description,
                    date=entry_date,
                    hours=hours,
                    hourly_rate=rate or 0,
                    category=category,
                )

        elif action == 'mark_billed':
            entry_ids = request.POST.getlist('entry_ids')
            invoice_id = request.POST.get('invoice_id')
            invoice = Invoice.objects.filter(id=invoice_id, client__firm=firm).first()
            if invoice and entry_ids:
                TimeEntry.objects.filter(
                    id__in=entry_ids, billing_status='unbilled'
                ).update(billing_status='billed', invoice=invoice)

        elif action == 'generate_invoice':
            client_id = request.POST.get('client_id')
            client = Client.objects.filter(id=client_id, firm=firm).first()
            if client:
                entries = TimeEntry.objects.filter(
                    client=client, billing_status='unbilled'
                )
                if entries.exists():
                    total = sum(float(e.amount) for e in entries if e.amount)
                    desc_parts = []
                    for e in entries.order_by('date'):
                        desc_parts.append(f"{e.date}: {e.description} ({e.hours}h × ${e.hourly_rate}/hr)")
                    description = '\n'.join(desc_parts)
                    inv = Invoice.objects.create(
                        client=client,
                        description=f"Professional services:\n{description}",
                        service_type='consultation',
                        amount=total,
                        status='draft',
                        invoice_date=today,
                        due_date=today + timedelta(days=30),
                    )
                    entries.update(billing_status='billed', invoice=inv)
                    return redirect('billing_dashboard')

        return redirect('time_tracking')

    # Get all unbilled time entries
    unbilled_entries = TimeEntry.objects.filter(
        client__firm=firm, billing_status='unbilled'
    ).select_related('client', 'user').order_by('-date')

    # Get recent billed entries
    recent_billed = TimeEntry.objects.filter(
        client__firm=firm, billing_status='billed'
    ).select_related('client', 'user', 'invoice').order_by('-date')[:50]

    # Summary stats
    total_unbilled_hours = unbilled_entries.aggregate(t=Sum('hours'))['t'] or 0
    total_unbilled_amount = sum(
        float(e.amount) for e in unbilled_entries
    )

    # Group by client
    by_client = {}
    for e in unbilled_entries:
        if e.client_id not in by_client:
            by_client[e.client_id] = {
                'client': e.client,
                'entries': [],
                'total_hours': 0,
                'total_amount': 0,
            }
        by_client[e.client_id]['entries'].append(e)
        by_client[e.client_id]['total_hours'] += float(e.hours)
        by_client[e.client_id]['total_amount'] += float(e.amount or 0)

    clients = Client.objects.filter(firm=firm)

    return render(request, 'clients/time_tracking.html', {
        'firm': firm,
        'unbilled_entries': unbilled_entries,
        'recent_billed': recent_billed,
        'total_unbilled_hours': float(total_unbilled_hours),
        'total_unbilled_amount': total_unbilled_amount,
        'by_client': list(by_client.values()),
        'clients': clients,
        'today': today,
    })


@login_required
def collections_view(request):
    """Manage collections — overdue invoices, payment reminders, escalation."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    today = date.today()

    # Get or create collections rules
    from ..models import CollectionsRule
    rules, _ = CollectionsRule.objects.get_or_create(firm=firm)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_rules':
            rules.reminder_day_1 = int(request.POST.get('reminder_day_1', 1))
            rules.reminder_day_2 = int(request.POST.get('reminder_day_2', 7))
            rules.reminder_day_3 = int(request.POST.get('reminder_day_3', 14))
            rules.reminder_day_final = int(request.POST.get('reminder_day_final', 30))
            rules.auto_mark_overdue = request.POST.get('auto_mark_overdue') == '1'
            rules.send_client_emails = request.POST.get('send_client_emails') == '1'
            rules.auto_escalate_to_firm = request.POST.get('auto_escalate_to_firm') == '1'
            rules.suspend_services_after_days = int(request.POST.get('suspend_services_after_days', 0))
            rules.reminder_email_subject = request.POST.get('reminder_email_subject', rules.reminder_email_subject)
            rules.reminder_email_body = request.POST.get('reminder_email_body', rules.reminder_email_body)
            rules.save()
            return redirect('collections')

        elif action == 'send_reminder':
            invoice_id = request.POST.get('invoice_id')
            inv = Invoice.objects.filter(id=invoice_id, client__firm=firm).first()
            if inv and inv.status in ('sent', 'overdue'):
                # Send reminder email
                from django.core.mail import send_mail
                subject = rules.reminder_email_subject.replace('{{ firm_name }}', firm.name)
                body = rules.reminder_email_body
                body = body.replace('{{ client_name }}', inv.client.name)
                body = body.replace('{{ invoice_number }}', inv.invoice_number)
                body = body.replace('{{ amount }}', f'${inv.total_amount:.2f}')
                body = body.replace('{{ due_date }}', str(inv.due_date))
                body = body.replace('{{ payment_link }}', inv.stripe_payment_link or '#')

                send_mail(
                    subject=subject,
                    message=body,
                    from_email='support@mortacc.com',
                    recipient_list=[inv.client.email],
                    fail_silently=True,
                )
                inv.reminder_count += 1
                inv.last_reminder_sent = timezone.now()
                inv.save()
                log_activity(inv.client, f'Payment reminder #{inv.reminder_count} sent for invoice {inv.invoice_number}', request.user)

        elif action == 'mark_overdue_bulk':
            # Mark all past-due sent invoices as overdue
            Invoice.objects.filter(
                client__firm=firm, status='sent', due_date__lt=today
            ).update(status='overdue')

        return redirect('collections')

    # Overdue invoices
    overdue_invoices = Invoice.objects.filter(
        client__firm=firm, status='overdue'
    ).select_related('client').order_by('due_date')

    # Sent but past due
    past_due_sent = Invoice.objects.filter(
        client__firm=firm, status='sent', due_date__lt=today
    ).select_related('client').order_by('due_date')

    # Aging report (30/60/90+ days)
    aging_buckets = {'30': [], '60': [], '90': [], '90plus': []}
    all_unpaid = Invoice.objects.filter(
        client__firm=firm, status__in=['sent', 'overdue']
    ).select_related('client')
    for inv in all_unpaid:
        if not inv.due_date:
            continue
        days_overdue = (today - inv.due_date).days
        if days_overdue <= 30:
            aging_buckets['30'].append(inv)
        elif days_overdue <= 60:
            aging_buckets['60'].append(inv)
        elif days_overdue <= 90:
            aging_buckets['90'].append(inv)
        else:
            aging_buckets['90plus'].append(inv)

    aging_summary = {
        k: {'count': len(v), 'total': sum(float(i.total_amount) for i in v)}
        for k, v in aging_buckets.items()
    }

    return render(request, 'clients/collections.html', {
        'firm': firm,
        'rules': rules,
        'overdue_invoices': overdue_invoices,
        'past_due_sent': past_due_sent,
        'aging_summary': aging_summary,
        'aging_buckets': aging_buckets,
        'today': today,
    })
