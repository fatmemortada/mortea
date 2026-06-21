"""Global search across entities, documents, invoices, and compliance tasks."""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat
from django.utils import timezone

from ..models import Client, CorporateProfile, Director, Shareholder, OnboardingDocument, Invoice, ComplianceTask, AnnualFiling, ActivityLog
from ..models.platform import Note, ChasingTask
from ._helpers import _get_firm


@login_required
def global_search_view(request):
    firm = _get_firm(request.user)
    if not firm:
        return render(request, 'clients/search.html', {
            'query': '', 'results': [], 'total': 0,
        })

    query = request.GET.get('q', '').strip()
    context = {
        'query': query,
        'results': [],
        'total': 0,
        'firm': firm,
    }

    if not query or len(query) < 2:
        return render(request, 'clients/search.html', context)

    results = []

    # 1. Clients — search name, email, phone, business_type, client_token
    client_qs = Client.objects.filter(firm=firm).filter(
        Q(name__icontains=query) |
        Q(email__icontains=query) |
        Q(phone__icontains=query) |
        Q(business_type__icontains=query) |
        Q(client_token__icontains=query)
    ).select_related('corporate_profile')[:20]

    for c in client_qs:
        corp = getattr(c, 'corporate_profile', None)
        results.append({
            'type': 'client',
            'label': 'Client',
            'title': c.name,
            'subtitle': c.email,
            'url': f'/clients/{c.id}/',
            'badge': c.get_status_display(),
            'meta': corp.jurisdiction if corp else '',
        })

    # 2. Directors
    directors = Director.objects.filter(client__firm=firm).filter(
        full_name__icontains=query
    ).select_related('client')[:10]

    for d in directors:
        results.append({
            'type': 'director',
            'label': 'Director',
            'title': d.full_name,
            'subtitle': d.client.name,
            'url': f'/entities/{d.client.id}/',
            'badge': 'Officer' if d.is_officer else '',
            'meta': d.officer_title,
        })

    # 3. Shareholders
    shareholders = Shareholder.objects.filter(client__firm=firm).filter(
        full_name__icontains=query
    ).select_related('client')[:10]

    for s in shareholders:
        results.append({
            'type': 'shareholder',
            'label': 'Shareholder',
            'title': s.full_name,
            'subtitle': s.client.name,
            'url': f'/entities/{s.client.id}/',
            'badge': f'{s.num_shares} shares',
            'meta': s.share_class,
        })

    # 4. Documents
    docs = OnboardingDocument.objects.filter(client__firm=firm).filter(
        document_name__icontains=query
    ).select_related('client')[:10]

    for d in docs:
        results.append({
            'type': 'document',
            'label': 'Document',
            'title': d.document_name,
            'subtitle': d.client.name,
            'url': f'/clients/{d.client.id}/?tab=documents',
            'badge': d.get_category_display(),
            'meta': d.get_review_status_display(),
        })

    # 5. Invoices
    invoices = Invoice.objects.filter(client__firm=firm).filter(
        Q(invoice_number__icontains=query) |
        Q(description__icontains=query)
    ).select_related('client')[:10]

    for inv in invoices:
        results.append({
            'type': 'invoice',
            'label': 'Invoice',
            'title': inv.invoice_number,
            'subtitle': inv.client.name,
            'url': f'/clients/{inv.client.id}/?tab=invoices',
            'badge': f'${inv.amount}',
            'meta': inv.get_status_display(),
        })

    # 6. Compliance Tasks
    tasks = ComplianceTask.objects.filter(client__firm=firm).filter(
        Q(title__icontains=query) |
        Q(description__icontains=query)
    ).select_related('client')[:10]

    for t in tasks:
        results.append({
            'type': 'task',
            'label': 'Compliance',
            'title': t.title,
            'subtitle': t.client.name,
            'url': f'/clients/{t.client.id}/?tab=compliance',
            'badge': t.get_status_display(),
            'meta': f'Due {t.due_date}',
        })

    # 7. Notes (internal & client-visible)
    notes = Note.objects.filter(client__firm=firm).filter(
        text__icontains=query
    ).select_related('client', 'created_by')[:10]

    for n in notes:
        results.append({
            'type': 'note',
            'label': 'Note',
            'title': n.text[:100] + ('…' if len(n.text) > 100 else ''),
            'subtitle': n.client.name,
            'url': f'/clients/{n.client.id}/?tab=notes',
            'badge': 'Internal' if n.is_internal else 'Visible',
            'meta': n.created_at.strftime('%b %d, %Y'),
        })

    # 8. CorporateProfile — by business number
    profiles = CorporateProfile.objects.filter(client__firm=firm).filter(
        Q(business_number__icontains=query) |
        Q(hst_number__icontains=query)
    ).select_related('client')[:10]

    for p in profiles:
        results.append({
            'type': 'profile',
            'label': 'Corporation',
            'title': p.client.name,
            'subtitle': f'BN: {p.business_number}' if p.business_number else p.get_jurisdiction_display(),
            'url': f'/entities/{p.client.id}/',
            'badge': p.get_jurisdiction_display(),
            'meta': p.get_status_display(),
        })

    # 9. AnnualFilings — by year or notes
    filings = AnnualFiling.objects.filter(client__firm=firm).filter(
        Q(notes__icontains=query) |
        Q(year__icontains=query)
    ).select_related('client')[:10]

    for f in filings:
        results.append({
            'type': 'filing',
            'label': 'Annual Filing',
            'title': f'{f.client.name} — {f.year}',
            'subtitle': f'Due {f.due_date}',
            'url': f'/clients/{f.client.id}/?tab=filings',
            'badge': f.get_status_display(),
            'meta': f.filed_date.strftime('%b %d, %Y') if f.filed_date else 'Not filed',
        })

    # 10. ChasingTasks
    chases = ChasingTask.objects.filter(client__firm=firm).filter(
        Q(title__icontains=query) |
        Q(description__icontains=query)
    ).select_related('client')[:10]

    for ct in chases:
        results.append({
            'type': 'chase',
            'label': 'Task',
            'title': ct.title,
            'subtitle': ct.client.name,
            'url': f'/clients/{ct.client.id}/?tab=tasks',
            'badge': ct.get_status_display(),
            'meta': f'Due {ct.due_date}' if ct.due_date else '',
        })

    # 11. ActivityLog
    activities = ActivityLog.objects.filter(firm=firm).filter(
        Q(description__icontains=query) |
        Q(target_name__icontains=query) |
        Q(action__icontains=query)
    ).select_related('user').order_by('-created_at')[:10]

    for a in activities:
        results.append({
            'type': 'activity',
            'label': 'Activity',
            'title': a.description or a.get_action_display(),
            'subtitle': a.target_name or '',
            'url': f'/activity-log/?q={query}',
            'badge': a.get_action_display(),
            'meta': a.created_at.strftime('%b %d, %Y'),
        })

    # 12. E-Signature Envelopes
    try:
        from ..models.e_signature import ESignatureEnvelope
        envelopes = ESignatureEnvelope.objects.filter(firm=firm).filter(
            Q(title__icontains=query) |
            Q(document_name__icontains=query)
        ).select_related('client').order_by('-created_at')[:10]

        for env in envelopes:
            signer_count = env.signers.count()
            results.append({
                'type': 'signature',
                'label': 'E-Signature',
                'title': env.title or env.document_name,
                'subtitle': env.client.name if env.client else '',
                'url': f'/e-signatures/{env.id}/',
                'badge': env.get_status_display(),
                'meta': f'{signer_count} signer{"s" if signer_count != 1 else ""}',
            })
    except ImportError:
        pass  # E-Signature model may not be available

    # Sort: clients first, then by relevance (exact match > startswith > contains)
    def score(r):
        t = r['title'].lower()
        q = query.lower()
        if t == q: return 0
        if t.startswith(q): return 1
        return 2

    results.sort(key=score)
    context['results'] = results[:50]
    context['total'] = len(results)

    return render(request, 'clients/search.html', context)
