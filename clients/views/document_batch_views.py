"""Bulk Document Import + AI Classification views."""
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from datetime import date

from ..models import (
    Client, DocumentBatch, ClassifiedDocument, DocumentChecklist,
    MINUTE_BOOK_CHECKLIST, log_activity,
)
from ._helpers import _get_firm


@login_required
def batch_list(request):
    """List all document batches."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')
    batches = DocumentBatch.objects.filter(firm=firm).order_by('-created_at')
    return render(request, 'clients/batch_list.html', {
        'firm': firm, 'batches': batches,
    })


@login_required
def batch_create(request):
    """Create a new batch upload."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        notes = request.POST.get('notes', '').strip()
        client_id = request.POST.get('client_id') or None
        files = request.FILES.getlist('files')

        if not name or not files:
            messages.error(request, 'Please provide a name and at least one file.')
            return redirect('batch_create')

        client = Client.objects.filter(id=client_id, firm=firm).first() if client_id else None

        batch = DocumentBatch.objects.create(
            firm=firm, client=client, uploaded_by=request.user,
            name=name, notes=notes, status='uploading',
            total_files=len(files),
        )

        # Save files and classify
        for f in files:
            doc = ClassifiedDocument.objects.create(
                batch=batch, file=f, original_filename=f.name, file_size=f.size,
            )
            # AI classification
            _classify_document(doc)

        batch.status = 'review'
        batch.processed_files = len(files)
        batch.classified_count = ClassifiedDocument.objects.filter(
            batch=batch, confidence_level__in=['high', 'medium']
        ).count()
        batch.unclassified_count = batch.total_files - batch.classified_count
        batch.save()

        log_activity(None, f'Document batch uploaded: {name} ({len(files)} files)', request.user)
        messages.success(request, f'Uploaded {len(files)} files. {batch.classified_count} classified with high confidence.')
        return redirect('batch_detail', batch_id=batch.id)

    return render(request, 'clients/batch_create.html', {
        'firm': firm, 'clients': Client.objects.filter(firm=firm),
    })


@login_required
def batch_detail(request, batch_id):
    """Review classified documents in a batch."""
    firm = _get_firm(request.user)
    batch = get_object_or_404(DocumentBatch, id=batch_id, firm=firm)
    documents = batch.documents.all().order_by('document_type', '-confidence')

    # Group by type
    by_type = {}
    for doc in documents:
        t = doc.effective_type
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(doc)

    # Generate gap analysis
    if batch.client:
        jurisdiction = getattr(batch.client, 'corporate_profile', None)
        jurisdiction = jurisdiction.jurisdiction if jurisdiction else 'federal'
    else:
        jurisdiction = batch.extracted_jurisdiction or 'federal'

    required = MINUTE_BOOK_CHECKLIST.get(jurisdiction, MINUTE_BOOK_CHECKLIST['federal'])
    found_types = set(doc.effective_type for doc in documents if doc.is_confident)
    missing = [t for t in required if t not in found_types]
    extra = [t for t in found_types if t not in required]

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'reclassify':
            doc_id = request.POST.get('document_id')
            new_type = request.POST.get('new_type')
            doc = get_object_or_404(ClassifiedDocument, id=doc_id, batch=batch)
            doc.corrected_type = new_type
            doc.is_reviewed = True
            doc.reviewed_by = request.user
            doc.reviewed_at = timezone.now()
            doc.save()
            messages.success(request, f'{doc.original_filename} reclassified to {doc.get_effective_type_display()}.')

        elif action == 'confirm_all':
            count = batch.documents.filter(is_reviewed=False).update(
                is_reviewed=True, reviewed_by=request.user, reviewed_at=timezone.now()
            )
            messages.success(request, f'{count} documents confirmed.')

        elif action == 'complete_batch':
            batch.status = 'completed'
            batch.completed_at = timezone.now()
            batch.save()
            messages.success(request, 'Batch marked as complete!')

        elif action == 'create_checklist':
            DocumentChecklist.objects.create(
                firm=firm, name=request.POST.get('checklist_name', f'{batch.name} Checklist'),
                jurisdiction=jurisdiction,
                required_documents=required,
                is_default=False,
            )
            messages.success(request, 'Checklist created.')

        return redirect('batch_detail', batch_id=batch.id)

    return render(request, 'clients/batch_detail.html', {
        'firm': firm, 'batch': batch, 'documents': documents,
        'by_type': by_type, 'required': required, 'missing': missing, 'extra': extra,
        'jurisdiction': jurisdiction,
    })


def _classify_document(doc):
    """AI document classification using keyword and pattern matching."""
    import re
    start = __import__('time').time()

    try:
        # Try to read file content
        try:
            content = doc.file.read().decode('utf-8', errors='ignore')[:50000]
            doc.file.seek(0)
        except Exception:
            content = doc.original_filename

        text = content.lower()
        filename = doc.original_filename.lower()

        # Classification rules
        rules = {
            'articles': {'keywords': ['articles of incorporation', 'certificate of incorporation', 'letters patent',
                                       'article d\'incorporation', 'memorandum of association'],
                          'filename': ['articles', 'certificate of incorp', 'letters patent']},
            'bylaw_no1': {'keywords': ['by-law no. 1', 'by-law no 1', 'bylaw no. 1', 'general by-law',
                                        'règlement général', 'by-law number 1'],
                           'filename': ['bylaw', 'by-law']},
            'org_resolution': {'keywords': ['organizing resolution', 'organizational resolution', 'first directors',
                                            'adopted the by-law', 'first meeting of directors'],
                                'filename': ['organizing', 'organizational', 'first meeting']},
            'annual_resolution': {'keywords': ['annual resolution', 'annual meeting of shareholders',
                                                'annual general meeting', 'agm', 'shareholders resolved',
                                                'directors resolution dated'],
                                   'filename': ['annual', 'agm']},
            'directors_register': {'keywords': ['register of directors', 'directors register'],
                                    'filename': ['director']},
            'shareholders_register': {'keywords': ['register of shareholders', 'shareholders register',
                                                    'securities register', 'share register'],
                                       'filename': ['shareholder', 'securities']},
            'share_certificate': {'keywords': ['share certificate', 'stock certificate', 'this certifies that',
                                                'is the registered holder of'],
                                   'filename': ['certificate', 'share cert']},
            'director_consent': {'keywords': ['consent to act', 'consent to act as director', 'i hereby consent'],
                                  'filename': ['consent']},
            'banking_resolution': {'keywords': ['banking resolution', 'bank account', 'authorized to open',
                                                 'banking arrangements'],
                                    'filename': ['bank', 'banking']},
            'tax_filing': {'keywords': ['t2 corporation income tax return', 't2 return', 't5 statement',
                                         'gst/hst return', 'corporation income tax return'],
                            'filename': ['t2', 't5', 'tax return', 'gst']},
            'annual_return': {'keywords': ['annual return', 'form 22', 'form 1', 'annual report'],
                               'filename': ['annual return', 'form 22']},
            'shareholder_agreement': {'keywords': ['unanimous shareholder', 'shareholder agreement', 'buy-sell',
                                                     'shotgun clause', 'right of first refusal'],
                                        'filename': ['sha', 'shareholder agreement', 'usa']},
            'ubo_declaration': {'keywords': ['individual with significant control', 'isc register',
                                              'beneficial owner', 'transparency register'],
                                 'filename': ['ubo', 'isc', 'beneficial']},
            'correspondence': {'keywords': ['dear', 'sincerely', 'regards', 'attached please find'],
                                'filename': ['letter', 'correspondence', 'email']},
            'invoice': {'keywords': ['invoice', 'bill', 'payment due', 'amount due', 'total due'],
                         'filename': ['invoice', 'bill']},
        }

        best_type = 'other'
        best_score = 0
        alternatives = []

        for doc_type, rule in rules.items():
            score = 0
            # Keyword matching
            for kw in rule['keywords']:
                if kw in text:
                    score += 20
            # Filename matching
            for fn in rule['filename']:
                if fn in filename:
                    score += 30
            # Title/first-page boost
            if score > 0:
                first_200 = text[:200]
                for kw in rule['keywords'][:3]:
                    if kw in first_200:
                        score += 25
            if score > best_score:
                if best_score > 0:
                    alternatives.append({'type': best_type, 'score': best_score})
                best_type = doc_type
                best_score = score
            elif score > 0:
                alternatives.append({'type': doc_type, 'score': score})

        # Calculate confidence
        max_possible = 100
        confidence = min(0.95, best_score / max_possible)

        if confidence >= 0.9:
            confidence_level = 'high'
        elif confidence >= 0.7:
            confidence_level = 'medium'
        elif confidence >= 0.5:
            confidence_level = 'low'
        else:
            confidence_level = 'uncertain'
            best_type = 'other'

        # Check if unreadable
        if len(text) < 50 and not filename:
            best_type = 'unreadable'
            confidence = 0.0
            confidence_level = 'uncertain'

        doc.document_type = best_type
        doc.confidence = confidence
        doc.confidence_level = confidence_level
        doc.alternative_types = sorted(alternatives, key=lambda x: x['score'], reverse=True)[:3]
        doc.ocr_text = text[:10000]
        doc.processing_time_ms = int((__import__('time').time() - start) * 1000)

        # Extract metadata
        date_match = __import__('re').search(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', content, __import__('re').IGNORECASE)
        if date_match:
            from datetime import datetime
            try:
                doc.extracted_date = datetime.strptime(f'{date_match.group(1)} {date_match.group(2)} {date_match.group(3)}', '%d %B %Y').date()
                doc.extracted_year = doc.extracted_date.year
            except ValueError:
                pass

        doc.save()

    except Exception as e:
        doc.error_message = str(e)
        doc.confidence_level = 'uncertain'
        doc.save()
