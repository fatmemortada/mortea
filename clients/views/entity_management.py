"""
Athennian-parity views: cap table & share classes, appointments,
multi-jurisdiction registrations, people/KYC registry, reports center.
"""
import csv
from datetime import date, timedelta
from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum

from ..models import (
    Client, Director, Shareholder, UBORecord, ShareTransaction,
    ShareClass, Appointment, EntityRegistration, Person, CorporateProfile,
    log_activity,
)
from ._helpers import _get_firm, _csv_response


# ── Cap Table & Share Classes ───────────────────────────────────────────────

def _build_cap_table(client):
    """Group shareholders by share class with % of class and % of total."""
    shareholders = list(client.shareholders.all().order_by('share_class', 'full_name'))
    total_shares = sum(s.num_shares for s in shareholders) or 0
    classes = defaultdict(list)
    for s in shareholders:
        classes[s.share_class or 'Common'].append(s)

    declared = {c.name: c for c in client.share_classes.all()}
    rows = []
    for class_name in sorted(classes):
        holders = classes[class_name]
        class_total = sum(h.num_shares for h in holders) or 0
        share_class = declared.get(class_name)
        rows.append({
            'name': class_name,
            'share_class': share_class,
            'issued': class_total,
            'pct_of_total': round(class_total / total_shares * 100, 2) if total_shares else 0,
            'holders': [{
                'shareholder': h,
                'pct_of_class': round(h.num_shares / class_total * 100, 2) if class_total else 0,
                'pct_of_total': round(h.num_shares / total_shares * 100, 2) if total_shares else 0,
            } for h in holders],
        })
    return rows, total_shares


@login_required
def cap_table_view(request, client_id):
    """Full cap table: authorized share classes + issued holdings with ownership %."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_class':
            name = request.POST.get('name', '').strip()
            if name and not client.share_classes.filter(name=name).exists():
                ShareClass.objects.create(
                    client=client, name=name,
                    class_type=request.POST.get('class_type', 'common'),
                    voting=request.POST.get('voting') == 'on',
                    votes_per_share=int(request.POST.get('votes_per_share') or 1),
                    authorized_shares=request.POST.get('authorized_shares') or None,
                    par_value=request.POST.get('par_value') or None,
                    rights_restrictions=request.POST.get('rights_restrictions', '').strip(),
                )
                log_activity(request.user, 'create', 'ShareClass', None, name,
                             f'Added share class {name} for {client.name}', firm=firm)
        elif action == 'delete_class':
            ShareClass.objects.filter(id=request.POST.get('class_id'), client=client).delete()
        return redirect('cap_table', client_id=client_id)

    cap_rows, total_shares = _build_cap_table(client)
    share_classes = client.share_classes.all()
    transactions = client.share_transactions.select_related('shareholder_from', 'shareholder_to')[:20]

    if request.GET.get('export') == 'csv':
        response = _csv_response(f'cap_table_{client.client_token or client.id}')
        writer = csv.writer(response)
        writer.writerow(['Share Class', 'Shareholder', 'Shares', '% of Class', '% of Total'])
        for row in cap_rows:
            for h in row['holders']:
                writer.writerow([row['name'], h['shareholder'].full_name,
                                 h['shareholder'].num_shares, h['pct_of_class'], h['pct_of_total']])
        return response

    return render(request, 'clients/cap_table.html', {
        'firm': firm, 'client': client, 'cap_rows': cap_rows,
        'total_shares': total_shares, 'share_classes': share_classes,
        'transactions': transactions,
    })


# ── Appointments (D&O and beyond) ───────────────────────────────────────────

@login_required
def appointments_view(request, client_id):
    """Manage officer, power of attorney, signing authority and agent appointments."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_appointment':
            name = request.POST.get('person_name', '').strip()
            if name:
                Appointment.objects.create(
                    client=client, person_name=name,
                    role=request.POST.get('role', 'officer'),
                    title=request.POST.get('title', '').strip(),
                    granted_by=request.POST.get('granted_by', '').strip(),
                    start_date=request.POST.get('start_date') or None,
                    notes=request.POST.get('notes', '').strip(),
                )
                log_activity(request.user, 'create', 'Appointment', None, name,
                             f'Appointed {name} for {client.name}', firm=firm)
        elif action == 'end_appointment':
            Appointment.objects.filter(id=request.POST.get('appointment_id'), client=client)\
                .update(end_date=request.POST.get('end_date') or date.today())
        elif action == 'delete_appointment':
            Appointment.objects.filter(id=request.POST.get('appointment_id'), client=client).delete()
        return redirect('appointments', client_id=client_id)

    appointments = client.appointments.all()
    active = [a for a in appointments if a.is_active]
    ended = [a for a in appointments if not a.is_active]

    return render(request, 'clients/appointments.html', {
        'firm': firm, 'client': client,
        'active_appointments': active, 'ended_appointments': ended,
        'role_choices': Appointment.ROLE_CHOICES,
    })


# ── Multi-Jurisdiction Registrations ────────────────────────────────────────

@login_required
def registrations_view(request, client_id):
    """Track home, extra-provincial and foreign registrations with renewal dates."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    today = date.today()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_registration':
            jurisdiction = request.POST.get('jurisdiction', '').strip()
            if jurisdiction:
                EntityRegistration.objects.create(
                    client=client, jurisdiction=jurisdiction,
                    registration_type=request.POST.get('registration_type', 'extra_provincial'),
                    registration_number=request.POST.get('registration_number', '').strip(),
                    agent_name=request.POST.get('agent_name', '').strip(),
                    registered_date=request.POST.get('registered_date') or None,
                    renewal_date=request.POST.get('renewal_date') or None,
                    status=request.POST.get('status', 'active'),
                    notes=request.POST.get('notes', '').strip(),
                )
                log_activity(request.user, 'create', 'EntityRegistration', None, jurisdiction,
                             f'Registered {client.name} in {jurisdiction}', firm=firm)
        elif action == 'set_status':
            EntityRegistration.objects.filter(id=request.POST.get('registration_id'), client=client)\
                .update(status=request.POST.get('status', 'active'))
        elif action == 'delete_registration':
            EntityRegistration.objects.filter(id=request.POST.get('registration_id'), client=client).delete()
        return redirect('registrations', client_id=client_id)

    registrations = client.registrations.all()
    renewal_cutoff = today + timedelta(days=90)
    upcoming_renewals = [r for r in registrations
                         if r.renewal_date and r.status == 'active' and r.renewal_date <= renewal_cutoff]

    return render(request, 'clients/registrations.html', {
        'firm': firm, 'client': client, 'registrations': registrations,
        'upcoming_renewals': upcoming_renewals, 'today': today,
        'type_choices': EntityRegistration.REGISTRATION_TYPE_CHOICES,
        'status_choices': EntityRegistration.STATUS_CHOICES,
    })


# ── People / KYC Registry ───────────────────────────────────────────────────

def _person_roles(firm, full_name):
    """All roles a person holds across the firm's entities, matched by name."""
    roles = []
    for d in Director.objects.filter(client__firm=firm, full_name__iexact=full_name).select_related('client'):
        label = f'Officer — {d.officer_title}' if d.is_officer and d.officer_title else 'Director'
        roles.append({'entity': d.client, 'role': label, 'active': d.is_active})
    for s in Shareholder.objects.filter(client__firm=firm, full_name__iexact=full_name).select_related('client'):
        roles.append({'entity': s.client, 'role': f'Shareholder — {s.num_shares} {s.share_class}', 'active': True})
    for u in UBORecord.objects.filter(client__firm=firm, full_name__iexact=full_name).select_related('client'):
        roles.append({'entity': u.client, 'role': f'UBO — {u.ownership_percentage}%', 'active': True})
    for a in Appointment.objects.filter(client__firm=firm, person_name__iexact=full_name).select_related('client'):
        roles.append({'entity': a.client, 'role': a.title or a.get_role_display(), 'active': a.is_active})
    return roles


@login_required
def people_view(request):
    """Firm-wide people registry with KYC status and cross-entity roles."""
    firm = _get_firm(request.user)
    today = date.today()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_person':
            name = request.POST.get('full_name', '').strip()
            if name and not Person.objects.filter(firm=firm, full_name__iexact=name).exists():
                Person.objects.create(
                    firm=firm, full_name=name,
                    email=request.POST.get('email', '').strip(),
                    phone=request.POST.get('phone', '').strip(),
                    address=request.POST.get('address', '').strip(),
                    date_of_birth=request.POST.get('date_of_birth') or None,
                    citizenship=request.POST.get('citizenship', '').strip(),
                    residency=request.POST.get('residency', '').strip(),
                    id_type=request.POST.get('id_type', ''),
                )
                log_activity(request.user, 'create', 'Person', None, name,
                             f'Added {name} to people registry', firm=firm)
        elif action == 'set_kyc':
            status = request.POST.get('kyc_status', 'pending')
            Person.objects.filter(id=request.POST.get('person_id'), firm=firm).update(
                kyc_status=status,
                kyc_verified_date=today if status == 'verified' else None,
            )
        elif action == 'delete_person':
            Person.objects.filter(id=request.POST.get('person_id'), firm=firm).delete()
        elif action == 'sync_from_records':
            # Pull distinct names from directors/shareholders/appointments into the registry
            existing = {p.full_name.lower() for p in Person.objects.filter(firm=firm)}
            names = set()
            names.update(Director.objects.filter(client__firm=firm).values_list('full_name', flat=True))
            names.update(Shareholder.objects.filter(client__firm=firm).values_list('full_name', flat=True))
            names.update(Appointment.objects.filter(client__firm=firm).values_list('person_name', flat=True))
            created = 0
            for name in names:
                name = name.strip()
                if name and name.lower() not in existing:
                    Person.objects.create(firm=firm, full_name=name)
                    existing.add(name.lower())
                    created += 1
            if created:
                log_activity(request.user, 'create', 'Person', None, '',
                             f'Synced {created} people from corporate records', firm=firm)
        return redirect('people')

    query = request.GET.get('q', '').strip()
    people = Person.objects.filter(firm=firm)
    if query:
        people = people.filter(full_name__icontains=query)

    people_rows = [{'person': p, 'roles': _person_roles(firm, p.full_name)} for p in people]
    kyc_counts = {
        'verified': sum(1 for r in people_rows if r['person'].kyc_status == 'verified'),
        'pending': sum(1 for r in people_rows if r['person'].kyc_status == 'pending'),
        'missing': sum(1 for r in people_rows if r['person'].kyc_status in ('not_started', 'expired')),
    }

    return render(request, 'clients/people.html', {
        'firm': firm, 'people_rows': people_rows, 'query': query,
        'kyc_counts': kyc_counts, 'today': today,
        'kyc_choices': Person.KYC_STATUS_CHOICES,
        'id_choices': Person.ID_TYPE_CHOICES,
    })


# ── Reports Center ──────────────────────────────────────────────────────────

REPORTS = {
    'directors':     'All Directors',
    'officers':      'All Officers',
    'shareholders':  'All Shareholders',
    'cap_tables':    'Cap Table Summary',
    'registrations': 'Registrations & Renewals',
    'appointments':  'Appointments',
    'ubo':           'UBO Summary',
    'kyc':           'People & KYC Status',
    'entities':      'Entities by Jurisdiction',
}


def _report_rows(report, firm):
    """Return (headers, rows) for a firm-wide report."""
    today = date.today()
    if report == 'directors':
        headers = ['Entity', 'Director', 'Appointed', 'Resigned', 'Address']
        rows = [[d.client.name, d.full_name,
                 d.appointment_date or '', d.resignation_date or '', d.address]
                for d in Director.objects.filter(client__firm=firm).select_related('client').order_by('client__name', 'full_name')]
    elif report == 'officers':
        headers = ['Entity', 'Officer', 'Title', 'Appointed']
        rows = [[d.client.name, d.full_name, d.officer_title, d.appointment_date or '']
                for d in Director.objects.filter(client__firm=firm, is_officer=True).select_related('client').order_by('client__name')]
    elif report == 'shareholders':
        headers = ['Entity', 'Shareholder', 'Class', 'Shares', 'Acquired']
        rows = [[s.client.name, s.full_name, s.share_class, s.num_shares, s.acquisition_date or '']
                for s in Shareholder.objects.filter(client__firm=firm).select_related('client').order_by('client__name', 'full_name')]
    elif report == 'cap_tables':
        headers = ['Entity', 'Total Issued Shares', 'Shareholders', 'Share Classes']
        rows = []
        for c in Client.objects.filter(firm=firm).prefetch_related('shareholders'):
            shareholders = list(c.shareholders.all())
            if shareholders:
                rows.append([c.name, sum(s.num_shares for s in shareholders),
                             len(shareholders), len({s.share_class for s in shareholders})])
    elif report == 'registrations':
        headers = ['Entity', 'Jurisdiction', 'Type', 'Number', 'Status', 'Renewal Date', 'Days to Renewal']
        rows = [[r.client.name, r.jurisdiction, r.get_registration_type_display(),
                 r.registration_number, r.get_status_display(), r.renewal_date or '',
                 (r.renewal_date - today).days if r.renewal_date else '']
                for r in EntityRegistration.objects.filter(client__firm=firm).select_related('client').order_by('renewal_date')]
    elif report == 'appointments':
        headers = ['Entity', 'Person', 'Role', 'Title', 'Start', 'End']
        rows = [[a.client.name, a.person_name, a.get_role_display(), a.title,
                 a.start_date or '', a.end_date or '']
                for a in Appointment.objects.filter(client__firm=firm).select_related('client').order_by('client__name')]
    elif report == 'ubo':
        headers = ['Entity', 'UBO', 'Ownership %', 'Control', 'Residence', 'Last Verified']
        rows = [[u.client.name, u.full_name, u.ownership_percentage, u.get_control_type_display(),
                 u.jurisdiction_of_residence, u.last_verified_at or '']
                for u in UBORecord.objects.filter(client__firm=firm).select_related('client').order_by('client__name')]
    elif report == 'kyc':
        headers = ['Person', 'KYC Status', 'Verified Date', 'ID Type', 'Citizenship', 'Residence']
        rows = [[p.full_name, p.get_kyc_status_display(), p.kyc_verified_date or '',
                 p.get_id_type_display() if p.id_type else '', p.citizenship, p.residency]
                for p in Person.objects.filter(firm=firm)]
    else:  # entities
        headers = ['Entity', 'Jurisdiction', 'Status', 'Incorporated', 'Business Number', 'Annual Return Due']
        rows = [[p.client.name, p.get_jurisdiction_display() if p.jurisdiction else '',
                 p.get_status_display(), p.incorporation_date or '', p.business_number, p.annual_return_due or '']
                for p in CorporateProfile.objects.filter(client__firm=firm).select_related('client').order_by('client__name')]
    return headers, rows


@login_required
def reports_center_view(request):
    """Cross-entity reports with one-click CSV export — Athennian-style reporting."""
    firm = _get_firm(request.user)
    report = request.GET.get('report', 'directors')
    if report not in REPORTS:
        report = 'directors'

    headers, rows = _report_rows(report, firm)

    if request.GET.get('export') == 'csv':
        response = _csv_response(f'report_{report}')
        writer = csv.writer(response)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        log_activity(request.user, 'export', 'Report', None, report,
                     f'Exported {REPORTS[report]} report', firm=firm)
        return response

    return render(request, 'clients/reports_center.html', {
        'firm': firm, 'reports': REPORTS, 'current_report': report,
        'current_label': REPORTS[report], 'headers': headers, 'rows': rows,
    })


@login_required
def entity_overview(request, client_id):
    """Single-page entity dashboard — everything an accountant needs at a glance."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    profile = getattr(client, 'corporate_profile', None)

    # Health score (reuse existing helper)
    from ._helpers import compute_health_score
    health = compute_health_score(client)

    # Key stats
    directors = client.directors.all()
    shareholders = client.shareholders.all()
    appointments = client.appointments.all()
    registrations = client.registrations.all()
    ubo_count = UBORecord.objects.filter(client=client).count()
    share_classes = ShareClass.objects.filter(client=client)

    # Documents
    onboarding_docs = client.onboarding_documents.all()
    minute_book_docs = client.minute_book_documents.all()
    total_docs = onboarding_docs.count() + minute_book_docs.count()

    # Compliance
    from ..models import ComplianceTask
    tasks = ComplianceTask.objects.filter(client=client).order_by('due_date')
    overdue_tasks = [t for t in tasks if t.status == 'overdue']
    upcoming_tasks = [t for t in tasks if t.status in ('pending', 'in_progress')][:10]
    completed_tasks = sum(1 for t in tasks if t.status == 'completed')
    total_tasks = len(tasks)

    # Invoices
    invoices = client.invoices.all().order_by('-invoice_date')
    total_billed = sum(i.amount for i in invoices)
    outstanding = sum(i.amount for i in invoices if i.status in ('sent', 'overdue'))

    # Key dates
    key_dates = []
    if profile:
        if profile.incorporation_date:
            key_dates.append(('Incorporated', profile.incorporation_date))
        if profile.fiscal_year_end:
            key_dates.append(('Fiscal Year End', profile.fiscal_year_end))
        # Annual return due — 60 days after incorporation anniversary in most jurisdictions
        if profile.incorporation_date:
            this_year = date.today().year
            anniv = date(this_year, profile.incorporation_date.month, profile.incorporation_date.day)
            key_dates.append(('Annual Return Due', anniv + timedelta(days=60)))

    # Appointments expiring soon
    expiring_appointments = [
        a for a in appointments
        if a.term_end_date and a.term_end_date <= date.today() + timedelta(days=90)
    ]

    # Recent activity
    from ..models import ActivityLog
    recent_activity = ActivityLog.objects.filter(
        client_id=client.id
    ).order_by('-timestamp')[:20]

    # Missing items for onboarding completeness
    from ._helpers import _get_missing_items
    missing = _get_missing_items(client)
    completeness = 100 - (len(missing) * 11) if missing else 100  # 9 items ≈ 11% each
    completeness = max(0, min(100, completeness))

    return render(request, 'clients/entity_overview.html', {
        'firm': firm, 'client': client, 'profile': profile,
        'health': health,
        'directors': directors, 'shareholders': shareholders,
        'appointments': appointments, 'registrations': registrations,
        'ubo_count': ubo_count, 'share_classes': share_classes,
        'total_docs': total_docs,
        'overdue_tasks': overdue_tasks, 'upcoming_tasks': upcoming_tasks,
        'completed_tasks': completed_tasks, 'total_tasks': total_tasks,
        'invoices': invoices[:5], 'total_billed': total_billed,
        'outstanding': outstanding,
        'key_dates': key_dates, 'expiring_appointments': expiring_appointments,
        'recent_activity': recent_activity,
        'completeness': completeness, 'missing_items': missing,
    })


@login_required
def org_chart_view(request, client_id):
    """Interactive D3.js org chart showing entity structure."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    profile = getattr(client, 'corporate_profile', None)

    return render(request, 'clients/org_chart.html', {
        'firm': firm, 'client': client, 'profile': profile,
        'directors': client.directors.all(),
        'shareholders': client.shareholders.all(),
        'appointments': client.appointments.all(),
        'registrations': client.registrations.all(),
        'share_classes': ShareClass.objects.filter(client=client),
    })
