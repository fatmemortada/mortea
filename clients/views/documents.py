from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
import os

from ..models import Client, CorporateProfile, UserProfile
from ._helpers import _get_firm


@login_required
def document_manager_view(request):
    try:
        firm = request.user.userprofile.firm
    except UserProfile.DoesNotExist:
        return redirect('login')

    clients = Client.objects.filter(firm=firm).prefetch_related(
        'onboarding_documents'
    ).order_by('name')

    CAT_LABELS = {
        'id': 'ID Document', 'bank': 'Bank Document',
        'tax': 'Tax Document', 'corporate': 'Corporate',
        'additional': 'Additional',
    }

    def icon_for(filename):
        ext = os.path.splitext(filename or '')[1].lower()
        if ext == '.pdf': return '📄', 'pdf'
        if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp'): return '🖼️', 'image'
        if ext in ('.doc', '.docx'): return '📝', 'doc'
        return '📎', 'other'

    doc_groups = []
    total_docs = 0; id_count = 0; corporate_count = 0; clients_with_docs = 0

    for client in clients:
        docs = client.onboarding_documents.all()
        if not docs.exists():
            continue
        clients_with_docs += 1
        group_docs = []
        for doc in docs:
            filename = os.path.basename(doc.file.name) if doc.file else '—'
            icon, icon_type = icon_for(filename)
            cat = doc.category or 'additional'
            if cat == 'id': id_count += 1
            if cat == 'corporate': corporate_count += 1
            total_docs += 1
            try:
                size = f"{doc.file.size // 1024} KB" if doc.file else ''
            except Exception:
                size = ''
            group_docs.append({
                'name': filename, 'category': cat,
                'category_label': CAT_LABELS.get(cat, cat.title()),
                'icon': icon, 'icon_type': icon_type,
                'url': doc.file.url if doc.file else '#',
                'size': size,
                'uploaded': doc.uploaded_at.strftime('%b %d, %Y') if hasattr(doc, 'uploaded_at') and doc.uploaded_at else '',
            })
        if group_docs:
            doc_groups.append({'client_name': client.name, 'docs': group_docs})

    return render(request, 'clients/document_manager.html', {
        'firm': firm, 'doc_groups': doc_groups,
        'total_docs': total_docs, 'id_count': id_count,
        'corporate_count': corporate_count, 'clients_with_docs': clients_with_docs,
    })


@login_required
def minute_books_view(request):
    firm = _get_firm(request.user)
    clients = Client.objects.filter(firm=firm).prefetch_related(
        'corporate_profile', 'directors', 'shareholders'
    ).order_by('name') if firm else Client.objects.none()

    rows = []
    ready_count = 0; incomplete_count = 0; no_profile_count = 0

    for client in clients:
        corp = getattr(client, 'corporate_profile', None)
        director_count = client.directors.count()
        shareholder_count = client.shareholders.count()

        if not corp:
            no_profile_count += 1
            readiness = 0
        else:
            checks = [
                bool(corp.jurisdiction), bool(corp.business_number),
                director_count > 0, shareholder_count > 0,
                bool(corp.registered_address),
            ]
            readiness = int((sum(checks) / len(checks)) * 100)

        if readiness == 100:
            ready_count += 1
        elif corp:
            incomplete_count += 1

        rows.append({
            'client': client, 'corp': corp,
            'director_count': director_count,
            'shareholder_count': shareholder_count,
            'readiness': readiness,
        })

    return render(request, 'clients/minute_books.html', {
        'rows': rows, 'total_clients': len(rows),
        'ready_count': ready_count, 'incomplete_count': incomplete_count,
        'no_profile_count': no_profile_count,
    })


@login_required
def minute_book_builder_view(request, client_id):
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    profile = getattr(client, 'corporate_profile', None)
    directors = list(client.directors.all().order_by('appointment_date'))
    shareholders = list(client.shareholders.all())
    officers = [d for d in directors if d.is_officer]

    from ..pdf_views import DOCUMENT_TYPES, BANKING_PACKAGE_DOCS, FULL_MINUTE_BOOK_DOCS

    categories = {}
    for doc_type, (template_name, display_name, category, _) in DOCUMENT_TYPES.items():
        if category not in categories:
            categories[category] = []
        has_data = True
        if doc_type == 'directors_register' and len(directors) == 0:
            has_data = False
        elif doc_type in ('shareholders_register', 'central_securities_register',
                         'shareholder_ledger', 'share_transfer_register',
                         'subscription_for_shares') and len(shareholders) == 0:
            has_data = False
        elif doc_type == 'officers_register' and len(officers) == 0:
            has_data = False
        elif not profile:
            has_data = False

        categories[category].append({
            'key': doc_type, 'name': display_name, 'has_data': has_data,
            'preview_url': _get_preview_url(client_id, doc_type),
        })

    has_share_certs = len(shareholders) > 0
    has_consents = len(directors) > 0

    jurisdiction_display = ''
    if profile:
        jurisdiction_display = dict(CorporateProfile.JURISDICTION_CHOICES).get(profile.jurisdiction, '')

    can_generate = profile is not None and len(directors) > 0 and len(shareholders) > 0

    return render(request, 'clients/minute_book_builder.html', {
        'client': client, 'profile': profile,
        'directors': directors, 'shareholders': shareholders,
        'officers': officers, 'categories': categories,
        'banking_package_docs': BANKING_PACKAGE_DOCS,
        'full_minute_book_docs': FULL_MINUTE_BOOK_DOCS,
        'has_share_certs': has_share_certs, 'has_consents': has_consents,
        'can_generate': can_generate, 'jurisdiction_display': jurisdiction_display,
        'director_count': len(directors), 'shareholder_count': len(shareholders),
        'officer_count': len(officers), 'total_doc_types': len(FULL_MINUTE_BOOK_DOCS),
    })


def _get_preview_url(client_id, doc_type):
    url_map = {
        'directors_register': 'pdf_directors_register',
        'shareholders_register': 'pdf_shareholders_register',
        'officers_register': 'pdf_officers_register',
        'central_securities_register': 'pdf_central_securities_register',
        'bylaw_no1': 'pdf_bylaw_no1',
        'directors_resolutions': 'pdf_directors_resolutions',
        'shareholders_resolutions': 'pdf_shareholders_resolutions',
        'subscription_for_shares': 'pdf_subscription_for_shares',
        'shareholder_ledger': 'pdf_shareholder_ledger',
        'share_transfer_register': 'pdf_share_transfer_register',
        'waiver_notice_directors': 'pdf_waiver_notice_directors',
        'waiver_notice_shareholders': 'pdf_waiver_notice_shareholders',
        'banking_resolution': 'pdf_banking_resolution',
    }
    url_name = url_map.get(doc_type)
    if url_name:
        return reverse(url_name, kwargs={'client_id': client_id})
    return '#'
