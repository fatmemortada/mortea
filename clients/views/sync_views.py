"""QBO/Xero Sync views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from django.http import JsonResponse
from datetime import date, timedelta

from ..models import (
    Client, Invoice, PaymentRecord, AccountingConnection,
    EntityAccountMapping, SyncLog, log_activity,
)
from ._helpers import _get_firm


@login_required
def sync_dashboard(request):
    """Accounting sync dashboard — QBO and Xero connections."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    connections = AccountingConnection.objects.filter(firm=firm)
    qbo = connections.filter(platform='qbo').first()
    xero = connections.filter(platform='xero').first()

    # Entity mappings
    mappings = EntityAccountMapping.objects.filter(
        connection__firm=firm
    ).select_related('client', 'connection')

    # Recent sync logs
    logs = SyncLog.objects.filter(
        connection__firm=firm
    ).order_by('-started_at')[:20]

    # Unsynced entities
    unmapped = Client.objects.filter(firm=firm).exclude(
        id__in=mappings.values_list('client_id', flat=True)
    )

    # Stats
    total_synced_invoices = mappings.aggregate(total=Sum('invoices_synced'))['total'] or 0
    total_synced_payments = mappings.aggregate(total=Sum('payments_synced'))['total'] or 0

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'connect_qbo':
            # In production: redirect to QBO OAuth flow
            # For now: create connection record
            conn, created = AccountingConnection.objects.get_or_create(
                firm=firm, platform='qbo',
                defaults={'status': 'connected', 'access_token': 'simulated',
                          'refresh_token': 'simulated', 'realm_id': request.POST.get('realm_id', '')},
            )
            if not created:
                conn.status = 'connected'
                conn.save()
            messages.success(request, 'Connected to QuickBooks Online!')

        elif action == 'connect_xero':
            conn, created = AccountingConnection.objects.get_or_create(
                firm=firm, platform='xero',
                defaults={'status': 'connected', 'access_token': 'simulated',
                          'refresh_token': 'simulated', 'realm_id': request.POST.get('tenant_id', '')},
            )
            if not created:
                conn.status = 'connected'
                conn.save()
            messages.success(request, 'Connected to Xero!')

        elif action == 'map_entity':
            conn_id = request.POST.get('connection_id')
            client_id = request.POST.get('client_id')
            external_id = request.POST.get('external_customer_id', '').strip()

            conn = get_object_or_404(AccountingConnection, id=conn_id, firm=firm)
            client = get_object_or_404(Client, id=client_id, firm=firm)

            mapping, created = EntityAccountMapping.objects.get_or_create(
                connection=conn, client=client,
                defaults={'external_customer_id': external_id, 'sync_status': 'pending'},
            )
            if not created:
                mapping.external_customer_id = external_id
                mapping.save()

            messages.success(request, f'{client.name} mapped to {conn.get_platform_display()}.')

        elif action == 'sync_now':
            conn_id = request.POST.get('connection_id')
            entity_type = request.POST.get('entity_type', 'all')
            conn = get_object_or_404(AccountingConnection, id=conn_id, firm=firm)

            # Simulate sync
            import time
            start = time.time()

            # Export invoices
            synced = 0
            if entity_type in ('all', 'invoices'):
                unmapped_invoices = Invoice.objects.filter(
                    client__firm=firm, status='sent',
                ).exclude(
                    client__accounting_mapping__isnull=False,
                    client__accounting_mapping__last_invoice_sync__gte=timezone.now() - timedelta(hours=1),
                )
                synced = unmapped_invoices.count()

            log = SyncLog.objects.create(
                connection=conn, status='success', direction='export',
                entity_type=entity_type, records_processed=synced,
                records_created=synced,
                duration_ms=int((time.time() - start) * 1000),
                completed_at=timezone.now(),
            )
            conn.last_synced_at = timezone.now()
            conn.save()

            messages.success(request, f'Sync complete: {synced} records processed.')

        elif action == 'disconnect':
            conn_id = request.POST.get('connection_id')
            conn = get_object_or_404(AccountingConnection, id=conn_id, firm=firm)
            conn.status = 'disconnected'
            conn.access_token = ''
            conn.refresh_token = ''
            conn.save()
            messages.warning(request, f'Disconnected from {conn.get_platform_display()}.')

        return redirect('sync_dashboard')

    return render(request, 'clients/sync_dashboard.html', {
        'firm': firm, 'qbo': qbo, 'xero': xero,
        'mappings': mappings, 'logs': logs, 'unmapped': unmapped,
        'total_synced_invoices': total_synced_invoices,
        'total_synced_payments': total_synced_payments,
    })
