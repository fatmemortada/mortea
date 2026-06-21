"""Client Portal 2.0 views — real-time entity dashboard for clients."""
import os, stripe
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.conf import settings
from datetime import date, timedelta

from ..models import (
    Client, Invoice, Document, ComplianceTask, EntitySubscription,
    ClientPortalRequest, ClientInvoicePayment, ClientNotification,
    CorporateProfile, Director, Shareholder, AnnualFiling,
    log_activity,
)
from ._helpers import _get_firm, compute_health_score

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')


@login_required
def client_portal_dashboard(request):
    """Enhanced client portal — real-time entity dashboard."""
    # Get the client associated with this user
    profile = getattr(request.user, 'userprofile', None)
    if not profile or not profile.portal_client:
        messages.error(request, 'No client account associated.')
        return redirect('client_login')

    client = profile.portal_client
    today = date.today()

    # Entity data
    cp = getattr(client, 'corporate_profile', None)
    directors = client.directors.all()
    shareholders = client.shareholders.all()
    filings = client.annual_filings.all().order_by('-year')

    # Compliance
    tasks = ComplianceTask.objects.filter(client=client).order_by('due_date')
    overdue_tasks = tasks.filter(status='overdue')
    upcoming_tasks = tasks.filter(status='pending', due_date__gte=today).order_by('due_date')[:10]
    health = compute_health_score(client)

    # Documents
    docs = Document.objects.filter(client=client, is_client_visible=True).order_by('-created_at')[:10]
    # Also show onboarding documents
    from ..models import OnboardingDocument
    onboarding_docs = OnboardingDocument.objects.filter(client=client).order_by('-uploaded_at')[:10]

    # Invoices
    invoices = Invoice.objects.filter(client=client).order_by('-invoice_date')
    unpaid = invoices.filter(status__in=['sent', 'overdue'])
    paid = invoices.filter(status='paid')

    # Subscriptions
    subs = EntitySubscription.objects.filter(client=client).select_related('plan')

    # Notifications
    notifications = ClientNotification.objects.filter(
        client=client, is_dismissed=False
    ).order_by('-created_at')[:15]

    # Requests
    requests = ClientPortalRequest.objects.filter(client=client).order_by('-created_at')[:10]

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'submit_request':
            req = ClientPortalRequest.objects.create(
                client=client, requested_by=request.user,
                request_type=request.POST.get('request_type', 'general'),
                priority=request.POST.get('priority', 'normal'),
                subject=request.POST.get('subject', '').strip(),
                description=request.POST.get('description', '').strip(),
            )
            if request.FILES.get('attachment'):
                req.attachment = request.FILES['attachment']
                req.save()
            log_activity(client, f'Client submitted request: {req.subject}', request.user)
            messages.success(request, 'Your request has been submitted!')

        elif action == 'pay_invoice':
            inv_id = request.POST.get('invoice_id')
            inv = get_object_or_404(Invoice, id=inv_id, client=client, status__in=['sent', 'overdue'])
            try:
                checkout = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    mode='payment',
                    line_items=[{
                        'price_data': {
                            'currency': 'cad',
                            'product_data': {'name': f'Invoice {inv.invoice_number}'},
                            'unit_amount': int(float(inv.total_amount) * 100),
                        },
                        'quantity': 1,
                    }],
                    success_url=f"{getattr(settings, 'SITE_URL', '')}/client/portal/?paid={inv.id}",
                    cancel_url=f"{getattr(settings, 'SITE_URL', '')}/client/portal/",
                    metadata={'invoice_id': str(inv.id), 'client_id': str(client.id)},
                )
                ClientInvoicePayment.objects.create(
                    client=client, invoice=inv, amount=inv.total_amount,
                    stripe_payment_intent_id=checkout.id,
                )
                return redirect(checkout.url)
            except Exception as e:
                messages.error(request, f'Payment error: {e}')

        elif action == 'mark_notification_read':
            notif_id = request.POST.get('notif_id')
            ClientNotification.objects.filter(id=notif_id, client=client).update(is_read=True)

        return redirect('client_portal_dashboard')

    return render(request, 'clients/client_portal_dashboard.html', {
        'client': client, 'corporate_profile': cp,
        'directors': directors, 'shareholders': shareholders, 'filings': filings,
        'overdue_tasks': overdue_tasks, 'upcoming_tasks': upcoming_tasks,
        'health': health, 'docs': docs, 'onboarding_docs': onboarding_docs,
        'invoices': invoices, 'unpaid': unpaid, 'paid': paid,
        'subs': subs, 'notifications': notifications, 'requests': requests,
        'today': today, 'stripe_key': os.environ.get('STRIPE_PUBLISHABLE_KEY', ''),
    })


@login_required
def portal_request_detail(request, request_id):
    """View a specific request status."""
    profile = getattr(request.user, 'userprofile', None)
    if not profile or not profile.portal_client:
        return redirect('client_login')

    client = profile.portal_client
    req = get_object_or_404(ClientPortalRequest, id=request_id, client=client)

    return render(request, 'clients/portal_request_detail.html', {
        'client': client, 'request': req,
    })


@login_required
def manage_portal_requests(request):
    """Firm-side view to manage client portal requests."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    requests = ClientPortalRequest.objects.filter(
        client__firm=firm
    ).select_related('client').order_by('-created_at')

    pending = requests.filter(status='new')

    if request.method == 'POST':
        action = request.POST.get('action')
        req_id = request.POST.get('request_id')

        if action == 'respond':
            req = get_object_or_404(ClientPortalRequest, id=req_id, client__firm=firm)
            response = request.POST.get('response', '').strip()
            new_status = request.POST.get('status', 'in_progress')
            req.admin_response = response
            req.status = new_status
            if new_status == 'completed':
                req.resolve(user=request.user, response=response)
            else:
                req.save()

            # Notify client
            ClientNotification.objects.create(
                client=req.client,
                title=f'Update on your request: {req.subject}',
                message=response or f'Your request status has been updated to {req.get_status_display()}.',
                notification_type='request_update',
                link_url=f'/client/portal/request/{req.id}/',
            )
            messages.success(request, f'Response sent to {req.client.name}.')

        elif action == 'create_invoice':
            req = get_object_or_404(ClientPortalRequest, id=req_id, client__firm=firm)
            amount = float(request.POST.get('amount', 0))
            if amount > 0:
                inv = Invoice.objects.create(
                    client=req.client,
                    description=f'Service: {req.subject}',
                    service_type='other',
                    amount=amount,
                    status='sent',
                    invoice_date=date.today(),
                    due_date=date.today() + timedelta(days=30),
                )
                req.invoice = inv
                req.save()
                messages.success(request, f'Invoice created for {req.client.name}.')

        return redirect('manage_portal_requests')

    return render(request, 'clients/manage_requests.html', {
        'firm': firm, 'requests': requests, 'pending': pending,
    })
