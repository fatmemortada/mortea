import os
import stripe
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from django.conf import settings
import datetime

from ..models import (
    Client, Invoice, UserProfile, log_activity, EngagementLetterRecord,
    TimeEntry, PaymentRecord, EntitySubscription, SubscriptionInvoice,
)
from ._helpers import _get_firm, require_permission

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
SITE_URL = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')


@login_required
@require_permission('billing', 'view')
def billing_dashboard_view(request):
    try:
        firm = request.user.userprofile.firm
    except UserProfile.DoesNotExist:
        return redirect('login')

    today = timezone.now().date()
    month_start = today.replace(day=1)

    clients = Client.objects.filter(firm=firm)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_invoice':
            client_id = request.POST.get('client_id')
            service_type = request.POST.get('service_type', 'other')
            amount = request.POST.get('amount', 0)
            invoice_date = request.POST.get('invoice_date')
            due_date = request.POST.get('due_date') or None
            description = request.POST.get('description', '').strip()
            notes = request.POST.get('notes', '').strip()
            send_after = request.POST.get('send_after', '0')
            client = Client.objects.filter(id=client_id, firm=firm).first()
            if client and description and invoice_date:
                count = Invoice.objects.filter(client__firm=firm).count() + 1
                Invoice.objects.create(
                    client=client, service_type=service_type, amount=amount,
                    invoice_date=invoice_date, due_date=due_date,
                    description=description, notes=notes,
                    status='sent' if send_after == '1' else 'draft',
                    invoice_number=f"INV-{count:04d}",
                )
            return redirect('billing_dashboard')

        elif action == 'mark_paid':
            inv_id = request.POST.get('invoice_id')
            inv = Invoice.objects.filter(id=inv_id, client__firm=firm).first()
            if inv:
                inv.status = 'paid'; inv.paid_date = today; inv.save()
                # Fire workflow trigger
                from ..workflow_triggers import trigger_workflows
                trigger_workflows('invoice_paid', inv.client.firm_id, {
                    'client_id': inv.client_id, 'invoice_id': inv.id,
                    'invoice_number': inv.invoice_number,
                    'amount': float(inv.total_amount),
                })
            return redirect('billing_dashboard')

        elif action == 'mark_sent':
            inv_id = request.POST.get('invoice_id')
            inv = Invoice.objects.filter(id=inv_id, client__firm=firm).first()
            if inv:
                inv.status = 'sent'; inv.save()
            return redirect('billing_dashboard')

        elif action == 'delete_invoice':
            inv_id = request.POST.get('invoice_id')
            Invoice.objects.filter(id=inv_id, client__firm=firm).delete()
            return redirect('billing_dashboard')

    invoices = Invoice.objects.filter(
        client__firm=firm
    ).select_related('client').order_by('-invoice_date')

    total_paid = invoices.filter(status='paid').aggregate(t=Sum('amount'))['t'] or 0
    paid_count = invoices.filter(status='paid').count()
    total_outstanding = invoices.filter(status__in=['sent','overdue']).aggregate(t=Sum('amount'))['t'] or 0
    outstanding_count = invoices.filter(status__in=['sent','overdue']).count()
    total_overdue = invoices.filter(status='overdue').aggregate(t=Sum('amount'))['t'] or 0
    overdue_count = invoices.filter(status='overdue').count()
    draft_count = invoices.filter(status='draft').count()
    paid_this_month = invoices.filter(status='paid', paid_date__gte=month_start).aggregate(t=Sum('amount'))['t'] or 0
    paid_this_month_count = invoices.filter(status='paid', paid_date__gte=month_start).count()

    monthly_bars = []
    for i in range(5, -1, -1):
        d = today - datetime.timedelta(days=30*i)
        m_start = d.replace(day=1)
        if m_start.month == 12:
            m_end = m_start.replace(year=m_start.year+1, month=1, day=1)
        else:
            m_end = m_start.replace(month=m_start.month+1, day=1)
        amt = invoices.filter(status='paid', paid_date__gte=m_start, paid_date__lt=m_end).aggregate(t=Sum('amount'))['t'] or 0
        monthly_bars.append({'month': d.strftime('%b %Y'), 'amount': amt, 'current': i == 0})
    max_amt = max((b['amount'] for b in monthly_bars), default=1) or 1
    for b in monthly_bars:
        b['height'] = max(4, int((float(b['amount']) / float(max_amt)) * 44))

    return render(request, 'clients/billing_dashboard.html', {
        'firm': firm, 'invoices': invoices, 'clients': clients,
        'total_paid': total_paid, 'paid_count': paid_count,
        'total_outstanding': total_outstanding, 'outstanding_count': outstanding_count,
        'total_overdue': total_overdue, 'overdue_count': overdue_count,
        'draft_count': draft_count, 'paid_this_month': paid_this_month,
        'paid_this_month_count': paid_this_month_count, 'monthly_bars': monthly_bars,
        'stripe_publishable_key': os.environ.get('STRIPE_PUBLISHABLE_KEY', ''),
    })


def _create_stripe_payment_link(invoice):
    """Generate a Stripe-hosted payment link for an invoice."""
    if not stripe.api_key:
        return None
    try:
        price = stripe.Price.create(
            unit_amount=int(float(invoice.total_amount) * 100),
            currency='cad',
            product_data={
                'name': f'Invoice {invoice.invoice_number}',
                'description': f'Mortacc — {invoice.client.name}',
            },
        )
        payment_link = stripe.PaymentLink.create(
            line_items=[{'price': price.id, 'quantity': 1}],
            metadata={
                'invoice_id': str(invoice.id),
                'client_id': str(invoice.client_id),
            },
            after_completion={
                'type': 'redirect',
                'redirect': {'url': f'{SITE_URL}/billing/'},
            },
        )
        invoice.stripe_payment_link = payment_link.url
        invoice.stripe_payment_link_id = payment_link.id
        invoice.save()
        return payment_link.url
    except stripe.error.StripeError as e:
        import logging
        logging.getLogger(__name__).error(f'Stripe payment link error: {e}')
        return None


def _generate_invoice_from_time_entries(client, entries, status='draft', send_payment_link=False):
    """Generate an invoice from a list of time entries."""
    from datetime import date, timedelta
    today = date.today()

    total = sum(float(e.amount or 0) for e in entries)
    desc_lines = []
    for e in sorted(entries, key=lambda x: x.date):
        desc_lines.append(f"{e.date}: {e.description} — {e.hours}h × ${float(e.hourly_rate):.2f}/hr = ${float(e.amount):.2f}")
    description = 'Professional services (time-based billing):\n' + '\n'.join(desc_lines)

    inv = Invoice.objects.create(
        client=client,
        description=description,
        service_type='consultation',
        amount=total,
        status=status,
        invoice_date=today,
        due_date=today + timedelta(days=30),
    )

    # Link time entries
    entries.update(billing_status='billed', invoice=inv)

    # Create Stripe payment link if requested
    if send_payment_link and status == 'sent':
        _create_stripe_payment_link(inv)

    return inv


@login_required
def engagements_view(request):
    profile = getattr(request.user, 'userprofile', None)
    if profile and not profile.get_plan_limit('engagement_letters'):
        from django.contrib import messages
        messages.warning(request, 'Engagement letters are available on the Professional plan and above. Upgrade in Settings.')
        return redirect('dashboard')

    firm = _get_firm(request.user)
    firm_clients = Client.objects.filter(firm=firm).values_list('id', flat=True) if firm else []

    records = EngagementLetterRecord.objects.filter(
        client__id__in=firm_clients
    ).select_related('client', 'lead').order_by('-signed_at')

    today = timezone.now()
    month_start = today.replace(day=1, hour=0, minute=0, second=0)

    return render(request, 'clients/engagements.html', {
        'records': records, 'total': records.count(),
        'signed_count': records.filter(is_signed=True).count(),
        'this_month_count': records.filter(signed_at__gte=month_start).count(),
    })


@login_required
@require_permission('settings', 'view')
def settings_view(request):
    firm = _get_firm(request.user)
    success_message = ""
    error_message = ""

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_firm" and firm:
            firm_name = request.POST.get("firm_name", "").strip()
            if firm_name:
                firm.name = firm_name; firm.save()
                success_message = "Firm details updated successfully."
            else:
                error_message = "Firm name cannot be empty."

        elif action == "update_account":
            request.user.first_name = request.POST.get("first_name", "").strip()
            request.user.last_name = request.POST.get("last_name", "").strip()
            new_email = request.POST.get("email", "").strip()
            if new_email and new_email != request.user.email:
                from django.contrib.auth.models import User
                if User.objects.filter(username=new_email).exclude(pk=request.user.pk).exists():
                    error_message = "That email is already in use by another account."
                else:
                    request.user.email = new_email
                    request.user.username = new_email
            if not error_message:
                request.user.save()
                success_message = "Account details updated successfully."

        elif action == "change_password":
            current_pw = request.POST.get("current_password", "")
            new_pw = request.POST.get("new_password", "")
            confirm_pw = request.POST.get("confirm_password", "")
            if not request.user.check_password(current_pw):
                error_message = "Current password is incorrect."
            elif new_pw != confirm_pw:
                error_message = "New passwords do not match."
            elif len(new_pw) < 8:
                error_message = "Password must be at least 8 characters."
            else:
                request.user.set_password(new_pw)
                request.user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, request.user)
                success_message = "Password changed successfully."

    from ..models import StaffInvite
    from .auth import _get_staff
    platform_agreement = getattr(request.user, 'platform_agreement', None)
    return render(request, "clients/settings.html", {
        "firm": firm, "success_message": success_message,
        "error_message": error_message,
        "staff_members": _get_staff(firm),
        "pending_invites": StaffInvite.objects.filter(firm=firm, accepted=False) if firm else [],
        "platform_agreement": platform_agreement,
    })
