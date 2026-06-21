"""CSV import for bulk client creation."""
import csv
import io
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ..models import Client, log_activity
from ._helpers import _get_firm, create_client_login_and_send_email
from ..emails import send_client_invitation


@login_required
def csv_import_clients(request):
    firm = _get_firm(request.user)
    if not firm:
        return redirect('dashboard')

    results = {'created': 0, 'skipped': 0, 'errors': []}
    preview_rows = []
    columns = []

    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        try:
            data = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(data))
            columns = reader.fieldnames or []

            for i, row in enumerate(reader):
                name = row.get('name', '').strip() or row.get('Name', '').strip()
                email = row.get('email', '').strip() or row.get('Email', '').strip()

                if not name or not email:
                    results['errors'].append(f'Row {i+2}: missing name or email')
                    results['skipped'] += 1
                    continue

                if Client.objects.filter(email=email, firm=firm).exists():
                    results['errors'].append(f'Row {i+2}: {email} already exists in your firm')
                    results['skipped'] += 1
                    continue

                client = Client.objects.create(
                    firm=firm,
                    name=name,
                    email=email,
                    phone=row.get('phone', '').strip() or row.get('Phone', '').strip() or '',
                    business_type=row.get('business_type', '').strip() or row.get('Business Type', '').strip() or '',
                    client_type=row.get('client_type', 'individual').strip() or 'individual',
                )
                try:
                    create_client_login_and_send_email(client)
                    send_client_invitation(client)
                except Exception:
                    pass

                preview_rows.append({'name': name, 'email': email})
                results['created'] += 1

            if results['created'] > 0:
                log_activity(request.user, 'create', 'Client', None, f'{results["created"]} clients',
                            f'CSV imported {results["created"]} clients', firm=firm)
                messages.success(request, f'{results["created"]} clients created successfully.')

        except Exception as e:
            messages.error(request, f'Error reading CSV: {e}')

    return render(request, 'clients/csv_import.html', {
        'firm': firm,
        'results': results,
        'preview_rows': preview_rows,
        'columns': columns,
    })
