"""AI document extraction views: upload, review extracted data, apply to records."""
import os

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.dateparse import parse_date

from ..models import (
    Client, CorporateProfile, Director, Shareholder, ShareClass,
    AIExtraction, log_activity,
)
from ..utils import ai_extraction as extraction_service
from ._helpers import _get_firm

EXTRACTABLE_EXTENSIONS = ('.pdf', '.png', '.jpg', '.jpeg')


@login_required
def ai_extraction_view(request, client_id):
    """Upload a corporate document, review what Claude extracted, apply to records."""
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    upload_error = ''

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'extract' and request.FILES.get('document'):
            upload = request.FILES['document']
            ext = os.path.splitext(upload.name)[1].lower()
            if ext not in EXTRACTABLE_EXTENSIONS:
                upload_error = 'AI extraction supports PDF, PNG and JPG files.'
            else:
                file_bytes = upload.read()
                data, error = extraction_service.extract_corporate_data(file_bytes, upload.name)
                upload.seek(0)
                extraction = AIExtraction.objects.create(
                    client=client, document=upload, document_name=upload.name,
                    status='completed' if data else 'failed',
                    extracted_data=data or {}, error_message=error or '',
                    created_by=request.user,
                )
                log_activity(request.user, 'create', 'AIExtraction', extraction.id, upload.name,
                             f'AI extraction of {upload.name} for {client.name}: '
                             f'{extraction.get_status_display()}', firm=firm)
                return redirect('ai_extraction', client_id=client_id)

        elif action == 'apply':
            extraction = AIExtraction.objects.filter(
                id=request.POST.get('extraction_id'), client=client, status='completed').first()
            if extraction:
                summary = _apply_extraction(client, extraction.extracted_data)
                extraction.status = 'applied'
                extraction.applied_at = timezone.now()
                extraction.save()
                log_activity(request.user, 'update', 'Client', client.id, client.name,
                             f'Applied AI extraction {extraction.document_name}: {summary}', firm=firm)
            return redirect('ai_extraction', client_id=client_id)

        elif action == 'delete':
            AIExtraction.objects.filter(id=request.POST.get('extraction_id'), client=client).delete()
            return redirect('ai_extraction', client_id=client_id)

    extractions = client.ai_extractions.all()[:10]
    latest = next((e for e in extractions if e.status == 'completed'), None)
    api_configured = bool(os.environ.get('ANTHROPIC_API_KEY'))

    return render(request, 'clients/ai_extraction.html', {
        'firm': firm, 'client': client, 'extractions': extractions,
        'latest': latest, 'upload_error': upload_error,
        'api_configured': api_configured,
    })


def _apply_extraction(client, data):
    """
    Write extracted data into the entity's records. Fills gaps only:
    profile fields are set when empty, people/classes are added when the
    name doesn't already exist. Returns a short summary string.
    """
    JURISDICTION_MAP = {
        'federal': 'federal', 'canada': 'federal', 'cbca': 'federal',
        'ontario': 'ontario', 'british columbia': 'bc', 'bc': 'bc',
        'quebec': 'quebec', 'québec': 'quebec', 'alberta': 'alberta',
    }

    profile, _ = CorporateProfile.objects.get_or_create(client=client)
    profile_updates = 0
    field_values = {
        'business_number': data.get('business_number', ''),
        'registered_address': data.get('registered_address', ''),
        'fiscal_year_end': data.get('fiscal_year_end', ''),
    }
    for field, value in field_values.items():
        if value and not getattr(profile, field):
            setattr(profile, field, value)
            profile_updates += 1
    jurisdiction = JURISDICTION_MAP.get(data.get('jurisdiction', '').strip().lower())
    if jurisdiction and not profile.jurisdiction:
        profile.jurisdiction = jurisdiction
        profile_updates += 1
    incorporation_date = parse_date(data.get('incorporation_date') or '')
    if incorporation_date and not profile.incorporation_date:
        profile.incorporation_date = incorporation_date
        profile_updates += 1
    if profile_updates:
        profile.save()

    existing_directors = {d.full_name.lower() for d in client.directors.all()}
    directors_added = 0
    for d in data.get('directors', []):
        name = (d.get('full_name') or '').strip()
        if name and name.lower() not in existing_directors:
            Director.objects.create(
                client=client, full_name=name,
                address=d.get('address', ''),
                appointment_date=parse_date(d.get('appointment_date') or ''),
                officer_title=d.get('officer_title', ''),
                is_officer=bool(d.get('officer_title')),
            )
            existing_directors.add(name.lower())
            directors_added += 1

    existing_shareholders = {s.full_name.lower() for s in client.shareholders.all()}
    shareholders_added = 0
    for s in data.get('shareholders', []):
        name = (s.get('full_name') or '').strip()
        if name and name.lower() not in existing_shareholders:
            Shareholder.objects.create(
                client=client, full_name=name,
                share_class=s.get('share_class') or 'Common',
                num_shares=max(int(s.get('num_shares') or 0), 0),
                address=s.get('address', ''),
            )
            existing_shareholders.add(name.lower())
            shareholders_added += 1

    existing_classes = {c.name.lower() for c in client.share_classes.all()}
    classes_added = 0
    for sc in data.get('share_classes', []):
        name = (sc.get('name') or '').strip()
        if name and name.lower() not in existing_classes:
            ShareClass.objects.create(
                client=client, name=name,
                voting=bool(sc.get('voting', True)),
                rights_restrictions=sc.get('rights_restrictions', ''),
            )
            existing_classes.add(name.lower())
            classes_added += 1

    return (f'{profile_updates} profile fields, {directors_added} directors, '
            f'{shareholders_added} shareholders, {classes_added} share classes added')
