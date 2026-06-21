"""
Deadline Engine + Minute Book Health Check.

Jurisdiction-aware deadline tracking across:
- Federal (CBCA): annual returns, AGM, director changes
- Ontario (OBCA): annual returns, notices of change
- Québec (LSAQ): déclaration annuelle, mise à jour
- BC (BCA): annual reports, transparency register

Plus minute book health scanning: missing resolutions, registers, consents.
"""
from datetime import date, timedelta
from django.utils import timezone


# ── JURISDICTION DEADLINE RULES ────────────────────────────────────

JURISDICTION_DEADLINES = {
    'federal': {
        'name': 'Federal (CBCA)',
        'agency': 'Corporations Canada',
        'deadlines': [
            {'id': 'annual_return', 'name': 'Annual Return',
             'due': 'anniversary', 'period_days': 60,
             'fee': '$12 (online)', 'penalty': 'Dissolution after 2 years of non-filing'},
            {'id': 'director_change', 'name': 'Notice of Change — Directors',
             'due': 'within_15_days', 'period_days': 15,
             'fee': 'Free', 'penalty': 'Potential fines'},
            {'id': 'address_change', 'name': 'Notice of Change — Registered Office',
             'due': 'within_15_days', 'period_days': 15,
             'fee': 'Free', 'penalty': 'Potential fines'},
            {'id': 'agm', 'name': 'Annual General Meeting',
             'due': 'within_18_months', 'period_days': 540,
             'fee': 'N/A', 'penalty': 'Non-compliance'},
        ],
    },
    'ontario': {
        'name': 'Ontario (OBCA)',
        'agency': 'Ontario Business Registry (OBR)',
        'deadlines': [
            {'id': 'annual_return', 'name': 'Annual Return',
             'due': 'within_6_months_fye', 'period_days': 180,
             'fee': 'Varies', 'penalty': 'Cancellation of registration'},
            {'id': 'director_change', 'name': 'Notice of Change — Directors',
             'due': 'within_15_days', 'period_days': 15,
             'fee': 'Free', 'penalty': 'Potential fines'},
            {'id': 'tax_filing', 'name': 'Ontario Corporate Tax Return',
             'due': 'within_6_months_fye', 'period_days': 180,
             'fee': 'N/A', 'penalty': 'Late-filing penalties'},
        ],
    },
    'bc': {
        'name': 'British Columbia (BCA)',
        'agency': 'BC Registries',
        'deadlines': [
            {'id': 'annual_report', 'name': 'Annual Report',
             'due': 'anniversary', 'period_days': 60,
             'fee': '$43.39', 'penalty': '$25 late fee; potential strike-off'},
            {'id': 'transparency_register', 'name': 'Transparency Register Update',
             'due': 'annually', 'period_days': 365,
             'fee': 'Free', 'penalty': 'Significant fines for non-compliance'},
            {'id': 'director_change', 'name': 'Director Change Filing',
             'due': 'within_15_days', 'period_days': 15,
             'fee': 'Free', 'penalty': 'Potential fines'},
        ],
    },
    'quebec': {
        'name': 'Québec (LSAQ)',
        'agency': 'Registraire des entreprises (REQ)',
        'deadlines': [
            {'id': 'declaration_annuelle', 'name': 'Déclaration Annuelle',
             'due': 'within_3_months_fye', 'period_days': 90,
             'fee': '$37', 'penalty': 'Potential dissolution'},
            {'id': 'mise_a_jour', 'name': 'Mise à jour (Update)',
             'due': 'within_30_days_change', 'period_days': 30,
             'fee': 'Free', 'penalty': 'Potential fines'},
            {'id': 'director_change', 'name': 'Changement — Administrateurs',
             'due': 'within_30_days', 'period_days': 30,
             'fee': 'Free', 'penalty': 'Potential fines'},
        ],
    },
}


def calculate_entity_deadlines(client):
    """Calculate all upcoming deadlines for an entity based on jurisdiction."""
    from .models import CorporateProfile, ComplianceTask

    today = timezone.now().date()
    cp = getattr(client, 'corporate_profile', None)
    if not cp or not cp.jurisdiction:
        return []

    jurisdiction = cp.jurisdiction
    rules = JURISDICTION_DEADLINES.get(jurisdiction, JURISDICTION_DEADLINES['federal'])
    deadlines = []

    for rule in rules['deadlines']:
        due_date = None
        days_remaining = None

        if rule['due'] == 'anniversary' and cp.incorporation_date:
            try:
                anniversary = cp.incorporation_date.replace(year=today.year)
                if anniversary < today:
                    anniversary = cp.incorporation_date.replace(year=today.year + 1)
            except ValueError:
                anniversary = cp.incorporation_date.replace(year=today.year, day=28) if cp.incorporation_date.day == 29 else today
            due_date = anniversary
            days_remaining = (due_date - today).days

        elif rule['due'] == 'within_15_days':
            # Check if there was a recent change that triggers this
            recent_changes = ComplianceTask.objects.filter(
                client=client, task_type__in=['director_change', 'address_change'],
                created_at__gte=today - timedelta(days=15),
            )
            if recent_changes.exists():
                due_date = recent_changes.first().created_at.date() + timedelta(days=15)
                days_remaining = (due_date - today).days

        elif rule['due'] == 'within_6_months_fye' and cp.fiscal_year_end:
            try:
                fye = cp.fiscal_year_end.replace(year=today.year)
                if fye < today:
                    fye = cp.fiscal_year_end.replace(year=today.year + 1)
            except ValueError:
                fye = today + timedelta(days=180)
            due_date = fye + timedelta(days=180)
            days_remaining = (due_date - today).days

        elif rule['due'] == 'annually':
            due_date = today + timedelta(days=365)
            days_remaining = 365

        elif rule['due'] == 'within_3_months_fye' and cp.fiscal_year_end:
            try:
                fye = cp.fiscal_year_end.replace(year=today.year)
                if fye < today:
                    fye = cp.fiscal_year_end.replace(year=today.year + 1)
            except ValueError:
                fye = today + timedelta(days=90)
            due_date = fye + timedelta(days=90)
            days_remaining = (due_date - today).days

        if due_date and days_remaining is not None and 0 <= days_remaining <= 180:
            urgency = 'overdue' if days_remaining <= 0 else 'critical' if days_remaining <= 7 else 'warning' if days_remaining <= 30 else 'info'
            deadlines.append({
                'entity': client.name,
                'client_id': client.id,
                'jurisdiction': rules['name'],
                'agency': rules['agency'],
                'deadline_name': rule['name'],
                'due_date': due_date.isoformat(),
                'days_remaining': days_remaining,
                'urgency': urgency,
                'fee': rule.get('fee', 'N/A'),
                'penalty': rule.get('penalty', ''),
            })

    return sorted(deadlines, key=lambda d: d['days_remaining'])


def calculate_all_firm_deadlines(firm):
    """Calculate deadlines for all entities in a firm, sorted by urgency."""
    from .models import Client

    clients = Client.objects.filter(firm=firm, corporate_profile__isnull=False)
    all_deadlines = []

    for client in clients:
        try:
            deadlines = calculate_entity_deadlines(client)
            all_deadlines.extend(deadlines)
        except Exception:
            pass

    return sorted(all_deadlines, key=lambda d: d['days_remaining'])


# ── MINUTE BOOK HEALTH CHECK ───────────────────────────────────────

MINUTE_BOOK_REQUIREMENTS = {
    'directors_register': {
        'name': 'Directors Register',
        'category': 'register',
        'weight': 10,
        'remediation': 'Generate updated Directors Register from current director records.',
    },
    'shareholders_register': {
        'name': 'Shareholders Register',
        'category': 'register',
        'weight': 10,
        'remediation': 'Generate updated Shareholders Register from current shareholder records.',
    },
    'officers_register': {
        'name': 'Officers Register',
        'category': 'register',
        'weight': 8,
        'remediation': 'Generate Officers Register listing all appointed officers.',
    },
    'central_securities_register': {
        'name': 'Central Securities Register',
        'category': 'register',
        'weight': 5,
        'remediation': 'Generate Central Securities Register for all share certificates.',
    },
    'shareholder_ledger': {
        'name': 'Shareholder Ledger',
        'category': 'register',
        'weight': 7,
        'remediation': 'Generate Shareholder Ledger showing all share transactions.',
    },
    'annual_resolutions': {
        'name': 'Annual Resolutions (Current Year)',
        'category': 'resolution',
        'weight': 10,
        'remediation': 'Generate AGM minutes and annual resolutions for the current year.',
    },
    'director_consents': {
        'name': 'Director Consent Forms',
        'category': 'consent',
        'weight': 8,
        'remediation': 'Generate Consent to Act as Director for each active director.',
    },
    'by_law': {
        'name': 'By-Law No. 1',
        'category': 'governing',
        'weight': 5,
        'remediation': 'Ensure current By-Law No. 1 is in the minute book.',
    },
    'banking_resolution': {
        'name': 'Banking Resolution',
        'category': 'resolution',
        'weight': 5,
        'remediation': 'Generate current banking resolution with authorized signing officers.',
    },
    'share_certificates': {
        'name': 'Share Certificates',
        'category': 'certificate',
        'weight': 7,
        'remediation': 'Ensure all shareholders have current share certificates.',
    },
    'transfer_register': {
        'name': 'Share Transfer Register',
        'category': 'register',
        'weight': 5,
        'remediation': 'Generate Share Transfer Register if any transfers occurred.',
    },
    'director_resignations': {
        'name': 'Director Resignation Documents',
        'category': 'resolution',
        'weight': 5,
        'remediation': 'Ensure resignations are documented with board resolutions.',
    },
}


def minute_book_health_check(client):
    """
    Scan minute book completeness. Return score + list of missing items
    with remediation actions.
    """
    from .models import MinuteBookDocument, Director, Shareholder

    today = timezone.now().date()
    findings = []
    total_weight = 0
    earned_weight = 0

    # Get existing document types
    existing_docs = set(MinuteBookDocument.objects.filter(
        client=client
    ).values_list('document_type', flat=True))

    for doc_id, req in MINUTE_BOOK_REQUIREMENTS.items():
        total_weight += req['weight']
        if doc_id in existing_docs:
            earned_weight += req['weight']
            findings.append({
                'name': req['name'],
                'status': 'present',
                'category': req['category'],
                'weight': req['weight'],
            })
        else:
            # Check if this requirement applies
            applies = True
            if doc_id == 'director_consents':
                applies = Director.objects.filter(client=client).exists()
            elif doc_id == 'share_certificates':
                applies = Shareholder.objects.filter(client=client).exists()
            elif doc_id == 'transfer_register':
                applies = Shareholder.objects.filter(client=client).count() > 1

            if applies:
                findings.append({
                    'name': req['name'],
                    'status': 'missing',
                    'category': req['category'],
                    'weight': req['weight'],
                    'remediation': req['remediation'],
                })
            else:
                earned_weight += req['weight']
                findings.append({
                    'name': req['name'],
                    'status': 'not_applicable',
                    'category': req['category'],
                    'weight': req['weight'],
                })

    score = int((earned_weight / max(1, total_weight)) * 100)
    missing_count = sum(1 for f in findings if f['status'] == 'missing')
    present_count = sum(1 for f in findings if f['status'] == 'present')

    grade = 'A' if score >= 90 else 'B' if score >= 70 else 'C' if score >= 50 else 'D' if score >= 30 else 'F'

    return {
        'client_name': client.name,
        'client_id': client.id,
        'score': score,
        'grade': grade,
        'total_checks': len(findings),
        'present': present_count,
        'missing': missing_count,
        'findings': findings,
        'scanned_at': today.isoformat(),
    }
