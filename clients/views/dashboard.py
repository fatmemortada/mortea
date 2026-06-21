from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum

from ..models import (
    Client, Firm, UserProfile, BookkeepingTask, Invoice,
    CorporateLead, PlatformAgreement, log_activity, trigger_webhook,
)
from ..emails import send_client_invitation, send_missing_docs_reminder
from ._helpers import _get_firm, _build_client_row, _get_missing_items, create_client_login_and_send_email


@login_required
def dashboard(request):
    profile = getattr(request.user, 'userprofile', None)
    if profile and profile.role in ('accountant', 'admin', 'staff'):
        if not hasattr(request.user, 'platform_agreement'):
            return redirect('sign_platform_agreement')

    firm = _get_firm(request.user)
    reminder_sent = None

    if request.method == "POST":
        if "client_name" in request.POST and not any(
            k in request.POST for k in [
                "delete_client", "mark_in_progress", "mark_in_review",
                "mark_done", "mark_not_started", "reopen_submission", "send_reminder",
            ]
        ):
            name = request.POST.get("client_name", "").strip()
            email = request.POST.get("client_email", "").strip()
            phone = request.POST.get("phone", "").strip()
            business_type = request.POST.get("business_type", "").strip()
            client_type = request.POST.get("client_type", "individual")

            if name and email:
                profile = getattr(request.user, "userprofile", None)
                max_clients = profile.get_plan_limit("max_clients") if profile else 10
                current_count = Client.objects.filter(firm=firm).count()
                if max_clients is not None and current_count >= max_clients:
                    return redirect("dashboard")

                new_client = Client.objects.create(
                    firm=firm, name=name, email=email, phone=phone,
                    business_type=business_type, client_type=client_type,
                    status="not_started",
                )
                create_client_login_and_send_email(new_client)
                send_client_invitation(new_client)
                log_activity(request.user, 'create', 'Client', new_client.id, new_client.name,
                            f'Added client {new_client.name}', firm=firm)
                trigger_webhook('client.created', firm, {
                    'id': new_client.id, 'name': new_client.name, 'email': new_client.email,
                    'client_token': new_client.client_token, 'status': new_client.status,
                })

            return redirect("dashboard")

        client_id = request.POST.get("client_id")
        if client_id:
            client = get_object_or_404(Client, id=client_id, firm=firm)

            if "delete_client" in request.POST:
                client_name = client.name
                client.delete()
                log_activity(request.user, 'delete', 'Client', None, client_name,
                            f'Deleted client {client_name}', firm=firm)
                trigger_webhook('client.deleted', firm, {
                    'id': client_id, 'name': client_name,
                })
            elif "mark_in_progress" in request.POST:
                client.status = "in_progress"; client.save()
                trigger_webhook('client.updated', firm, {
                    'id': client.id, 'name': client.name, 'status': 'in_progress',
                })
            elif "mark_in_review" in request.POST:
                client.status = "in_review"; client.save()
                trigger_webhook('client.updated', firm, {
                    'id': client.id, 'name': client.name, 'status': 'in_review',
                })
            elif "mark_done" in request.POST:
                client.status = "completed"; client.save()
                trigger_webhook('client.updated', firm, {
                    'id': client.id, 'name': client.name, 'status': 'completed',
                })
            elif "mark_not_started" in request.POST:
                client.status = "not_started"; client.save()
                trigger_webhook('client.updated', firm, {
                    'id': client.id, 'name': client.name, 'status': 'not_started',
                })
            elif "reopen_submission" in request.POST:
                client.status = "in_progress"
                client.onboarding_submitted_at = None
                client.save()
                trigger_webhook('client.updated', firm, {
                    'id': client.id, 'name': client.name, 'status': 'in_progress', 'reopened': True,
                })
            elif "send_reminder" in request.POST:
                missing = _get_missing_items(client)
                if missing:
                    send_missing_docs_reminder(client, missing)
                    reminder_sent = client.id

        # ── Bulk actions ──────────────────────────────────────────────────
        if "bulk_action" in request.POST:
            client_ids = request.POST.getlist("bulk_client_ids")
            action = request.POST.get("bulk_action", "")
            if client_ids and action:
                clients_qs = Client.objects.filter(id__in=client_ids, firm=firm)
                if action == "mark_in_progress":
                    clients_qs.update(status="in_progress")
                elif action == "mark_completed":
                    clients_qs.update(status="completed")
                elif action == "bulk_reminder":
                    for c in clients_qs:
                        missing = _get_missing_items(c)
                        if missing:
                            send_missing_docs_reminder(c, missing)
                elif action == "bulk_delete":
                    clients_qs.delete()
                    log_activity(request.user, 'delete', 'Client', None, f'{len(client_ids)} clients',
                                f'Bulk deleted {len(client_ids)} clients', firm=firm)
            return redirect("dashboard")

        return redirect("dashboard")

    clients = (
        Client.objects.filter(firm=firm)
        .select_related("submission")
        .prefetch_related(
            "bookkeeping_tasks", "invoices",
            "engagementletterrecord_set", "onboarding_documents",
            "minute_book_documents",
        )
        .order_by("name")
    ) if firm else Client.objects.none()
    client_rows = [_build_client_row(c) for c in clients]

    needs_attention = [r for r in client_rows if r["health"] in ("red", "amber")]

    all_bk_tasks = BookkeepingTask.objects.filter(client__firm=firm)
    bk_outstanding_total = all_bk_tasks.exclude(status="completed").count()
    bk_unbilled_total = all_bk_tasks.filter(status="completed", billed=False).count()

    all_invoices = Invoice.objects.filter(client__firm=firm)
    inv_outstanding_amount = (
        all_invoices.filter(status__in=["sent", "overdue"])
        .aggregate(total=Sum("amount"))["total"] or 0
    )
    inv_paid_this_month = (
        all_invoices.filter(status="paid", paid_date__month=timezone.now().month)
        .aggregate(total=Sum("amount"))["total"] or 0
    )

    profile = getattr(request.user, "userprofile", None)
    plan = profile.plan if profile else "starter"
    max_clients = profile.get_plan_limit("max_clients") if profile else 10
    client_count = clients.count()
    at_client_limit = (max_clients is not None and client_count >= max_clients)
    can_use_engagement_letters = profile.get_plan_limit("engagement_letters") if profile else False

    incorporation_leads = CorporateLead.objects.filter(
        status__in=['new', 'in_progress']
    ).order_by('-submitted_at')[:20]

    # ── Dashboard widgets: recent activity & upcoming deadlines ─────
    from ..models import ActivityLog, ComplianceTask, AnnualFiling
    today = timezone.now().date()
    thirty_days = today + timezone.timedelta(days=30)

    recent_activity = ActivityLog.objects.filter(
        firm=firm
    ).select_related('user').order_by('-created_at')[:8]

    # Upcoming deadlines (merged compliance + annual filings + invoices)
    upcoming_deadlines = []
    for t in ComplianceTask.objects.filter(
        client__firm=firm, status__in=['pending', 'in_progress'],
        due_date__gte=today, due_date__lte=thirty_days,
    ).select_related('client').order_by('due_date')[:10]:
        days = (t.due_date - today).days
        upcoming_deadlines.append({
            'name': t.client.name, 'title': t.title,
            'due_date': t.due_date, 'days': days, 'type': 'compliance',
        })
    for f in AnnualFiling.objects.filter(
        client__firm=firm, status='pending',
        due_date__gte=today, due_date__lte=thirty_days,
    ).select_related('client').order_by('due_date')[:5]:
        days = (f.due_date - today).days
        upcoming_deadlines.append({
            'name': f.client.name, 'title': f'Annual Filing — {f.year}',
            'due_date': f.due_date, 'days': days, 'type': 'filing',
        })
    upcoming_deadlines.sort(key=lambda x: x['days'])
    upcoming_deadlines = upcoming_deadlines[:10]

    return render(request, "clients/dashboard.html", {
        "firm": firm,
        "client_rows": client_rows,
        "in_progress_count": clients.filter(status="in_progress").count(),
        "needs_review_count": clients.filter(status="in_review").count(),
        "completed_count": clients.filter(status="completed").count(),
        "reminder_sent": reminder_sent,
        "needs_attention": needs_attention,
        "bk_outstanding_total": bk_outstanding_total,
        "bk_unbilled_total": bk_unbilled_total,
        "inv_outstanding_amount": inv_outstanding_amount,
        "inv_paid_this_month": inv_paid_this_month,
        "incorporation_leads": incorporation_leads,
        "recent_activity": recent_activity,
        "upcoming_deadlines": upcoming_deadlines,
        "incorporation_count": incorporation_leads.count(),
        "plan": plan, "client_count": client_count,
        "max_clients": max_clients, "at_client_limit": at_client_limit,
        "can_use_engagement_letters": can_use_engagement_letters,
    })


@login_required
def admin_dashboard(request):
    firm = _get_firm(request.user)
    clients = Client.objects.filter(firm=firm).prefetch_related(
        'compliance_tasks', 'invoices', 'corporate_profile'
    ).order_by('name') if firm else Client.objects.none()

    today = timezone.now().date()

    from ..models import ComplianceTask
    ComplianceTask.objects.filter(
        client__firm=firm, status='pending', due_date__lt=today,
    ).update(status='overdue')

    rows = []
    for client in clients:
        tasks = client.compliance_tasks.all()
        overdue  = tasks.filter(status='overdue').count()
        upcoming = tasks.filter(status='pending').count()
        completed = tasks.filter(status='completed').count()

        next_task = tasks.filter(
            status__in=['pending', 'overdue']
        ).order_by('due_date').first()

        invoices = client.invoices.all()
        unpaid_amount = sum(
            i.amount for i in invoices.filter(status__in=['sent', 'overdue'])
        )

        corp = getattr(client, 'corporate_profile', None)

        if overdue > 0:
            health = 'red'
        elif upcoming > 3 or unpaid_amount > 0:
            health = 'amber'
        else:
            health = 'green'

        rows.append({
            'client': client, 'corp': corp,
            'overdue': overdue, 'upcoming': upcoming, 'completed': completed,
            'next_task': next_task, 'unpaid_amount': unpaid_amount,
            'health': health,
        })

    total_clients = len(rows)
    red_count = sum(1 for r in rows if r['health'] == 'red')
    amber_count = sum(1 for r in rows if r['health'] == 'amber')
    green_count = sum(1 for r in rows if r['health'] == 'green')
    total_overdue = sum(r['overdue'] for r in rows)

    # Chart data: revenue by month (last 6 months)
    import datetime
    monthly_labels = []
    monthly_revenue = []
    for i in range(5, -1, -1):
        d = today - datetime.timedelta(days=30*i)
        m_start = d.replace(day=1)
        if m_start.month == 12:
            m_end = m_start.replace(year=m_start.year+1, month=1, day=1)
        else:
            m_end = m_start.replace(month=m_start.month+1, day=1)
        amt = Invoice.objects.filter(
            client__firm=firm, status='paid', paid_date__gte=m_start, paid_date__lt=m_end
        ).aggregate(t=Sum('amount'))['t'] or 0
        monthly_labels.append(d.strftime('%b'))
        monthly_revenue.append(float(amt))

    # Chart data: entity status distribution
    status_labels = ['Active', 'In Progress', 'Inactive', 'Dissolved']
    status_data = [
        sum(1 for r in rows if r.get('corp') and r['corp'].status == 'active'),
        sum(1 for r in rows if r.get('corp') and r['corp'].status == 'in_progress'),
        sum(1 for r in rows if r.get('corp') and r['corp'].status == 'inactive'),
        sum(1 for r in rows if r.get('corp') and r['corp'].status == 'dissolved'),
    ]

    return render(request, 'clients/admin_dashboard.html', {
        'rows': rows, 'today': today,
        'total_clients': total_clients, 'red_count': red_count,
        'amber_count': amber_count, 'green_count': green_count,
        'total_overdue': total_overdue,
        'monthly_labels': monthly_labels, 'monthly_revenue': monthly_revenue,
        'status_labels': status_labels, 'status_data': status_data,
    })


@login_required
def mortacc_admin_view(request):
    if not request.user.is_superuser:
        return redirect('dashboard')

    firms = Firm.objects.all().order_by('name')
    rows = []
    total_clients = 0
    active_subscriptions = 0
    agreements_signed = 0

    for firm in firms:
        owner_profile = UserProfile.objects.filter(firm=firm).order_by('id').first()
        if not owner_profile:
            continue

        owner = owner_profile.user
        client_count = Client.objects.filter(firm=firm).count()
        total_clients += client_count

        agreement = None
        try:
            agreement = owner.platform_agreement
            agreements_signed += 1
        except Exception:
            import logging
            logger = logging.getLogger('clients')
            logger.debug(f'Platform agreement lookup failed for user {owner.id}', exc_info=True)

        if owner_profile.subscription_active:
            active_subscriptions += 1

        sub_id = owner_profile.stripe_subscription_id or ''
        if 'enterprise' in sub_id.lower():
            bundle = 'enterprise'
        elif 'starter' in sub_id.lower():
            bundle = 'starter'
        else:
            bundle = 'growth'

        rows.append({
            'firm': firm, 'owner': owner,
            'subscription_active': owner_profile.subscription_active,
            'billing_cycle': owner_profile.billing_cycle or 'monthly',
            'bundle': bundle, 'agreement': agreement,
            'client_count': client_count,
        })

    unsigned_count = len([r for r in rows if not r['agreement']])

    return render(request, 'clients/mortacc_admin.html', {
        'rows': rows, 'total_firms': len(rows),
        'active_subscriptions': active_subscriptions,
        'agreements_signed': agreements_signed,
        'total_clients': total_clients,
        'unsigned_count': unsigned_count,
    })
