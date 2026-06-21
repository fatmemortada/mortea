from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
import secrets

from ..models import Client, UserProfile, OnboardingDocument, BookkeepingTask, BookkeepingDocument


def client_login_view(request):
    if request.user.is_authenticated:
        try:
            if request.user.userprofile.role == "client":
                return redirect("client_portal")
            return redirect("dashboard")
        except Exception:
            return redirect("dashboard")

    error_message = ""

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            try:
                if user.userprofile.role == "client":
                    return redirect("client_portal")
                return redirect("dashboard")
            except Exception:
                return redirect("dashboard")
        else:
            error_message = "Invalid email or password."

    return render(request, "clients/client_login.html", {"error_message": error_message})


@login_required
def client_portal_view(request):
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        return redirect("client_login")

    if profile.role != "client" or not profile.portal_client:
        return redirect("login")

    client = profile.portal_client
    engagement = client.engagementletterrecord_set.order_by("-signed_at").first()
    documents = client.onboarding_documents.order_by("-uploaded_at")

    if request.method == "POST" and "upload_bk_doc" in request.POST:
        task_id = request.POST.get("task_id")
        uploaded_file = request.FILES.get("bk_file")
        category = request.POST.get("bk_category", "other")
        if task_id and uploaded_file:
            task = get_object_or_404(BookkeepingTask, id=task_id, client=client)
            BookkeepingDocument.objects.create(
                task=task, category=category,
                document_name=uploaded_file.name, file=uploaded_file,
                uploaded_by="client",
            )
        return redirect("client_portal")

    bookkeeping_tasks = client.bookkeeping_tasks.order_by("-year", "month")
    visible_tasks = client.chasing_tasks.filter(
        is_client_visible=True, status__in=["pending", "in_progress"]
    ).order_by("due_date")
    invoices = client.invoices.filter(status__in=["sent", "paid", "overdue"]).order_by("-invoice_date")

    corporate_profile = getattr(client, 'corporate_profile', None)
    return render(request, "clients/client_portal.html", {
        "client": client, "engagement": engagement, "documents": documents,
        "bookkeeping_tasks": bookkeeping_tasks, "visible_tasks": visible_tasks,
        "invoices": invoices, "corporate_profile": corporate_profile,
    })


@login_required
def client_upload_document_view(request):
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        return redirect("client_login")

    if profile.role != "client" or not profile.portal_client:
        return redirect("login")

    client = profile.portal_client

    if request.method == "POST":
        category = request.POST.get("category", "").strip()
        document_name = request.POST.get("document_name", "").strip()
        uploaded_file = request.FILES.get("file")

        if category and document_name and uploaded_file:
            OnboardingDocument.objects.create(
                client=client, category=category,
                document_name=document_name, file=uploaded_file,
                uploaded_by="client",
            )

    return redirect("client_portal")


# ── Client Password Reset ──────────────────────────────────────────────────

def client_password_reset_request(request):
    """Self-service password reset for client portal users. Sends email with token link."""
    success = False

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if email:
            try:
                user = User.objects.get(username=email)
                profile = user.userprofile
                if profile.role == "client" and profile.portal_client:
                    token = secrets.token_urlsafe(32)
                    request.session[f'pwd_reset_{token}'] = user.id
                    request.session[f'pwd_exp_{token}'] = (
                        timezone.now() + timezone.timedelta(hours=1)
                    ).isoformat()

                    site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
                    send_mail(
                        subject="Password reset — Mortacc Client Portal",
                        message=(
                            f"Hello,\n\n"
                            f"Reset your password here:\n"
                            f"{site_url}/client/reset-password/{token}/\n\n"
                            f"This link expires in 1 hour.\n\n"
                            f"— Mortacc"
                        ),
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mortacc.com'),
                        recipient_list=[email],
                        fail_silently=True,
                    )
                success = True
            except (User.DoesNotExist, UserProfile.DoesNotExist):
                success = True  # Prevent email enumeration

    return render(request, "clients/client_password_reset.html", {"success": success})


def client_password_reset_confirm(request, token):
    """Validate reset token and allow user to set a new password."""
    error = ""
    user_id = request.session.get(f'pwd_reset_{token}')
    expiry_str = request.session.get(f'pwd_exp_{token}')

    if not user_id or not expiry_str:
        return render(request, "clients/client_password_reset_confirm.html", {
            "error": "This reset link is invalid or has expired.", "done": False,
        })

    from django.utils.dateparse import parse_datetime
    expiry = parse_datetime(expiry_str)
    if expiry and timezone.now() > expiry:
        return render(request, "clients/client_password_reset_confirm.html", {
            "error": "This reset link has expired. Please request a new one.", "done": False,
        })

    if request.method == "POST":
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")
        if len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            try:
                user = User.objects.get(id=user_id)
                user.set_password(password)
                user.save()
                request.session.pop(f'pwd_reset_{token}', None)
                request.session.pop(f'pwd_exp_{token}', None)
                return render(request, "clients/client_password_reset_confirm.html", {
                    "done": True, "error": "",
                })
            except User.DoesNotExist:
                error = "User not found."

    return render(request, "clients/client_password_reset_confirm.html", {
        "error": error, "done": False,
    })
