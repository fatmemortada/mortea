"""
T1 Personal Tax Organizer — views for client questionnaire and staff dashboard.
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from datetime import date

from ..models import (
    Client, T1Organizer, T1Document, T1_QUESTIONNAIRE,
    generate_initial_documents, get_questionnaire, log_activity,
)
from ._helpers import _get_firm


# ── Client-Facing Questionnaire (token-based, no login needed) ──────

def t1_client_portal(request, token):
    """Secure client-facing T1 questionnaire — accessed via unique token."""
    organizer = get_object_or_404(T1Organizer.objects.select_related('client'), token=token)

    if organizer.status == 'not_started':
        organizer.status = 'in_progress'
        organizer.save()

    language = organizer.language
    questionnaire = get_questionnaire(language)
    documents = organizer.documents.all()

    # Calculate completion
    organizer.calculate_completion()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'save_answers':
            # Save all yes/no and select fields
            for sec in questionnaire['sections']:
                for q in sec['questions']:
                    field_id = q['id']
                    if q['type'] in ('yesno', 'select', 'number', 'text'):
                        val = request.POST.get(field_id, '')
                        if val:
                            if q['type'] == 'yesno':
                                setattr(organizer, field_id, val == 'yes')
                            elif q['type'] == 'number':
                                try:
                                    setattr(organizer, field_id, int(val))
                                except ValueError:
                                    pass
                            else:
                                setattr(organizer, field_id, val)

            organizer.save()
            generate_initial_documents(organizer)
            organizer.calculate_completion()
            messages.success(request, 'Your answers have been saved.' if language == 'en' else 'Vos réponses ont été enregistrées.')

        elif action == 'upload_document':
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(T1Document, id=doc_id, organizer=organizer)
            uploaded_file = request.FILES.get('file')
            if uploaded_file:
                doc.file = uploaded_file
                doc.original_filename = uploaded_file.name
                doc.status = 'uploaded'
                doc.uploaded_at = timezone.now()
                doc.save()
                doc.auto_rename()
                messages.success(request, f'{doc.get_doc_type_display()} uploaded.')

        elif action == 'mark_na':
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(T1Document, id=doc_id, organizer=organizer)
            doc.status = 'not_applicable'
            doc.save()

        elif action == 'submit':
            organizer.status = 'submitted'
            organizer.submitted_at = timezone.now()
            organizer.calculate_completion()
            organizer.detect_risk_flags()
            organizer.generate_ai_summary()
            organizer.save()

            # Notify accountant
            try:
                from ..emails import send_submission_notification
                send_submission_notification(organizer.client)
            except Exception:
                pass

            messages.success(request,
                'Your T1 organizer has been submitted! Your accountant will review it.' if language == 'en'
                else 'Votre organiseur T1 a été soumis! Votre comptable l\'examinera.')
            return redirect('t1_client_success', token=token)

        return redirect('t1_client_portal', token=token)

    return render(request, 'clients/t1_client_portal.html', {
        'organizer': organizer,
        'client': organizer.client,
        'questionnaire': questionnaire,
        'documents': documents,
        'language': language,
    })


def t1_client_success(request, token):
    """Success page after T1 submission."""
    organizer = get_object_or_404(T1Organizer.objects.select_related('client'), token=token)
    return render(request, 'clients/t1_client_success.html', {
        'organizer': organizer,
        'language': organizer.language,
    })


# ── Staff Dashboard ─────────────────────────────────────────────────

@login_required
def t1_dashboard(request):
    """Staff dashboard showing all T1 organizers with completion percentages."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    organizers = T1Organizer.objects.filter(firm=firm).select_related('client').order_by('-tax_year', '-created_at')

    # Stats
    total = organizers.count()
    submitted = organizers.filter(status__in=['submitted', 'under_review', 'complete']).count()
    in_progress = organizers.filter(status__in=['sent', 'in_progress']).count()
    not_started = organizers.filter(status='not_started').count()
    avg_completion = int(sum(o.completion_pct for o in organizers) / max(1, total))

    # Risk-flagged organizers
    with_risks = [o for o in organizers if o.risk_flags and len(o.risk_flags) > 0]

    return render(request, 'clients/t1_dashboard.html', {
        'firm': firm,
        'organizers': organizers,
        'total': total,
        'submitted': submitted,
        'in_progress': in_progress,
        'not_started': not_started,
        'avg_completion': avg_completion,
        'with_risks': with_risks,
    })


@login_required
def t1_create(request):
    """Create a new T1 organizer for a client."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    clients = Client.objects.filter(firm=firm)

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        tax_year = int(request.POST.get('tax_year', date.today().year - 1))
        language = request.POST.get('language', 'en')
        client = get_object_or_404(Client, id=client_id, firm=firm)

        # Check if already exists
        existing = T1Organizer.objects.filter(client=client, tax_year=tax_year).first()
        if existing:
            messages.warning(request, f'T1 {tax_year} already exists for {client.name}.')
            return redirect('t1_organizer_detail', organizer_id=existing.id)

        organizer = T1Organizer.objects.create(
            client=client, firm=firm, tax_year=tax_year, language=language, status='not_started',
        )
        generate_initial_documents(organizer)

        log_activity(request.user, 'create', 'T1Organizer', organizer.id, str(organizer),
                     f'T1 {tax_year} created for {client.name}', firm=firm)

        messages.success(request, f'T1 {tax_year} organizer created for {client.name}.')
        return redirect('t1_organizer_detail', organizer_id=organizer.id)

    return render(request, 'clients/t1_create.html', {
        'firm': firm, 'clients': clients,
        'current_year': date.today().year,
    })


@login_required
def t1_organizer_detail(request, organizer_id):
    """Staff view of a single T1 organizer — review, send, export."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    organizer = get_object_or_404(T1Organizer.objects.select_related('client'), id=organizer_id, firm=firm)
    documents = organizer.documents.all()
    questionnaire = get_questionnaire(organizer.language)

    organizer.calculate_completion()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'send_to_client':
            organizer.status = 'sent'
            organizer.sent_at = timezone.now()
            organizer.save()
            # Email client the link
            portal_url = f"{request.build_absolute_uri('/')}t1/{organizer.token}/"
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject=f'T1 {organizer.tax_year} Tax Organizer — {organizer.client.name}',
                    message=f"""Hi {organizer.client.name},

Your accountant has prepared your T1 {organizer.tax_year} Personal Tax Organizer.

Please complete the secure questionnaire and upload your tax documents here:
{portal_url}

This will help prepare your tax return accurately and ensure you claim all eligible deductions and credits.

Mortacc T1 Organizer""",
                    from_email='support@mortacc.com',
                    recipient_list=[organizer.client.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            messages.success(request, f'T1 organizer sent to {organizer.client.email}.')

        elif action == 'generate_summary':
            organizer.detect_risk_flags()
            organizer.generate_ai_summary()
            messages.success(request, 'AI summary and risk flags generated.')

        elif action == 'export':
            return t1_export_package(organizer)

        elif action == 'mark_complete':
            organizer.status = 'complete'
            organizer.save()
            log_activity(request.user, 'update', 'T1Organizer', organizer.id, str(organizer),
                         f'T1 {organizer.tax_year} marked complete for {organizer.client.name}', firm=firm)
            messages.success(request, 'T1 organizer marked as complete.')

        return redirect('t1_organizer_detail', organizer_id=organizer.id)

    return render(request, 'clients/t1_organizer_detail.html', {
        'firm': firm,
        'organizer': organizer,
        'documents': documents,
        'questionnaire': questionnaire,
        'portal_url': f"/t1/{organizer.token}/",
    })


def t1_export_package(organizer):
    """Generate export package CSV for the accountant."""
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="T1_{organizer.tax_year}_{organizer.client.name}.csv"'
    response.write('﻿')  # UTF-8 BOM

    writer = csv.writer(response)
    writer.writerow(['T1 Personal Tax Organizer — Export'])
    writer.writerow(['Client', organizer.client.name])
    writer.writerow(['Tax Year', organizer.tax_year])
    writer.writerow(['Status', organizer.get_status_display()])
    writer.writerow(['Completion', f'{organizer.completion_pct}%'])
    writer.writerow(['Language', organizer.language])
    writer.writerow([])

    writer.writerow(['PERSONAL INFORMATION'])
    writer.writerow(['Marital Status', organizer.get_marital_status_display() or 'Not provided'])
    writer.writerow(['Marital Status Changed', 'Yes' if organizer.marital_status_changed else 'No'])
    writer.writerow(['Address Changed', 'Yes' if organizer.address_changed else 'No'])
    writer.writerow(['Dependants', organizer.dependants])
    writer.writerow([])

    writer.writerow(['INCOME SOURCES'])
    for field in ['has_employment_income', 'has_self_employment', 'has_rental_income',
                  'has_investment_income', 'has_capital_gains', 'has_foreign_income', 'has_pension_income']:
        writer.writerow([field.replace('has_', '').replace('_', ' ').title(), 'Yes' if getattr(organizer, field) else 'No'])
    writer.writerow([])

    writer.writerow(['DEDUCTIONS & CREDITS'])
    for field in ['has_rrsp_deduction', 'has_childcare_expenses', 'has_medical_expenses',
                  'has_donations', 'has_tuition', 'has_rent_receipts', 'has_property_tax']:
        writer.writerow([field.replace('has_', '').replace('_', ' ').title(), 'Yes' if getattr(organizer, field) else 'No'])
    writer.writerow([])

    writer.writerow(['DOCUMENTS'])
    writer.writerow(['Type', 'Description', 'Status', 'File'])
    for doc in organizer.documents.all():
        writer.writerow([doc.get_doc_type_display(), doc.description, doc.get_status_display(),
                        doc.renamed_filename or doc.original_filename or ''])
    writer.writerow([])

    if organizer.risk_flags:
        writer.writerow(['RISK FLAGS'])
        for flag in organizer.risk_flags:
            writer.writerow([f'[{flag["level"].upper()}]', flag['message']])

    if organizer.ai_summary:
        writer.writerow([])
        writer.writerow(['AI SUMMARY'])
        writer.writerow([organizer.ai_summary])

    return response


@login_required
def t1_auto_prepare_view(request, organizer_id):
    """One-click T1 auto-prepare: estimate refund, find missing docs, generate review notes."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    from ..models import T1Organizer
    from ..t1_auto_prepare import full_t1_auto_prepare

    organizer = get_object_or_404(T1Organizer, id=organizer_id, firm=firm)
    result = full_t1_auto_prepare(organizer)

    messages.success(request,
        f'⚡ T1 {organizer.tax_year} auto-prepared for {organizer.client.name}! '
        f'Estimated {"refund" if result["estimate"]["net_refund"] > 0 else "owing"}: '
        f'${abs(result["estimate"]["net_refund"]):,.2f}. '
        f'{len(result["missing_documents"])} missing doc(s), '
        f'{len(result["opportunities"])} tax opportunit{"y" if len(result["opportunities"]) == 1 else "ies"}.'
    )

    return redirect('t1_organizer_detail', organizer_id=organizer.id)
