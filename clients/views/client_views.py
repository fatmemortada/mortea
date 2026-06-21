from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from decimal import Decimal

from ..models import (
    Client, CorporateProfile, Director, Shareholder, AnnualFiling,
    OnboardingDocument, MinuteBookDocument, BookkeepingTask,
    BookkeepingDocument, ChasingTask, Invoice, ComplianceTask, Message,
)
from ..emails import send_missing_docs_reminder
from ._helpers import _get_firm, _get_missing_items, compute_health_score


@login_required
def client_detail(request, client_id):
    firm = _get_firm(request.user)
    client = get_object_or_404(Client, id=client_id, firm=firm)
    active_tab = request.GET.get("tab", "overview")
    reminder_sent = False

    if request.method == "POST":
        active_tab = request.POST.get("active_tab", "overview")

        if "save_client_record" in request.POST:
            client.phone = request.POST.get("phone", "").strip()
            client.business_type = request.POST.get("business_type", "").strip()
            new_status = request.POST.get("status", "").strip()
            if new_status in dict(Client.STATUS_CHOICES):
                client.status = new_status
            new_language = request.POST.get("language", "english").strip()
            if new_language in ["english", "french"]:
                client.language = new_language
            client.save()

        elif "reopen_submission" in request.POST:
            client.status = "in_progress"
            client.onboarding_submitted_at = None
            client.save()

        elif "send_reminder" in request.POST:
            missing = _get_missing_items(client)
            if missing:
                send_missing_docs_reminder(client, missing)
                reminder_sent = True

        elif "accountant_upload_identity" in request.POST:
            for f in request.FILES.getlist("identity_files"):
                OnboardingDocument.objects.create(
                    client=client, category="identity",
                    document_name=f.name, file=f, uploaded_by="accountant",
                )

        elif "accountant_upload_tax" in request.POST:
            for f in request.FILES.getlist("tax_files"):
                OnboardingDocument.objects.create(
                    client=client, category="tax",
                    document_name=f.name, file=f, uploaded_by="accountant",
                )

        elif "accountant_upload_banking" in request.POST:
            for f in request.FILES.getlist("banking_files"):
                OnboardingDocument.objects.create(
                    client=client, category="banking",
                    document_name=f.name, file=f, uploaded_by="accountant",
                )

        elif "accountant_upload_other" in request.POST:
            for f in request.FILES.getlist("other_files"):
                OnboardingDocument.objects.create(
                    client=client, category="other",
                    document_name=f.name, file=f, uploaded_by="accountant",
                )

        elif "delete_onboarding_document" in request.POST:
            OnboardingDocument.objects.filter(
                id=request.POST.get("document_id"), client=client
            ).delete()

        elif "accountant_upload_minute_book" in request.POST:
            for f in request.FILES.getlist("minute_book_files"):
                MinuteBookDocument.objects.create(
                    client=client, document_name=f.name,
                    file=f, uploaded_by="accountant",
                )

        elif "delete_minute_book_document" in request.POST:
            MinuteBookDocument.objects.filter(
                id=request.POST.get("document_id"), client=client
            ).delete()

        elif "save_corporate" in request.POST:
            corp, _ = CorporateProfile.objects.get_or_create(client=client)
            corp.jurisdiction = request.POST.get("corp_jurisdiction", "")
            corp.status = request.POST.get("corp_status", "in_progress")
            corp.business_number = request.POST.get("corp_business_number", "")
            corp.hst_number = request.POST.get("corp_hst_number", "")
            corp.fiscal_year_end = request.POST.get("corp_fiscal_year_end", "")
            corp.registered_address = request.POST.get("corp_registered_address", "")
            corp.notes = request.POST.get("corp_notes", "")
            inc_date = request.POST.get("corp_incorporation_date")
            ard = request.POST.get("corp_annual_return_due")
            if inc_date:
                corp.incorporation_date = inc_date
            if ard:
                corp.annual_return_due = ard
            corp.save()

        elif "add_director" in request.POST:
            name = request.POST.get("dir_name", "").strip()
            if name:
                Director.objects.create(
                    client=client, full_name=name,
                    address=request.POST.get("dir_address", ""),
                    appointment_date=request.POST.get("dir_appointment_date") or None,
                    is_officer=request.POST.get("dir_is_officer") == "1",
                    officer_title=request.POST.get("dir_officer_title", ""),
                )

        elif "delete_director" in request.POST:
            Director.objects.filter(id=request.POST.get("delete_director"), client=client).delete()

        elif "add_shareholder" in request.POST:
            name = request.POST.get("sh_name", "").strip()
            if name:
                Shareholder.objects.create(
                    client=client, full_name=name,
                    address=request.POST.get("sh_address", ""),
                    share_class=request.POST.get("sh_share_class", "Common"),
                    num_shares=int(request.POST.get("sh_num_shares") or 0),
                    acquisition_date=request.POST.get("sh_acquisition_date") or None,
                )

        elif "delete_shareholder" in request.POST:
            Shareholder.objects.filter(id=request.POST.get("delete_shareholder"), client=client).delete()

        elif "add_filing" in request.POST:
            year = request.POST.get("filing_year", "").strip()
            due_date = request.POST.get("filing_due_date", "").strip()
            if year and due_date:
                AnnualFiling.objects.create(
                    client=client, year=int(year), due_date=due_date,
                    notes=request.POST.get("filing_notes", ""),
                )

        elif "mark_filed" in request.POST:
            AnnualFiling.objects.filter(
                id=request.POST.get("mark_filed"), client=client
            ).update(status="filed", filed_date=timezone.now().date())

        elif "add_bookkeeping_month" in request.POST:
            month = request.POST.get("bk_month", "").strip()
            year = request.POST.get("bk_year", "").strip()
            if month and year:
                BookkeepingTask.objects.get_or_create(
                    client=client, month=month, year=int(year),
                    defaults={"status": "not_started"},
                )

        elif "update_bookkeeping" in request.POST:
            task_id = request.POST.get("task_id")
            task = get_object_or_404(BookkeepingTask, id=task_id, client=client)
            task.status = request.POST.get("bk_status", task.status)
            task.hst_status = request.POST.get("bk_hst_status", task.hst_status)
            task.billed = request.POST.get("bk_billed") == "on"
            task.notes = request.POST.get("bk_notes", task.notes)
            task.save()

        elif "upload_bookkeeping_doc" in request.POST:
            task_id = request.POST.get("task_id")
            task = get_object_or_404(BookkeepingTask, id=task_id, client=client)
            uploaded_file = request.FILES.get("bk_file")
            if uploaded_file:
                BookkeepingDocument.objects.create(
                    task=task, category=request.POST.get("bk_category", "other"),
                    document_name=uploaded_file.name, file=uploaded_file,
                    uploaded_by="accountant",
                )

        elif "delete_bookkeeping_doc" in request.POST:
            doc_id = request.POST.get("doc_id")
            BookkeepingDocument.objects.filter(id=doc_id, task__client=client).delete()

        elif "delete_bookkeeping_month" in request.POST:
            task_id = request.POST.get("task_id")
            BookkeepingTask.objects.filter(id=task_id, client=client).delete()

        elif "add_chasing_task" in request.POST:
            title = request.POST.get("chase_title", "").strip()
            if title:
                ChasingTask.objects.create(
                    client=client, title=title,
                    description=request.POST.get("chase_description", ""),
                    due_date=request.POST.get("chase_due_date") or None,
                    is_client_visible=request.POST.get("chase_visible") == "on",
                    status="pending",
                )

        elif "update_chasing_task" in request.POST:
            chase_id = request.POST.get("chase_id")
            chase = get_object_or_404(ChasingTask, id=chase_id, client=client)
            chase.status = request.POST.get("chase_status", chase.status)
            chase.title = request.POST.get("chase_title", chase.title)
            chase.description = request.POST.get("chase_description", chase.description)
            chase.due_date = request.POST.get("chase_due_date") or None
            chase.is_client_visible = request.POST.get("chase_visible") == "on"
            chase.save()

        elif "delete_chasing_task" in request.POST:
            chase_id = request.POST.get("chase_id")
            ChasingTask.objects.filter(id=chase_id, client=client).delete()

        elif "add_invoice" in request.POST:
            amount = request.POST.get("inv_amount", "0").strip()
            description = request.POST.get("inv_description", "").strip()
            if description and amount:
                count = client.invoices.count() + 1
                Invoice.objects.create(
                    client=client,
                    invoice_number=f"{client.client_token}-{count:03d}",
                    description=description,
                    service_type=request.POST.get("inv_service_type", "other"),
                    amount=Decimal(amount), status="draft",
                    invoice_date=request.POST.get("inv_date") or timezone.now().date(),
                    due_date=request.POST.get("inv_due_date") or None,
                    notes=request.POST.get("inv_notes", ""),
                )

        elif "update_invoice_status" in request.POST:
            inv_id = request.POST.get("inv_id")
            inv = get_object_or_404(Invoice, id=inv_id, client=client)
            new_status = request.POST.get("inv_status")
            inv.status = new_status
            if new_status == "paid" and not inv.paid_date:
                inv.paid_date = timezone.now().date()
            inv.save()

        elif "delete_invoice" in request.POST:
            inv_id = request.POST.get("inv_id")
            Invoice.objects.filter(id=inv_id, client=client).delete()

        elif "send_message" in request.POST:
            body = request.POST.get("message_body", "").strip()
            if body:
                Message.objects.create(client=client, sender=request.user, body=body)

        return redirect(f"{request.path}?tab={active_tab}")

    submission = getattr(client, "submission", None)
    missing_items = _get_missing_items(client)
    is_submitted = client.onboarding_submitted_at is not None

    identity_documents = client.onboarding_documents.filter(category="identity")
    tax_documents = client.onboarding_documents.filter(category="tax")
    banking_documents = client.onboarding_documents.filter(category="banking")
    other_documents = client.onboarding_documents.filter(category="other")

    doc_sections = [
        ("Identity Documents", "identity", identity_documents),
        ("Tax Documents", "tax", tax_documents),
        ("Banking Documents", "banking", banking_documents),
        ("Other Documents", "other", other_documents),
    ]

    corp, _ = CorporateProfile.objects.get_or_create(client=client)
    health = compute_health_score(client)

    return render(request, "clients/client_detail.html", {
        "client": client, "active_tab": active_tab,
        "health": health,
        "submission": submission, "missing_items": missing_items,
        "identity_documents": identity_documents,
        "tax_documents": tax_documents,
        "banking_documents": banking_documents,
        "other_documents": other_documents,
        "minute_book_documents": client.minute_book_documents.all(),
        "is_submitted": is_submitted, "reminder_sent": reminder_sent,
        "doc_sections": doc_sections, "corp": corp,
        "directors": client.directors.all(),
        "shareholders": client.shareholders.all(),
        "annual_filings": client.annual_filings.all(),
        "bookkeeping_tasks": client.bookkeeping_tasks.order_by("-year", "month"),
        "chasing_tasks": client.chasing_tasks.order_by("status", "due_date"),
        "today": timezone.now().date(), "invoices": client.invoices.all(),
        "messages": client.messages.select_related('sender').order_by('created_at')[:50],
    })


@login_required
def review_client_document(request, document_id):
    document = get_object_or_404(OnboardingDocument, id=document_id)

    if request.method == "POST":
        action = request.POST.get("action")
        note = request.POST.get("review_note", "").strip()

        if action == "approve":
            document.review_status = "approved"
            status_text = "APPROVED"; status_line = "Approved"
        elif action == "reject":
            document.review_status = "rejected"
            status_text = "REJECTED"; status_line = "Rejected"
        else:
            return redirect("client_detail", client_id=document.client.id)

        document.review_note = note
        document.reviewed_at = timezone.now()
        document.reviewed_by = request.user
        document.save()

        client = document.client
        subject = f"Document {status_text} — {document.document_name}"
        message = (
            f"Hello {client.name},\n\n"
            f"Your document has been reviewed.\n\n"
            f"Document:\n{document.document_name}\n\n"
            f"Status:\n{status_line}\n"
        )
        if note:
            message += f"\nReview note from your accountant:\n{note}\n"
        message += (
            f"\nYou can log in to your client portal to view details:\n"
            f"https://www.mortacc.com/client/login/\n\n"
            f"Thank you,\nMortacc Solutions Inc."
        )

        send_mail(
            subject, message.strip(),
            getattr(settings, "DEFAULT_FROM_EMAIL", "support@mortacc.com"),
            [client.email], fail_silently=True,
        )

    return redirect("client_detail", client_id=document.client.id)


@login_required
def client_dashboard(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    corporate_profile = getattr(client, 'corporate_profile', None)
    today = timezone.now().date()

    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        action = request.POST.get('action')

        if task_id and action:
            task = get_object_or_404(ComplianceTask, id=task_id, client=client)
            if action == 'complete':
                task.status = 'completed'
                task.completed_at = timezone.now()
                task.save()
            elif action == 'reopen':
                task.status = 'pending'
                task.completed_at = None
                task.save()
            elif action == 'waive':
                task.status = 'waived'
                task.save()

        return redirect('client_dashboard', client_id=client_id)

    client.compliance_tasks.filter(status='pending', due_date__lt=today).update(status='overdue')

    all_tasks = client.compliance_tasks.all()
    upcoming_tasks = all_tasks.exclude(status='completed').order_by('due_date')
    completed_tasks = all_tasks.filter(status='completed').order_by('-completed_at')

    documents = client.platform_documents.all().order_by('-created_at')
    invoices = client.invoices.all()[:5]

    context = {
        'client': client, 'corporate_profile': corporate_profile,
        'upcoming_tasks': upcoming_tasks, 'completed_tasks': completed_tasks,
        'documents': documents, 'invoices': invoices, 'today': today,
    }
    return render(request, 'clients/client_dashboard.html', context)
