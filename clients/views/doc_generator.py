"""Unified Document Generator Center — one page, all documents."""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from ..models import Client, CorporateProfile
from ..pdf_views import DOCUMENT_TYPES
from ._helpers import _get_firm


@login_required
def doc_generator(request, client_id):
    """Show all available documents for a client with one-click generation."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    profile = getattr(client, 'corporate_profile', None)
    directors = client.directors.filter(resignation_date__isnull=True)
    shareholders = client.shareholders.all()
    officers = directors.filter(is_officer=True)

    has_data = profile is not None and directors.exists() and shareholders.exists()

    # Group documents by category
    categories = [
        {
            'name': 'Registers',
            'icon': '📋',
            'docs': [
                {'name': 'Directors Register', 'url': f'/clients/{client.id}/pdf/directors-register/', 'ready': directors.exists()},
                {'name': 'Shareholders Register', 'url': f'/clients/{client.id}/pdf/shareholders-register/', 'ready': shareholders.exists()},
                {'name': 'Officers Register', 'url': f'/clients/{client.id}/pdf/officers-register/', 'ready': officers.exists()},
                {'name': 'Central Securities Register', 'url': f'/clients/{client.id}/pdf/central-securities-register/', 'ready': shareholders.exists()},
                {'name': 'Shareholder Ledger', 'url': f'/clients/{client.id}/pdf/shareholder-ledger/', 'ready': shareholders.exists()},
                {'name': 'Share Transfer Register', 'url': f'/clients/{client.id}/pdf/share-transfer-register/', 'ready': shareholders.exists()},
            ],
        },
        {
            'name': 'Resolutions',
            'icon': '📜',
            'docs': [
                {'name': 'Directors Resolutions', 'url': f'/clients/{client.id}/pdf/directors-resolutions/', 'ready': directors.exists()},
                {'name': 'Shareholders Resolutions', 'url': f'/clients/{client.id}/pdf/shareholders-resolutions/', 'ready': shareholders.exists()},
                {'name': 'Banking Resolution', 'url': f'/clients/{client.id}/pdf/banking-resolution/', 'ready': has_data},
            ],
        },
        {
            'name': 'Certificates & Consents',
            'icon': '📄',
            'docs': [
                {'name': f'Share Certificate — {s.full_name}', 'url': f'/clients/{client.id}/pdf/share-certificate/{s.id}/', 'ready': True}
                for s in shareholders
            ] + [
                {'name': f'Consent — {d.full_name}', 'url': f'/clients/{client.id}/pdf/consent/{d.id}/', 'ready': True}
                for d in directors
            ] + [
                {'name': 'Subscription for Shares', 'url': f'/clients/{client.id}/pdf/subscription-for-shares/', 'ready': shareholders.exists()},
            ],
        },
        {
            'name': 'Governance',
            'icon': '🏛️',
            'docs': [
                {'name': 'General By-Law No. 1', 'url': f'/clients/{client.id}/pdf/bylaw-no1/', 'ready': has_data},
                {'name': 'Waiver of Notice — Directors', 'url': f'/clients/{client.id}/pdf/waiver-notice-directors/', 'ready': directors.exists()},
                {'name': 'Waiver of Notice — Shareholders', 'url': f'/clients/{client.id}/pdf/waiver-notice-shareholders/', 'ready': shareholders.exists()},
            ],
        },
        {
            'name': 'Full Packages',
            'icon': '📦',
            'docs': [
                {'name': 'Complete Minute Book (ZIP)', 'url': f'/clients/{client.id}/pdf/minute-book-zip/', 'ready': has_data, 'featured': True},
                {'name': 'Banking Package', 'url': f'/clients/{client.id}/pdf/banking-package/', 'ready': has_data},
                {'name': 'Custom Selection', 'url': f'/clients/{client.id}/minute-book-builder/', 'ready': True},
            ],
        },
        {
            'name': 'Templates',
            'icon': '📝',
            'docs': [
                {'name': 'Board Resolution (Bank Account)', 'url': f'/clients/{client.id}/templates/builtin_0/fill/?format=pdf', 'ready': True},
                {'name': 'Director Consent to Act', 'url': f'/clients/{client.id}/templates/builtin_1/fill/?format=pdf', 'ready': directors.exists()},
                {'name': 'Shareholder Agreement', 'url': f'/clients/{client.id}/templates/builtin_2/fill/?format=pdf', 'ready': shareholders.exists()},
            ],
        },
    ]

    return render(request, 'clients/doc_generator.html', {
        'client': client, 'profile': profile,
        'categories': categories, 'has_data': has_data,
        'director_count': directors.count(), 'shareholder_count': shareholders.count(),
    })
