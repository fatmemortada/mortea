from functools import wraps
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from django.http import HttpResponseForbidden
from ..utils.missing_items import get_missing_items


_get_missing_items = get_missing_items


def require_permission(model_name, action):
    """
    Decorator that checks RBAC permissions before allowing access to a view.
    Must be applied AFTER @login_required in the decorator stack.

    Usage:  @login_required
            @require_permission('settings', 'view')
            def settings_view(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            firm = _get_firm(request.user)
            if not firm:
                from django.shortcuts import redirect
                return redirect('login')

            # Superusers bypass RBAC
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Check user's role assignments for this permission
            from ..models import UserRoleAssignment, PermissionAuditLog
            assignments = UserRoleAssignment.objects.filter(
                user=request.user, firm=firm, is_active=True
            ).select_related('role')

            for assignment in assignments:
                if assignment.role.has_permission(model_name, action):
                    return view_func(request, *args, **kwargs)

            # Permission denied — log and return 403
            PermissionAuditLog.objects.create(
                user=request.user, firm=firm,
                action=action, model_name=model_name,
                allowed=False, denied_reason=f'Missing {action} permission on {model_name}',
                ip_address=request.META.get('REMOTE_ADDR', None),
            )
            return HttpResponseForbidden(
                f"You don't have the '{action}' permission for {model_name}."
            )
        return _wrapped_view
    return decorator


def compute_health_score(client) -> dict:
    """Compute an entity health score (0-100) based on compliance, documents, profile, and billing."""
    from datetime import date
    today = date.today()

    # 1. Compliance (40 points) — based on overdue vs pending tasks
    tasks = client.compliance_tasks.all()
    total_tasks = len(tasks)
    if total_tasks == 0:
        compliance_score = 40  # No tasks yet = full points
    else:
        overdue = sum(1 for t in tasks if t.status == 'overdue' or (t.status == 'pending' and t.due_date < today))
        completed = sum(1 for t in tasks if t.status == 'completed')
        pending = total_tasks - overdue - completed
        ratio = (completed + pending * 0.5) / total_tasks if total_tasks > 0 else 0
        compliance_score = int(40 * ratio)

    # 2. Documents (30 points) — onboarding completeness
    missing = _get_missing_items(client)
    total_items = 9
    complete_items = total_items - len(missing)
    doc_score = int(30 * (complete_items / total_items)) if total_items > 0 else 0

    # 3. Profile (20 points) — corporate profile completeness
    profile = getattr(client, 'corporate_profile', None)
    if profile:
        checks = [
            bool(profile.jurisdiction),
            bool(profile.incorporation_date),
            bool(profile.business_number),
            bool(profile.registered_address),
            bool(profile.fiscal_year_end),
        ]
        profile_score = int(20 * (sum(checks) / len(checks)))
    else:
        profile_score = 0

    # 4. Billing (10 points) — invoice status
    invoices = client.invoices.all()
    total_inv = len(invoices)
    if total_inv == 0:
        billing_score = 10  # No invoices yet = full points
    else:
        overdue_inv = sum(1 for i in invoices if i.status == 'overdue')
        unpaid_inv = sum(1 for i in invoices if i.status == 'sent')
        billing_score = int(10 * (1 - (overdue_inv + unpaid_inv * 0.3) / total_inv))
        billing_score = max(0, billing_score)

    total = compliance_score + doc_score + profile_score + billing_score

    if total >= 80:
        grade, color, label = 'A', '#16a34a', 'Excellent'
    elif total >= 60:
        grade, color, label = 'B', '#2563eb', 'Good'
    elif total >= 40:
        grade, color, label = 'C', '#d97706', 'Needs Attention'
    elif total >= 20:
        grade, color, label = 'D', '#dc2626', 'At Risk'
    else:
        grade, color, label = 'F', '#991b1b', 'Critical'

    return {
        'score': total,
        'grade': grade,
        'color': color,
        'label': label,
        'breakdown': {
            'compliance': compliance_score,
            'documents': doc_score,
            'profile': profile_score,
            'billing': billing_score,
        },
    }


def _build_client_row(client):
    missing = _get_missing_items(client)

    bk_tasks = list(client.bookkeeping_tasks.all())
    bk_total = len(bk_tasks)
    bk_outstanding = sum(1 for t in bk_tasks if t.status != "completed")
    bk_unbilled = sum(1 for t in bk_tasks if t.status == "completed" and not t.billed)

    engagement = client.engagementletterrecord_set.last()
    has_engagement = engagement is not None

    if missing and not has_engagement:
        health = "red"
    elif missing or bk_outstanding > 2 or not has_engagement:
        health = "amber"
    else:
        health = "green"

    invoices = list(client.invoices.all())
    inv_outstanding = sum(1 for i in invoices if i.status in ("sent", "overdue"))
    inv_outstanding_amount = sum(i.amount for i in invoices if i.status in ("sent", "overdue"))
    inv_paid_amount = sum(i.amount for i in invoices if i.status == "paid")

    return {
        "client": client,
        "missing_items": missing,
        "onboarding_docs_count": len(list(client.onboarding_documents.all())),
        "minute_book_docs_count": len(list(client.minute_book_documents.all())),
        "is_submitted": client.onboarding_submitted_at is not None,
        "bk_outstanding": bk_outstanding,
        "bk_total": bk_total,
        "bk_unbilled": bk_unbilled,
        "has_engagement": has_engagement,
        "health": health,
        "inv_outstanding": inv_outstanding,
        "inv_outstanding_amount": float(inv_outstanding_amount),
        "inv_paid_amount": float(inv_paid_amount),
    }


def _get_firm(user):
    try:
        return user.userprofile.firm
    except Exception:
        return None


def generate_temp_password(length=10):
    import secrets
    import string
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def create_client_login_and_send_email(client):
    from django.contrib.auth.models import User
    from django.core.mail import send_mail
    from django.conf import settings

    user, created = User.objects.get_or_create(
        username=client.email,
        defaults={"email": client.email},
    )

    temp_password = generate_temp_password()
    user.email = client.email
    user.set_password(temp_password)
    user.save()

    profile = user.userprofile
    profile.role = "client"
    profile.portal_client = client
    profile.save()

    login_url = "https://www.mortacc.com/client/login/"
    if settings.DEBUG:
        login_url = "http://127.0.0.1:8000/client/login/"

    subject = "Your Mortacc client portal access"
    if created:
        message = (
            f"Hello {client.name},\n\n"
            f"Your client portal account has been created.\n\n"
            f"Login link:\n{login_url}\n\n"
            f"Email:\n{client.email}\n\n"
            f"Temporary password:\n{temp_password}\n\n"
            f"Please log in and change your password after your first sign in.\n\n"
            f"Thank you,\nMortacc Solutions Inc."
        )
    else:
        message = (
            f"Hello {client.name},\n\n"
            f"Your client portal access has been updated.\n\n"
            f"Login link:\n{login_url}\n\n"
            f"Email:\n{client.email}\n\n"
            f"Temporary password:\n{temp_password}\n\n"
            f"Please use this password to log in.\n\n"
            f"Thank you,\nMortacc Solutions Inc."
        )

    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", "support@mortacc.com"),
        [client.email],
        fail_silently=True,
    )


def _csv_response(filename_prefix):
    import csv
    from django.http import HttpResponse
    from django.utils import timezone
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename_prefix}_{timezone.now().strftime("%Y%m%d")}.csv"'
    response.write('﻿')
    return response
