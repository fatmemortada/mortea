"""Advanced CSV Import/Export for all models."""
import csv, io
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db import models as dj_models

from ..models import (
    Client, CorporateProfile, Director, Shareholder, ComplianceTask,
    Invoice, EntitySubscription, SubscriptionPlan, TimeEntry,
    DividendDeclaration, IncorporationProject, RiskFinding,
)
from ._helpers import _get_firm


EXPORT_REGISTRY = {
    'clients': {
        'model': Client, 'label': 'Clients',
        'fields': ['id', 'name', 'email', 'phone', 'business_type', 'client_type', 'status', 'language', 'created_at'],
        'related': {'firm': 'firm_id'},
    },
    'corporate_profiles': {
        'model': CorporateProfile, 'label': 'Corporate Profiles',
        'fields': ['id', 'client_id', 'jurisdiction', 'incorporation_date', 'status', 'business_number', 'hst_number', 'fiscal_year_end', 'registered_address'],
    },
    'directors': {
        'model': Director, 'label': 'Directors',
        'fields': ['id', 'client_id', 'full_name', 'address', 'appointment_date', 'resignation_date', 'is_officer', 'officer_title'],
    },
    'shareholders': {
        'model': Shareholder, 'label': 'Shareholders',
        'fields': ['id', 'client_id', 'full_name', 'address', 'share_class', 'num_shares', 'acquisition_date'],
    },
    'compliance_tasks': {
        'model': ComplianceTask, 'label': 'Compliance Tasks',
        'fields': ['id', 'client_id', 'task_type', 'title', 'description', 'due_date', 'status', 'notes', 'created_at'],
    },
    'invoices': {
        'model': Invoice, 'label': 'Invoices',
        'fields': ['id', 'client_id', 'invoice_number', 'description', 'service_type', 'amount', 'tax_amount', 'total_amount', 'status', 'invoice_date', 'due_date', 'paid_date', 'created_at'],
    },
    'subscriptions': {
        'model': EntitySubscription, 'label': 'Subscriptions',
        'fields': ['id', 'client_id', 'plan_id', 'status', 'billing_cycle', 'current_period_start', 'current_period_end', 'next_billing_date', 'auto_renew', 'created_at'],
    },
    'time_entries': {
        'model': TimeEntry, 'label': 'Time Entries',
        'fields': ['id', 'client_id', 'user_id', 'description', 'date', 'hours', 'hourly_rate', 'amount', 'category', 'billing_status', 'created_at'],
    },
    'dividends': {
        'model': DividendDeclaration, 'label': 'Dividends',
        'fields': ['id', 'client_id', 'dividend_type', 'total_amount', 'declaration_date', 'payment_date', 'fiscal_year', 'status', 'created_at'],
    },
    'incorporations': {
        'model': IncorporationProject, 'label': 'Incorporations',
        'fields': ['id', 'client_id', 'jurisdiction', 'structure_type', 'current_step', 'fixed_fee', 'disbursements', 'created_at', 'completed_at'],
    },
}


@login_required
def csv_export_center(request):
    """Export center — download CSV for any registered model."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if request.method == 'POST':
        export_type = request.POST.get('export_type')
        config = EXPORT_REGISTRY.get(export_type)
        if not config:
            messages.error(request, 'Invalid export type.')
            return redirect('csv_export_center')

        # Build queryset filtered by firm
        model = config['model']
        fields = config['fields']
        queryset = model.objects.all()

        # Apply firm filter based on model
        if hasattr(model, 'firm_id') or 'firm' in [f.name for f in model._meta.get_fields()]:
            try:
                firm_field = model._meta.get_field('firm')
                if firm_field and hasattr(firm_field, 'remote_field'):
                    queryset = queryset.filter(firm=firm)
            except Exception:
                pass  # model doesn't have a 'firm' FK field
        # Filter by client__firm for models with client FK
        if 'client_id' in fields:
            queryset = queryset.filter(client__firm=firm)
        elif export_type == 'subscriptions':
            queryset = queryset.filter(firm=firm)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{export_type}_{__import__("django").utils.timezone.now().strftime("%Y%m%d")}.csv"'
        response.write('﻿')  # UTF-8 BOM

        writer = csv.writer(response)
        writer.writerow(fields)

        for obj in queryset[:10000]:
            row = []
            for f in fields:
                val = getattr(obj, f, '')
                if val is None:
                    val = ''
                elif hasattr(val, 'isoformat'):
                    val = val.isoformat()
                elif isinstance(val, (dict, list)):
                    val = str(val)
                row.append(str(val))
            writer.writerow(row)

        return response

    return render(request, 'clients/csv_export_center.html', {
        'firm': firm, 'registry': EXPORT_REGISTRY,
    })


@login_required
def csv_import_center(request):
    """Import center — upload CSV to create/update records."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if request.method == 'POST' and request.FILES.get('csv_file'):
        import_type = request.POST.get('import_type')
        config = EXPORT_REGISTRY.get(import_type)
        if not config:
            messages.error(request, 'Invalid import type.')
            return redirect('csv_import_center')

        csv_file = request.FILES['csv_file']
        dry_run = request.POST.get('dry_run') == '1'

        try:
            decoded = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))
            rows = list(reader)
        except Exception as e:
            messages.error(request, f'CSV parse error: {e}')
            return redirect('csv_import_center')

        created = 0
        updated = 0
        errors = []
        preview_rows = []

        for i, row in enumerate(rows):
            try:
                row_data = {}
                for f in config['fields']:
                    if f in row and f != 'id':
                        val = row[f].strip()
                        if val == '':
                            row_data[f] = None
                        else:
                            row_data[f] = val

                # Auto-assign firm
                if import_type == 'clients':
                    row_data['firm'] = firm
                    obj, is_new = Client.objects.update_or_create(
                        email=row_data.get('email', ''), firm=firm,
                        defaults=row_data,
                    )
                elif import_type in ('directors', 'shareholders', 'compliance_tasks', 'invoices'):
                    # Require client_id
                    client_id = row_data.get('client_id')
                    if client_id:
                        client = Client.objects.filter(id=client_id, firm=firm).first()
                        if client:
                            row_data['client'] = client
                            if 'client_id' in row_data:
                                del row_data['client_id']
                            obj = config['model'].objects.create(**{k: v for k, v in row_data.items() if k in config['fields'] and v is not None})
                            is_new = True
                        else:
                            errors.append(f'Row {i+1}: Client {client_id} not found')
                            continue
                    else:
                        errors.append(f'Row {i+1}: client_id required')
                        continue
                else:
                    continue

                if is_new:
                    created += 1
                else:
                    updated += 1

                if dry_run:
                    preview_rows.append({**row, '_action': 'CREATE' if is_new else 'UPDATE'})

            except Exception as e:
                errors.append(f'Row {i+1}: {str(e)}')

        if dry_run:
            return render(request, 'clients/csv_import_preview.html', {
                'firm': firm, 'import_type': import_type, 'preview_rows': preview_rows,
                'created': created, 'updated': updated, 'errors': errors, 'total': len(rows),
            })

        messages.success(request, f'Import complete: {created} created, {updated} updated, {len(errors)} errors.')
        if errors:
            for err in errors[:10]:
                messages.warning(request, err)

        return redirect('csv_import_center')

    return render(request, 'clients/csv_import_center.html', {
        'firm': firm, 'registry': EXPORT_REGISTRY,
    })
