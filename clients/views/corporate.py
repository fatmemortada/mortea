from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.http import Http404, HttpResponse
from django.db.models import Sum
from django_ratelimit.decorators import ratelimit

from ..models import (
    Client, OnboardingSubmission, OnboardingDocument, MinuteBookDocument,
    CorporateProfile, Director, Shareholder,
    ComplianceTask, CorporateLead, EngagementLetterRecord,
    AnnualFiling, log_activity,
)
from ..emails import send_submission_notification
from ._helpers import _get_firm, _get_missing_items


# ── Onboarding Portal (token-only) ──────────────────────────────────────────

@ratelimit(key='ip', rate='30/m', block=True)
def onboarding_portal(request, token):
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        return HttpResponse("Too many requests. Please wait a moment and try again.", status=429)

    client = get_object_or_404(Client, onboarding_token=token)
    submission, _ = OnboardingSubmission.objects.get_or_create(client=client)

    is_submitted = client.onboarding_submitted_at is not None
    can_edit = not is_submitted
    success_message = ""

    if request.method == "GET" and can_edit:
        remove = request.GET.get("remove")
        delete_doc = request.GET.get("delete_doc")
        if remove == "id_document":
            submission.id_document = None; submission.save()
            return redirect(f"/onboarding/{token}/?step=3")
        if remove == "tax_document":
            submission.tax_document = None; submission.save()
            return redirect(f"/onboarding/{token}/?step=4")
        if remove == "bank_document":
            submission.bank_document = None; submission.save()
            return redirect(f"/onboarding/{token}/?step=5")
        if delete_doc:
            OnboardingDocument.objects.filter(id=delete_doc, client=client).delete()
            return redirect(f"/onboarding/{token}/")

    if request.method == "POST" and can_edit:
        if "save_draft" in request.POST or "submit_final" in request.POST:
            submission.legal_full_name = request.POST.get("legal_full_name", "").strip()
            submission.phone_number = request.POST.get("phone_number", "").strip()
            submission.address = request.POST.get("address", "").strip()
            submission.business_name = request.POST.get("business_name", "").strip()
            submission.business_number = request.POST.get("business_number", "").strip()
            submission.service_needed = request.POST.get("service_needed", "").strip()
            submission.notes = request.POST.get("notes", "").strip()

            if "id_document" in request.FILES:
                submission.id_document = request.FILES["id_document"]
            if "tax_document" in request.FILES:
                submission.tax_document = request.FILES["tax_document"]
            if "bank_document" in request.FILES:
                submission.bank_document = request.FILES["bank_document"]

            for f in request.FILES.getlist("identity_files"):
                OnboardingDocument.objects.create(
                    client=client, category="identity",
                    document_name=f.name, file=f, uploaded_by="client",
                )
            for f in request.FILES.getlist("tax_files"):
                OnboardingDocument.objects.create(
                    client=client, category="tax",
                    document_name=f.name, file=f, uploaded_by="client",
                )
            for f in request.FILES.getlist("banking_files"):
                OnboardingDocument.objects.create(
                    client=client, category="banking",
                    document_name=f.name, file=f, uploaded_by="client",
                )
            for f in request.FILES.getlist("other_files"):
                OnboardingDocument.objects.create(
                    client=client, category="other",
                    document_name=f.name, file=f, uploaded_by="client",
                )
            for f in request.FILES.getlist("minute_book_files"):
                MinuteBookDocument.objects.create(
                    client=client, document_name=f.name,
                    file=f, uploaded_by="client",
                )

            submission.save()

            if "submit_final" in request.POST:
                client.onboarding_submitted_at = timezone.now()
                client.status = "in_review"
                client.save()
                send_submission_notification(client)
                # Fire workflow trigger
                from ..workflow_triggers import trigger_workflows
                trigger_workflows('onboarding_submitted', client.firm_id, {
                    'client_id': client.id, 'client_name': client.name,
                    'client_email': client.email,
                })
                return redirect("onboarding_success", token=token)

            client.status = "in_progress"
            client.save()

            save_draft_val = request.POST.get("save_draft", "")
            next_step = request.POST.get("next_step", "")
            if save_draft_val.startswith("step"):
                next_step = save_draft_val.replace("step", "")
            if next_step:
                return redirect(f"/onboarding/{token}/?step={next_step}")
            success_message = "Your progress has been saved. You can return to this link anytime to continue."

        elif request.POST.get("delete_portal_document"):
            OnboardingDocument.objects.filter(
                id=request.POST.get("document_id"), client=client
            ).delete()
        elif request.POST.get("delete_portal_minute_book_document"):
            MinuteBookDocument.objects.filter(
                id=request.POST.get("document_id"), client=client
            ).delete()
        elif "remove_id_document" in request.POST:
            submission.id_document = None; submission.save()
        elif "remove_tax_document" in request.POST:
            submission.tax_document = None; submission.save()
        elif "remove_bank_document" in request.POST:
            submission.bank_document = None; submission.save()

    missing_items = _get_missing_items(client)
    total = 9
    completed = total - len(missing_items)
    progress = round((completed / total) * 100)
    current_step = int(request.GET.get("step", 1))
    if current_step < 1 or current_step > 6:
        current_step = 1

    return render(request, "clients/onboarding_portal.html", {
        "client": client, "submission": submission,
        "completed": completed, "total": total, "progress": progress,
        "missing_items": missing_items, "current_step": current_step,
        "identity_documents": client.onboarding_documents.filter(category="identity"),
        "tax_documents": client.onboarding_documents.filter(category="tax"),
        "banking_documents": client.onboarding_documents.filter(category="banking"),
        "other_documents": client.onboarding_documents.filter(category="other"),
        "minute_book_documents": client.minute_book_documents.all(),
        "can_edit_uploads": can_edit, "success_message": success_message,
    })


def onboarding_success(request, token):
    client = get_object_or_404(Client, onboarding_token=token)
    missing_items = _get_missing_items(client)
    return render(request, "clients/onboarding_success.html", {
        "client": client, "missing_items": missing_items,
    })


# ── Corporate Views ─────────────────────────────────────────────────────────

def corporate_view(request):
    return render(request, "clients/corporate.html")


def corporate_intake_view(request):
    return render(request, "clients/corporate_intake.html")


@login_required
def incorporation_requests_view(request):
    profile = getattr(request.user, 'userprofile', None)
    firm = _get_firm(request.user) if profile else None

    leads = CorporateLead.objects.all().order_by('-submitted_at')

    if request.method == 'POST':
        lead_id = request.POST.get('lead_id')
        action = request.POST.get('action', '')
        if lead_id:
            lead = get_object_or_404(CorporateLead, id=lead_id)
            if action == 'in_progress':
                lead.status = 'in_progress'; lead.save()
            elif action == 'completed':
                lead.status = 'completed'; lead.save()
            elif action == 'new':
                lead.status = 'new'; lead.save()
            elif action == 'create_client':
                client_name = lead.company_name_1 if lead.company_name_1 else f"{lead.first_name} {lead.last_name}"
                existing = Client.objects.filter(email=lead.email).first()
                if not existing:
                    new_client = Client.objects.create(
                        firm=firm, name=client_name, email=lead.email,
                        phone=lead.phone or '', business_type=lead.company_name_1 or 'Incorporation',
                        client_type='business', status='not_started', language='english',
                    )
                    jurisdiction = lead.jurisdiction if lead.jurisdiction else 'federal'
                    CorporateProfile.objects.create(
                        client=new_client, jurisdiction=jurisdiction,
                        status='in_progress', registered_address=lead.registered_address or '',
                        notes=lead.notes or f'Created from incorporation lead #{lead.id}',
                    )
                    lead.status = 'in_progress'; lead.save()
                    # Fire workflow trigger
                    from ..workflow_triggers import trigger_workflows
                    trigger_workflows('client_created', firm.id, {
                        'client_id': new_client.id, 'client_name': new_client.name,
                        'client_email': new_client.email,
                    })
                    try:
                        log_activity(request.user, 'create', 'Client', new_client.id, new_client.name,
                                    f'Created client from incorporation lead #{lead.id}', firm=firm)
                    except Exception:
                        import logging
                        logger = logging.getLogger('clients')
                        logger.debug('Activity logging failed during lead conversion', exc_info=True)
                else:
                    if not hasattr(existing, 'corporate_profile'):
                        jurisdiction = lead.jurisdiction if lead.jurisdiction else 'federal'
                        CorporateProfile.objects.create(
                            client=existing, jurisdiction=jurisdiction,
                            status='in_progress', registered_address=lead.registered_address or '',
                            notes=lead.notes or f'Created from incorporation lead #{lead.id}',
                        )
                    lead.status = 'in_progress'; lead.save()

        return redirect('incorporation_requests')

    new_count = leads.filter(status='new').count()
    in_progress_count = leads.filter(status='in_progress').count()
    completed_count = leads.filter(status='completed').count()

    return render(request, 'clients/incorporation_requests.html', {
        'leads': leads, 'new_count': new_count,
        'in_progress_count': in_progress_count, 'completed_count': completed_count,
        'total_count': leads.count(), 'firm': firm,
    })


# ── Engagement Flow ─────────────────────────────────────────────────────────

def engagement_view(request):
    return render(request, "clients/engagement.html")


@ratelimit(key='ip', rate='10/h', block=True)
def engagement_submit_view(request):
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        return HttpResponse("Too many submissions. Please try again later.", status=429)

    if request.method != "POST":
        return redirect("engagement")

    lead = CorporateLead.objects.create(
        first_name=request.POST.get("first_name", "").strip(),
        last_name=request.POST.get("last_name", "").strip(),
        email=request.POST.get("email", "").strip(),
        phone=request.POST.get("phone", "").strip(),
        company_type=request.POST.get("company_type", "named").strip() or "named",
        company_name_1=request.POST.get("company_name_1", "").strip(),
        company_name_2=request.POST.get("company_name_2", "").strip(),
        company_name_3=request.POST.get("company_name_3", "").strip(),
        french_name_1=request.POST.get("french_name_1", "").strip(),
        french_name_2=request.POST.get("french_name_2", "").strip(),
        french_name_3=request.POST.get("french_name_3", "").strip(),
        jurisdiction=request.POST.get("jurisdiction", "").strip(),
        business_activity=request.POST.get("business_activity", "").strip(),
        registered_address=request.POST.get("registered_address", "").strip(),
        authorized_representative_name=request.POST.get("authorized_representative_name", "").strip(),
        authorized_representative_address=request.POST.get("authorized_representative_address", "").strip(),
        authorized_representative_email=request.POST.get("authorized_representative_email", "").strip(),
        authorized_representative_phone=request.POST.get("authorized_representative_phone", "").strip(),
        directors=request.POST.get("directors", "").strip(),
        officers=request.POST.get("officers", "").strip(),
        shareholders=request.POST.get("shareholders", "").strip(),
        notes=request.POST.get("notes", "").strip(),
        engagement_signed=request.POST.get("engagement_signed", "").strip().lower() == "yes",
    )

    EngagementLetterRecord.objects.create(
        lead=lead,
        full_name=f"{lead.first_name} {lead.last_name}",
        email=lead.email, phone=lead.phone,
        content_html=request.POST.get("content_html", ""),
    )

    sender = getattr(settings, "DEFAULT_FROM_EMAIL", "support@mortacc.com")
    company_display = lead.company_name_1 if lead.company_type == "named" else "Numbered Company"

    internal_body = f"""NEW INCORPORATION REQUEST\n{'=' * 50}
CLIENT: {lead.first_name} {lead.last_name} ({lead.email})\nPhone: {lead.phone or 'N/A'}
Jurisdiction: {lead.jurisdiction.upper()}\nCompany Type: {lead.company_type.capitalize()}
1st: {lead.company_name_1}\n2nd: {lead.company_name_2}\n3rd: {lead.company_name_3}
Engagement Signed: {'Yes' if lead.engagement_signed else 'No'}"""

    send_mail(
        f"New Incorporation Request — {company_display} ({lead.jurisdiction.upper()})",
        internal_body, sender, ["support@mortacc.com"], fail_silently=True,
    )
    send_mail(
        "We received your incorporation request — Mortacc",
        f"Hello {lead.first_name},\n\nThank you for submitting your incorporation request. We have received all your information and will begin processing it shortly.\n\nIf you have any questions, reach out to us at support@mortacc.com.\n\n—\nMortacc Solutions Inc.",
        sender, [lead.email], fail_silently=True,
    )

    return redirect("engagement_success")


def engagement_success_view(request):
    return render(request, "clients/engagement_success.html")


@login_required
def view_letter(request, id):
    record = get_object_or_404(EngagementLetterRecord, id=id)
    return render(request, "clients/view_letter.html", {"record": record})


# ── Entities ────────────────────────────────────────────────────────────────

@login_required
def entities_view(request):
    try:
        firm = request.user.userprofile.firm
    except Exception:
        return redirect('login')

    entities = CorporateProfile.objects.filter(
        client__firm=firm
    ).select_related('client').order_by('-created_at')

    active_count = entities.filter(status='active').count()
    in_progress_count = entities.filter(status='in_progress').count()

    return render(request, 'clients/entities.html', {
        'firm': firm, 'entities': entities,
        'active_count': active_count, 'in_progress_count': in_progress_count,
    })


@login_required
def entity_detail_view(request, client_id):
    try:
        firm = request.user.userprofile.firm
    except Exception:
        return redirect('login')

    client = get_object_or_404(Client, id=client_id, firm=firm)

    try:
        profile = client.corporate_profile
    except CorporateProfile.DoesNotExist:
        profile = None

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_director':
            name = request.POST.get('director_name', '').strip()
            officer_title = request.POST.get('officer_title', '').strip()
            if name:
                Director.objects.create(
                    client=client, full_name=name,
                    address=request.POST.get('director_address', '').strip(),
                    officer_title=officer_title,
                    is_officer=bool(officer_title),
                    appointment_date=request.POST.get('appointment_date') or None,
                )
            return redirect('entity_detail', client_id=client_id)
        elif action == 'add_shareholder':
            name = request.POST.get('shareholder_name', '').strip()
            if name:
                Shareholder.objects.create(
                    client=client, full_name=name,
                    share_class=request.POST.get('share_class', 'Common').strip(),
                    num_shares=int(request.POST.get('num_shares', 0)),
                    address=request.POST.get('shareholder_address', '').strip(),
                    acquisition_date=request.POST.get('acquisition_date') or None,
                )
            return redirect('entity_detail', client_id=client_id)

    directors = client.directors.all().order_by('full_name')
    officers = directors.filter(is_officer=True)
    shareholders = client.shareholders.all().order_by('full_name')
    compliance_tasks = client.compliance_tasks.all().order_by('due_date')
    total_shares = shareholders.aggregate(total=Sum('num_shares'))['total'] or 0

    # Timeline: recent activity for this entity
    from ..models import ActivityLog
    timeline = ActivityLog.objects.filter(
        target_id=client.id,
        target_type='Client',
    ).select_related('user').order_by('-created_at')[:30]

    return render(request, 'clients/entity_detail.html', {
        'firm': firm, 'client': client, 'profile': profile,
        'directors': directors, 'officers': officers,
        'shareholders': shareholders, 'compliance_tasks': compliance_tasks,
        'total_shares': total_shares, 'timeline': timeline,
    })


# ── Org Chart ───────────────────────────────────────────────────────────────

@login_required
def org_chart(request, client_id):
    try:
        firm = request.user.userprofile.firm
    except Exception:
        return redirect('login')
    client = get_object_or_404(Client, id=client_id, firm=firm)
    corporate_profile = getattr(client, 'corporate_profile', None)

    shareholders = client.shareholders.all()
    total_shares = sum(s.num_shares for s in shareholders if s.num_shares) or 1

    shareholders_data = []
    for s in shareholders:
        shares = s.num_shares or 0
        pct = round((shares / total_shares) * 100, 1)
        shareholders_data.append({
            'name': s.full_name, 'shares': shares,
            'pct': pct, 'share_class': s.share_class,
        })

    directors = client.directors.all()
    directors_data = []
    for d in directors:
        title = f"Director & {d.officer_title}" if (d.is_officer and d.officer_title) else 'Director'
        directors_data.append({'name': d.full_name, 'title': title})

    context = {
        'client': client, 'corporate_profile': corporate_profile,
        'shareholders': shareholders_data, 'directors': directors_data,
        'total_shares': total_shares,
        'corporation_name': corporate_profile.corporation_name if corporate_profile and corporate_profile.corporation_name else client.name,
    }
    return render(request, 'clients/org_chart.html', context)


@login_required
def structure_charts_view(request):
    try:
        firm = request.user.userprofile.firm
    except Exception:
        return redirect('login')

    entities = CorporateProfile.objects.filter(
        client__firm=firm
    ).select_related('client').order_by('client__name')

    return render(request, 'clients/structure_charts.html', {
        'firm': firm, 'entities': entities,
    })
