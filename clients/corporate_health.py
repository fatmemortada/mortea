"""
Corporate Health Engine — automated entity health scoring.

Checks every dimension of corporate compliance and assigns a 0-100
health score. The accountant sees "These 43 corporations require
attention" instead of finding problems manually.

Level 8 of the Mortacc automation hierarchy.
"""
from datetime import date, timedelta
from django.utils import timezone


def calculate_corporate_health(client):
    """
    Returns a dict with:
      - score: 0-100 overall health score
      - grade: A+ through F
      - checks: list of {category, status, label, detail, weight}
      - urgent_count: number of critical issues
      - summary: one-line assessment
    """
    today = timezone.now().date()
    checks = []
    total_weight = 0
    earned_weight = 0

    cp = getattr(client, 'corporate_profile', None)

    def add_check(category, condition, weight, label_pass, label_fail, detail=''):
        nonlocal total_weight, earned_weight
        total_weight += weight
        passed = bool(condition)
        if passed:
            earned_weight += weight
        checks.append({
            'category': category,
            'status': 'pass' if passed else 'fail',
            'label': label_pass if passed else label_fail,
            'detail': detail,
            'weight': weight,
        })
        return passed

    # ── 1. Annual Returns (weight: 15) ────────────────────────────
    if cp and cp.incorporation_date:
        inc_date = cp.incorporation_date
        # Calculate most recent anniversary
        try:
            anniversary = inc_date.replace(year=today.year)
        except ValueError:
            anniversary = inc_date.replace(year=today.year, day=inc_date.day - 1)
        if anniversary > today:
            try:
                anniversary = inc_date.replace(year=today.year - 1)
            except ValueError:
                pass

        # Check if annual return was filed for the current period
        from .models import AnnualFiling
        current_year_filing = AnnualFiling.objects.filter(
            client=client,
            year__gte=today.year - 1 if today.month < anniversary.month else today.year,
        ).order_by('-year').first()

        if current_year_filing and current_year_filing.status == 'filed':
            add_check('Annual Return', True, 15, 'Annual return filed', 'Annual return not filed',
                      f'Filed for {current_year_filing.year}')
        else:
            days_overdue = (today - (anniversary + timedelta(days=60))).days
            urgency = f'{max(0, days_overdue)} days overdue' if days_overdue > 0 else 'Due within 60 days'
            add_check('Annual Return', False, 15, '', f'Annual return missing',
                      urgency)
    else:
        add_check('Annual Return', False, 15, '', 'No incorporation date on file',
                  'Cannot determine annual return deadline without incorporation date')

    # ── 2. Minute Book Completeness (weight: 15) ──────────────────
    from .models import MinuteBookDocument, Director, Shareholder
    missing_minute_book = []
    # Check for key registers
    doc_types = MinuteBookDocument.objects.filter(client=client).values_list('document_type', flat=True)
    required = ['directors_register', 'shareholders_register', 'officers_register']
    for req in required:
        if req not in doc_types:
            missing_minute_book.append(req.replace('_', ' ').title())
    # Check for consent forms if there are directors
    if Director.objects.filter(client=client).exists():
        if 'consent_director' not in doc_types:
            missing_minute_book.append('Director Consents')
    if Shareholder.objects.filter(client=client).exists():
        if 'share_certificate' not in doc_types:
            missing_minute_book.append('Share Certificates')

    if not missing_minute_book:
        add_check('Minute Book', True, 15, 'Minute book complete', '',
                  'All core registers and documents present')
    elif len(missing_minute_book) <= 2:
        add_check('Minute Book', False, 15, '', f'Missing {len(missing_minute_book)} documents',
                  ', '.join(missing_minute_book[:3]))
    else:
        add_check('Minute Book', False, 15, '', f'Missing {len(missing_minute_book)} documents',
                  ', '.join(missing_minute_book[:3]) + f' +{len(missing_minute_book)-3} more')

    # ── 3. Director Status (weight: 10) ──────────────────────────
    directors = Director.objects.filter(client=client)
    if not directors.exists():
        add_check('Directors', False, 10, '', 'No directors on file',
                  'Every corporation needs at least one director')
    else:
        expired = directors.filter(resignation_date__isnull=False, resignation_date__lt=today)
        no_resignation = directors.filter(resignation_date__isnull=True)
        if expired.exists():
            add_check('Directors', False, 10, '', f'{expired.count()} director(s) resigned',
                      ', '.join(d.full_name for d in expired[:3]))
        elif no_resignation.count() < 1:
            add_check('Directors', False, 10, '', 'All directors resigned',
                      'No active directors — corporation cannot operate')
        else:
            add_check('Directors', True, 10, f'{no_resignation.count()} active director(s)', '',
                      'All directors current and active')

    # ── 4. Compliance Tasks (weight: 15) ─────────────────────────
    from .models import ComplianceTask
    overdue = ComplianceTask.objects.filter(
        client=client, status='overdue'
    ).count()
    pending = ComplianceTask.objects.filter(
        client=client, status='pending',
        due_date__lte=today + timedelta(days=30)
    ).count()

    if overdue == 0 and pending == 0:
        add_check('Compliance', True, 15, 'All tasks up to date', '',
                  'No overdue or upcoming tasks')
    elif overdue <= 2 and pending <= 3:
        add_check('Compliance', False, 15, '', f'{overdue} overdue, {pending} upcoming',
                  'Minor attention needed')
    else:
        add_check('Compliance', False, 15, '', f'{overdue} overdue, {pending} upcoming',
                  'Immediate attention required')

    # ── 5. UBO / KYC (weight: 8) ─────────────────────────────────
    from .models import Person
    people = Person.objects.filter(client=client)
    kyc_verified = people.filter(kyc_status='verified').count()
    kyc_total = people.count()
    if kyc_total == 0:
        add_check('KYC / UBO', False, 8, '', 'No people in KYC registry',
                  'FINTRAC requires UBO identification')
    elif kyc_verified == kyc_total:
        add_check('KYC / UBO', True, 8, f'All {kyc_total} people verified', '',
                  'KYC complete for all associated persons')
    else:
        add_check('KYC / UBO', False, 8, '', f'{kyc_total - kyc_verified} of {kyc_total} not verified',
                  'KYC verification incomplete')

    # ── 6. T2 Tax Filing (weight: 10) ─────────────────────────────
    from .models import T2Return
    t2 = T2Return.objects.filter(client=client).order_by('-tax_year').first()
    if t2:
        if t2.status in ['filed', 'accepted']:
            add_check('T2 Tax Filing', True, 10, f'T2 {t2.tax_year} filed', '',
                      f'Filed with CRA · ${float(t2.net_tax_owing):,.2f}')
        elif t2.status == 'ready_to_file':
            add_check('T2 Tax Filing', False, 10, '', 'T2 ready but not filed',
                      f'Year {t2.tax_year} — ready to submit')
        elif t2.status == 'rejected':
            add_check('T2 Tax Filing', False, 10, '', 'T2 rejected — needs revision',
                      f'Year {t2.tax_year} rejected')
        else:
            deadline = t2.fiscal_year_end + timedelta(days=180) if t2.fiscal_year_end else today
            days_left = (deadline - today).days
            add_check('T2 Tax Filing', False, 10, '', f'T2 {t2.tax_year} in progress',
                      f'{max(0, days_left)} days until deadline')
    else:
        if cp and cp.fiscal_year_end:
            fye = cp.fiscal_year_end.replace(year=today.year)
            deadline = fye + timedelta(days=180)
            days_left = (deadline - today).days
            add_check('T2 Tax Filing', False, 10, '', 'No T2 return started',
                      f'{max(0, days_left)} days until FYE + 6 months')
        else:
            add_check('T2 Tax Filing', False, 10, '', 'No T2 return or FYE data',
                      'Set fiscal year end to enable T2 tracking')

    # ── 7. Bookkeeping Currency (weight: 7) ──────────────────────
    from .models import BookkeepingTask
    latest_bk = BookkeepingTask.objects.filter(client=client).order_by('-year', '-id').first()
    if latest_bk:
        months_ago = 0
        try:
            bk_month = timezone.datetime.strptime(latest_bk.month, '%B').month
            bk_date = date(latest_bk.year, bk_month, 1)
            months_ago = (today.year - bk_date.year) * 12 + (today.month - bk_date.month)
        except (ValueError, TypeError):
            pass
        if months_ago <= 1:
            add_check('Bookkeeping', True, 7, 'Bookkeeping current', '',
                      f'Last: {latest_bk.month} {latest_bk.year}')
        elif months_ago <= 3:
            add_check('Bookkeeping', False, 7, '', f'{months_ago} months behind',
                      f'Last: {latest_bk.month} {latest_bk.year}')
        else:
            add_check('Bookkeeping', False, 7, '', f'{months_ago} months behind',
                      f'Last: {latest_bk.month} {latest_bk.year} — critical')
    else:
        add_check('Bookkeeping', False, 7, '', 'No bookkeeping tasks',
                  'Monthly bookkeeping not started')

    # ── 8. GST/HST Status (weight: 7) ────────────────────────────
    if latest_bk and latest_bk.hst_status == 'filed':
        add_check('GST/HST', True, 7, 'GST/HST filed', '',
                  f'{latest_bk.month} {latest_bk.year}')
    elif latest_bk and latest_bk.hst_status == 'pending':
        add_check('GST/HST', False, 7, '', 'GST/HST pending',
                  f'{latest_bk.month} {latest_bk.year}')
    else:
        add_check('GST/HST', False, 7, '', 'GST/HST status unknown',
                  'Run monthly bookkeeping to track GST/HST')

    # ── 9. Entity Registrations (weight: 7) ──────────────────────
    if cp and hasattr(cp, 'jurisdiction') and cp.jurisdiction:
        from .models import EntityRegistration
        registrations = EntityRegistration.objects.filter(client=client)
        if registrations.exists():
            expiring = registrations.filter(
                renewal_date__isnull=False,
                renewal_date__lte=today + timedelta(days=90)
            )
            if not expiring.exists():
                add_check('Registrations', True, 7, 'All registrations current', '',
                          f'{registrations.count()} registration(s) on file')
            else:
                add_check('Registrations', False, 7, '', f'{expiring.count()} registration(s) expiring soon',
                          'Renewal needed within 90 days')
        else:
            add_check('Registrations', False, 7, '', 'No registrations on file',
                      'Extra-provincial registrations may be required')
    else:
        add_check('Registrations', False, 7, '', 'No jurisdiction data',
                  'Set jurisdiction to track registration requirements')

    # ── 10. Invoices / Collections (weight: 6) ────────────────────
    from .models import Invoice
    overdue_inv = Invoice.objects.filter(
        client=client, status__in=['sent', 'overdue'],
        due_date__lt=today,
    ).count()
    total_inv = Invoice.objects.filter(client=client).count()

    if overdue_inv == 0:
        add_check('Collections', True, 6, 'No overdue invoices', '',
                  f'{total_inv} total invoice(s)')
    elif overdue_inv <= 2:
        add_check('Collections', False, 6, '', f'{overdue_inv} invoice(s) overdue',
                  'Minor collection needed')
    else:
        add_check('Collections', False, 6, '', f'{overdue_inv} invoice(s) overdue',
                  'Significant collections issue')

    # ── Calculate Score ───────────────────────────────────────────
    if total_weight > 0:
        score = int((earned_weight / total_weight) * 100)
    else:
        score = 0

    # ── Grade ─────────────────────────────────────────────────────
    grade_map = [(95, 'A+'), (85, 'A'), (75, 'B+'), (65, 'B'), (55, 'C+'),
                 (45, 'C'), (35, 'D'), (0, 'F')]
    grade = next(g for s, g in grade_map if score >= s)

    urgent_count = sum(1 for c in checks if c['status'] == 'fail' and c['weight'] >= 10)

    # ── Summary ───────────────────────────────────────────────────
    fail_count = sum(1 for c in checks if c['status'] == 'fail')
    if score >= 90:
        summary = 'Excellent — all critical areas covered'
    elif score >= 70:
        summary = f'Good — {fail_count} area(s) need attention'
    elif score >= 50:
        summary = f'Fair — {fail_count} issues require action'
    elif score >= 30:
        summary = f'Poor — {fail_count} problems, {urgent_count} urgent'
    else:
        summary = f'Critical — {fail_count} failures, immediate action required'

    return {
        'client_id': client.id,
        'client_name': client.name,
        'score': score,
        'grade': grade,
        'grade_color': {
            'A+': '#16a34a', 'A': '#16a34a', 'B+': '#65a30d', 'B': '#65a30d',
            'C+': '#d97706', 'C': '#d97706', 'D': '#dc2626', 'F': '#dc2626',
        }.get(grade, '#64748b'),
        'checks': checks,
        'urgent_count': urgent_count,
        'fail_count': fail_count,
        'pass_count': sum(1 for c in checks if c['status'] == 'pass'),
        'summary': summary,
        'scored_at': today.isoformat(),
    }


def calculate_firm_health(firm):
    """Calculate health scores for all entities in a firm, ranked by urgency."""
    from .models import Client
    clients = Client.objects.filter(firm=firm).select_related('corporate_profile')
    if not clients:
        return []

    results = []
    for client in clients:
        try:
            health = calculate_corporate_health(client)
            results.append(health)
        except Exception:
            pass

    results.sort(key=lambda r: (r['score'], -r['urgent_count']))
    return results
