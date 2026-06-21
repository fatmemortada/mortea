"""
Service Catalog + E-Commerce views.

Firms publish services. Clients browse, request, and purchase.
Stripe checkout integration. Automated fulfillment triggers.
"""
import os
import stripe
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.conf import settings
from datetime import date, timedelta

from ..models import (
    Client, Firm, Invoice,
    ServiceCategory, Service, ServiceOrder, ServiceOrderItem, ServiceRequest,
    log_activity,
)
from ._helpers import _get_firm

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
SITE_URL = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')


@login_required
def service_catalog(request):
    """Service catalog — browse and purchase services."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    categories = ServiceCategory.objects.filter(firm=firm, is_active=True).prefetch_related('services')
    services = Service.objects.filter(firm=firm, is_active=True).select_related('category')

    # Client requests
    client = None
    if hasattr(request.user, 'userprofile') and request.user.userprofile.portal_client:
        client = request.user.userprofile.portal_client
        client_orders = ServiceOrder.objects.filter(client=client).order_by('-created_at')[:10]
        client_requests = ServiceRequest.objects.filter(client=client).order_by('-created_at')[:10]
    else:
        client_orders = []
        client_requests = []

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_to_cart':
            service_id = request.POST.get('service_id')
            entity_id = request.POST.get('entity_id') or None
            quantity = int(request.POST.get('quantity', 1))

            service = get_object_or_404(Service, id=service_id, firm=firm, is_active=True)

            # Store in session cart
            cart = request.session.get('service_cart', [])
            cart.append({
                'service_id': service.id,
                'entity_id': entity_id,
                'quantity': quantity,
                'name': service.name,
                'price': float(service.sale_price or service.price),
            })
            request.session['service_cart'] = cart
            messages.success(request, f'{service.name} added to cart.')

        elif action == 'checkout':
            cart = request.session.get('service_cart', [])
            if not cart:
                messages.error(request, 'Cart is empty.')
                return redirect('service_catalog')

            # Calculate totals
            subtotal = sum(item['price'] * item['quantity'] for item in cart)
            tax = subtotal * 0.05  # GST
            total = subtotal + tax

            # Create order
            order_client = client or Client.objects.filter(firm=firm).first()
            if not order_client:
                messages.error(request, 'No client account found. Please contact your accountant.')
                return redirect('service_catalog')
            order = ServiceOrder.objects.create(
                client=order_client,
                firm=firm,
                ordered_by=request.user,
                status='pending',
                subtotal=subtotal,
                tax_amount=tax,
                total=total,
                estimated_completion=date.today() + timedelta(days=10),
            )

            for item in cart:
                service = Service.objects.filter(id=item['service_id'], firm=firm, is_active=True).first()
                if not service:
                    continue
                entity = Client.objects.filter(id=item.get('entity_id')).first() if item.get('entity_id') else None
                ServiceOrderItem.objects.create(
                    order=order, service=service, entity=entity,
                    quantity=item['quantity'],
                    unit_price=item['price'],
                    total_price=item['price'] * item['quantity'],
                )

            # Try Stripe checkout
            try:
                line_items = []
                for item in cart:
                    svc = Service.objects.filter(id=item['service_id'], firm=firm, is_active=True).first()
                    if not svc:
                        continue
                    price_data = {
                        'currency': 'cad',
                        'product_data': {
                            'name': svc.name,
                            'description': svc.short_description or svc.description[:100],
                        },
                        'unit_amount': int(item['price'] * 100),
                    }
                    if svc.stripe_price_id:
                        line_items.append({'price': svc.stripe_price_id, 'quantity': item['quantity']})
                    else:
                        line_items.append({'price_data': price_data, 'quantity': item['quantity']})

                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    mode='payment',
                    customer=request.user.userprofile.stripe_customer_id or None,
                    line_items=line_items,
                    success_url=f"{SITE_URL}/billing/?order_success={order.id}",
                    cancel_url=f"{SITE_URL}/services/?canceled=1",
                    metadata={
                        'order_id': str(order.id),
                        'firm_id': str(firm.id),
                    },
                )
                order.stripe_checkout_session_id = checkout_session.id
                order.payment_url = checkout_session.url
                order.save()

                request.session['service_cart'] = []
                return redirect(checkout_session.url)

            except stripe.error.StripeError as e:
                import logging
                logging.getLogger(__name__).error(f'Stripe checkout error: {e}')
                messages.error(request, 'Payment processing error. Your order has been saved.')

            request.session['service_cart'] = []

        elif action == 'request_service':
            service_id = request.POST.get('service_id')
            description = request.POST.get('description', '').strip()
            urgency = request.POST.get('urgency', 'normal')

            service = Service.objects.filter(id=service_id, firm=firm).first()
            ServiceRequest.objects.create(
                client=client or Client.objects.filter(firm=firm).first(),
                firm=firm, service=service,
                requested_service=service.name if service else 'Custom request',
                description=description, urgency=urgency,
            )
            messages.success(request, 'Service request submitted! We will review and provide a quote.')

        return redirect('service_catalog')

    cart = request.session.get('service_cart', [])
    cart_total = sum(item['price'] * item['quantity'] for item in cart)

    return render(request, 'clients/service_catalog.html', {
        'firm': firm, 'categories': categories, 'services': services,
        'cart': cart, 'cart_total': cart_total, 'cart_count': len(cart),
        'client_orders': client_orders, 'client_requests': client_requests,
        'is_client_view': client is not None,
    })


@login_required
def service_orders_dashboard(request):
    """View and manage all service orders (firm-side)."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    orders = ServiceOrder.objects.filter(firm=firm).select_related('client').order_by('-created_at')
    pending = orders.filter(status__in=['pending', 'paid', 'in_progress'])
    completed = orders.filter(status='completed')

    if request.method == 'POST':
        action = request.POST.get('action')
        order_id = request.POST.get('order_id')

        if action == 'mark_paid':
            order = orders.filter(id=order_id).first()
            if order:
                order.mark_paid()
                log_activity(order.client, f'Order #{order.id} marked paid', request.user)
                messages.success(request, f'Order #{order.id} marked as paid.')

        elif action == 'mark_complete':
            order = orders.filter(id=order_id).first()
            if order:
                order.status = 'completed'
                order.save()
                # Generate invoice
                if not order.invoice:
                    inv = Invoice.objects.create(
                        client=order.client,
                        description=f'Services: {", ".join(item.service.name for item in order.items.all())}',
                        service_type='other',
                        amount=order.total,
                        status='sent',
                        invoice_date=date.today(),
                        due_date=date.today() + timedelta(days=30),
                    )
                    order.invoice = inv
                    order.save()
                log_activity(order.client, f'Order #{order.id} completed', request.user)
                messages.success(request, f'Order #{order.id} completed and invoiced.')

        elif action == 'convert_request':
            req_id = request.POST.get('request_id')
            sreq = ServiceRequest.objects.filter(id=req_id, firm=firm).first()
            if sreq:
                amount = request.POST.get('quote_amount', 0)
                # Create order from request
                order = ServiceOrder.objects.create(
                    client=sreq.client, firm=firm,
                    ordered_by=request.user, status='pending',
                    subtotal=amount, total=amount,
                    notes=f'Converted from service request: {sreq.requested_service}',
                )
                sreq.status = 'converted'
                sreq.quote_amount = amount
                sreq.converted_order = order
                sreq.save()
                messages.success(request, f'Request converted to order #{order.id}.')

        return redirect('service_orders')

    requests = ServiceRequest.objects.filter(firm=firm, status='new').select_related('client').order_by('-created_at')

    return render(request, 'clients/service_orders.html', {
        'firm': firm, 'orders': orders, 'pending': pending, 'completed': completed,
        'requests': requests,
    })


@login_required
def annual_package_view(request, client_id=None):
    """Generate a complete annual maintenance package for an entity."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if client_id:
        client = get_object_or_404(Client, id=client_id, firm=firm)
        entities = [client]
    else:
        entities = Client.objects.filter(firm=firm)

    entity_packages = []
    for entity in entities:
        profile = getattr(entity, 'corporate_profile', None)
        if not profile or not profile.incorporation_date:
            continue

        years_since = (date.today() - profile.incorporation_date).days // 365
        if years_since < 0:
            continue

        # Determine what needs to be done
        tasks = ComplianceTask.objects.filter(client=entity)
        filings = AnnualFiling.objects.filter(client=entity) if hasattr(entity, 'annual_filings') else entity.annual_filings.all()

        needs = {
            'annual_resolution': not filings.filter(year=date.today().year, status='filed').exists(),
            'minute_book_update': not tasks.filter(task_type='minute_book_update', status='completed').exists(),
            'agm_minutes': not tasks.filter(task_type='agm', status='completed').exists(),
            'directors_update': True,  # Always good practice
            'shareholders_update': True,
        }

        doc_count = sum(1 for v in needs.values() if v)
        estimated_fee = doc_count * 100  # Rough estimate

        entity_packages.append({
            'client': entity,
            'profile': profile,
            'years_since_inc': years_since,
            'needs': needs,
            'doc_count': doc_count,
            'estimated_fee': estimated_fee,
        })

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        generate_all = client_id == 'all'

        for ep in entity_packages:
            if not generate_all and str(ep['client'].id) != client_id:
                continue
            # Generate invoice for the package
            inv = Invoice.objects.create(
                client=ep['client'],
                description=f'Annual Corporate Maintenance Package — {date.today().year}\nIncludes: resolutions, minute book updates, filings review',
                service_type='annual_maintenance',
                amount=ep['estimated_fee'],
                status='sent',
                invoice_date=date.today(),
                due_date=date.today() + timedelta(days=30),
            )
            log_activity(ep['client'], f'Annual package generated: ${ep["estimated_fee"]:.2f}', request.user)

        count = len(entity_packages) if generate_all else 1
        messages.success(request, f'Annual packages generated for {count} entities.')

        if client_id and not generate_all:
            return redirect('client_detail', client_id=int(client_id))
        return redirect('financial_dashboard')

    return render(request, 'clients/annual_package.html', {
        'firm': firm, 'entity_packages': entity_packages, 'today': date.today(),
        'client_filter': client_id is not None,
    })
