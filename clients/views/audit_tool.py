"""Corporate Records Audit Tool — analyzes minute book completeness."""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import date

from ..models import Client, CorporateProfile, Director, Shareholder
from ._helpers import _get_firm, _get_missing_items


CHECKS = [
    ('articles', 'Articles of Incorporation', 'profile_exists', None),
    ('bylaws', 'General By-Law No. 1', 'profile_exists', None),
    ('directors_register', 'Directors Register', 'has_directors', None),
    ('shareholders_register', 'Shareholders Register', 'has_shareholders', None),
    ('officers_register', 'Officers Register', 'has_officers', None),
    ('annual_resolutions', 'Annual Resolutions (past 3 years)', 'has_annual_resolutions', None),
    ('minute_book', 'Minute Book Documents', 'has_minute_book_docs', None),
    ('director_consents', 'Director Consents to Act', 'has_directors', 'Each director needs a signed consent'),
    ('share_certificates', 'Share Certificates', 'has_shareholders', 'Each shareholder needs a certificate'),
    ('ubo_register', 'UBO Register', 'has_shareholders', 'Required for individuals with 25%+ ownership'),
    ('banking_resolution', 'Banking Resolution', 'profile_exists', None),
    ('registered_office', 'Registered Office Address', 'has_address', None),
]


@login_required
def audit_tool(request, client_id):
    """Analyze a client's corporate records for completeness."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    profile = getattr(client, 'corporate_profile', None)
    today = date.today()

    # Run all checks
    results = []
    total = len(CHECKS)
    passed = 0

    for check_id, check_name, condition, recommendation in CHECKS:
        status = 'fail'
        detail = ''

        if condition == 'profile_exists':
            status = 'pass' if profile else 'fail'
            detail = 'Corporate profile exists' if profile else 'No corporate profile created'
        elif condition == 'has_directors':
            count = client.directors.filter(resignation_date__isnull=True).count()
            status = 'pass' if count > 0 else 'fail'
            detail = f'{count} active director(s)' if count > 0 else 'No directors on record'
        elif condition == 'has_shareholders':
            count = client.shareholders.count()
            status = 'pass' if count > 0 else 'fail'
            detail = f'{count} shareholder(s)' if count > 0 else 'No shareholders on record'
        elif condition == 'has_officers':
            count = client.directors.filter(is_officer=True, resignation_date__isnull=True).count()
            status = 'pass' if count > 0 else 'warn'
            detail = f'{count} officer(s)' if count > 0 else 'No officers appointed'
        elif condition == 'has_annual_resolutions':
            count = client.compliance_tasks.filter(status='completed').count()
            status = 'pass' if count >= 3 else ('warn' if count > 0 else 'fail')
            detail = f'{count} completed compliance task(s)' if count > 0 else 'No completed annual resolutions'
        elif condition == 'has_minute_book_docs':
            count = client.minute_book_documents.count()
            status = 'pass' if count > 0 else 'warn'
            detail = f'{count} document(s)' if count > 0 else 'No minute book documents uploaded'
        elif condition == 'has_address':
            status = 'pass' if (profile and profile.registered_address) else 'fail'
            detail = 'Address on file' if (profile and profile.registered_address) else 'No registered address'

        if status == 'pass':
            passed += 1

        results.append({
            'id': check_id, 'name': check_name,
            'status': status, 'detail': detail,
            'recommendation': recommendation,
        })

    score = int((passed / total) * 100) if total > 0 else 0
    if score >= 90:
        grade, color = 'A', '#16a34a'
    elif score >= 70:
        grade, color = 'B', '#2563eb'
    elif score >= 50:
        grade, color = 'C', '#d97706'
    elif score >= 30:
        grade, color = 'D', '#dc2626'
    else:
        grade, color = 'F', '#991b1b'

    return render(request, 'clients/audit_tool.html', {
        'client': client, 'profile': profile,
        'results': results, 'score': score, 'grade': grade, 'color': color,
        'passed': passed, 'total': total, 'today': today,
    })
