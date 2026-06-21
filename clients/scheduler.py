from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# JOB LOGGING WRAPPERS
# ═══════════════════════════════════════════════════════════════════════

def _log_job_start(job_id, job_name):
    """Create a SchedulerJobLog entry and return it for later updating."""
    from .models import SchedulerJobLog
    log = SchedulerJobLog.objects.create(
        job_id=job_id,
        job_name=job_name,
        status='running',
        started_at=timezone.now(),
    )
    return log


def _log_job_end(log, records=0, error=None):
    """Update the SchedulerJobLog with completion data."""
    log.completed_at = timezone.now()
    log.duration_ms = int((log.completed_at - log.started_at).total_seconds() * 1000)
    log.records_affected = records
    if error:
        log.status = 'failed'
        log.error_message = str(error)[:500]
    else:
        log.status = 'completed'
    log.save()
    return log


# ═══════════════════════════════════════════════════════════════════════
# EXISTING JOBS (with logging added)
# ═══════════════════════════════════════════════════════════════════════

def send_automated_reminders():
    """
    Runs daily at 9am — checks all clients with missing documents
    and sends reminder emails based on how many days have passed.
    """
    log = _log_job_start('automated_reminders', 'Send automated client reminders')
    count = 0
    try:
        from .models import Client
        from django.core.mail import send_mail

        now = timezone.now()
        pending_clients = Client.objects.filter(
            onboarding_submitted_at__isnull=True
        ).select_related('firm')

        for client in pending_clients:
            if not client.onboarding_token:
                continue
            if not client.created_at:
                continue

            days_since_created = (now - client.created_at).days
            missing = _get_missing_items(client)
            if not missing:
                continue

            site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
            portal_link = f"{site_url}/onboarding/{client.onboarding_token}/"
            missing_list = '\n'.join([f'- {item}' for item in missing])
            firm_name = client.firm.name if client.firm else 'Your accountant'

            if days_since_created == 2:
                _send_reminder(
                    client=client,
                    subject=f"Quick reminder — your file with {firm_name} is almost ready",
                    message=f"""Hi {client.name},

Just a quick reminder that your accountant is waiting for a few documents to complete your file.

Still needed:
{missing_list}

It only takes a few minutes to upload them:
{portal_link}

If you have any questions, reply to this email.

{firm_name} · Powered by Mortacc"""
                )
                count += 1

            elif days_since_created == 5:
                _send_reminder(
                    client=client,
                    subject=f"Your file is still incomplete — {firm_name}",
                    message=f"""Hi {client.name},

We noticed your file is still missing a few items. Your accountant can't proceed until these are received:

{missing_list}

Please take a moment to complete your submission:
{portal_link}

If you're having trouble, reply to this email and we'll help.

{firm_name} · Powered by Mortacc"""
                )
                count += 1

            elif days_since_created == 7:
                _notify_accountant(client, missing)
                count += 1
    except Exception as e:
        logger.error('automated_reminders failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Sent %d automated reminder(s).', count)


def _send_reminder(client, subject, message):
    from django.core.mail import send_mail
    try:
        send_mail(
            subject=subject, message=message,
            from_email='support@mortacc.com',
            recipient_list=[client.email], fail_silently=False,
        )
    except Exception as e:
        logger.error('Failed to send reminder to %s: %s', client.email, e)


def _notify_accountant(client, missing):
    from django.contrib.auth.models import User
    from django.core.mail import send_mail

    site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
    missing_list = '\n'.join([f'- {item}' for item in missing])

    accountants = User.objects.filter(
        userprofile__firm=client.firm,
        userprofile__role='accountant'
    )
    for accountant in accountants:
        try:
            send_mail(
                subject=f"Follow up needed — {client.name} hasn't responded in 7 days",
                message=f"""Hi {accountant.first_name},

{client.name} ({client.email}) has not completed their onboarding package after 7 days.

Still missing:
{missing_list}

You may want to follow up with them directly.

View their file: {site_url}/clients/{client.id}/

Mortacc""",
                from_email='support@mortacc.com',
                recipient_list=[accountant.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error('Failed to notify accountant %s: %s', accountant.email, e)


# Shared utility — avoids duplication with views.py
from .utils.missing_items import get_missing_items as _get_missing_items


def mark_overdue_compliance_tasks():
    """
    Runs daily at midnight — marks any ComplianceTask past its due_date
    as overdue (unless already completed or waived). Fires webhooks.
    """
    log = _log_job_start('mark_overdue_tasks', 'Auto-mark overdue compliance tasks')
    count = 0
    try:
        from .models import ComplianceTask, trigger_webhook
        today = timezone.now().date()
        overdue_tasks = ComplianceTask.objects.filter(
            due_date__lt=today,
            status__in=['pending', 'in_progress'],
        )
        for task in overdue_tasks.select_related('client__firm'):
            task.status = 'overdue'
            task.save()
            trigger_webhook('task.overdue', task.client.firm, {
                'id': task.id, 'task_name': task.task_name,
                'client_id': task.client_id, 'client_name': task.client.name,
                'due_date': str(task.due_date), 'status': 'overdue',
            })
            count += 1
    except Exception as e:
        logger.error('mark_overdue_compliance_tasks failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Marked %d compliance task(s) as overdue.', count)


def send_weekly_compliance_digest():
    """
    Runs every Monday at 8am — sends each firm a digest of upcoming
    and overdue compliance tasks for the week ahead.
    """
    log = _log_job_start('weekly_compliance_digest', 'Send weekly compliance digest')
    count = 0
    try:
        from .models import ComplianceTask, Firm
        from django.core.mail import send_mail
        from django.contrib.auth.models import User

        today = timezone.now().date()
        week_end = today + timezone.timedelta(days=7)

        firms = Firm.objects.all()
        for firm in firms:
            tasks = ComplianceTask.objects.filter(
                client__firm=firm,
                status__in=['pending', 'overdue'],
                due_date__lte=week_end,
            ).select_related('client').order_by('due_date')

            if not tasks.exists():
                continue

            overdue = [t for t in tasks if t.status == 'overdue' or t.due_date < today]
            upcoming = [t for t in tasks if t.status == 'pending' and t.due_date >= today]

            lines = [f"COMPLIANCE DIGEST — Week of {today.strftime('%B %d, %Y')}", "=" * 50, ""]
            if overdue:
                lines.append(f"⚠ OVERDUE ({len(overdue)} tasks):")
                for t in overdue:
                    days = (today - t.due_date).days
                    lines.append(f"  • {t.client.name} — {t.title} (due {t.due_date}, {days} days ago)")
                lines.append("")
            if upcoming:
                lines.append(f"📋 DUE THIS WEEK ({len(upcoming)} tasks):")
                for t in upcoming:
                    days = (t.due_date - today).days
                    lines.append(f"  • {t.client.name} — {t.title} (due {t.due_date}, in {days} days)")
                lines.append("")
            lines.append(f"View all tasks: {getattr(settings, 'SITE_URL', 'https://mortacc.com')}/compliance/")

            recipients = User.objects.filter(
                userprofile__firm=firm,
                userprofile__role__in=['accountant', 'admin'],
            ).values_list('email', flat=True)

            if recipients:
                try:
                    send_mail(
                        subject=f"Compliance Digest — Week of {today.strftime('%b %d')}",
                        message="\n".join(lines),
                        from_email='support@mortacc.com',
                        recipient_list=list(recipients),
                        fail_silently=False,
                    )
                    count += 1
                except Exception as e:
                    logger.error('Failed to send weekly digest to %s: %s', firm.name, e)
    except Exception as e:
        logger.error('send_weekly_compliance_digest failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Weekly digest sent to %d firm(s).', count)


def process_subscription_renewals():
    """
    Runs daily at 2am — identifies subscriptions due for renewal,
    generates invoices, and updates billing periods.
    """
    log = _log_job_start('subscription_renewals', 'Process subscription renewals')
    count = 0
    try:
        from .models import EntitySubscription, SubscriptionInvoice, Invoice

        today = timezone.now().date()
        due_subs = EntitySubscription.objects.filter(
            status='active',
            auto_renew=True,
            next_billing_date__lte=today,
        ).select_related('client', 'plan', 'firm')

        for sub in due_subs:
            price = sub.custom_price_override or getattr(sub.plan, f'price_{sub.billing_cycle}', sub.plan.price_monthly)
            amount = price / 100.0 if price else 0

            inv = Invoice.objects.create(
                client=sub.client,
                description=f'Entity Subscription Renewal: {sub.plan.name} ({sub.get_billing_cycle_display()})',
                service_type='subscription',
                amount=amount,
                status='sent',
                invoice_date=today,
                due_date=today + timezone.timedelta(days=30),
                auto_generated=True,
            )

            billing_cycle_days = {'monthly': 30, 'quarterly': 90, 'annual': 365}
            next_end = today + timezone.timedelta(days=billing_cycle_days.get(sub.billing_cycle, 365))
            period_start = sub.current_period_end or today

            SubscriptionInvoice.objects.create(
                subscription=sub,
                invoice=inv,
                billing_period_start=period_start,
                billing_period_end=next_end,
                amount_charged=amount,
            )

            sub.current_period_start = period_start
            sub.current_period_end = next_end
            sub.next_billing_date = next_end
            sub.save()
            count += 1
    except Exception as e:
        logger.error('process_subscription_renewals failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Processed %d subscription renewal(s).', count)


def process_collections_reminders():
    """
    Runs daily at 8:30am — sends payment reminders for overdue invoices
    according to each firm's collections rules.
    """
    log = _log_job_start('collections_reminders', 'Send payment reminders for overdue invoices')
    count = 0
    try:
        from .models import Invoice, CollectionsRule
        from django.core.mail import send_mail

        today = timezone.now().date()

        overdue_invoices = Invoice.objects.filter(
            status__in=['sent', 'overdue'],
            due_date__lt=today,
        ).exclude(
            last_reminder_sent__date=today,
        ).select_related('client__firm')

        for inv in overdue_invoices:
            if not inv.should_send_reminder():
                continue

            if inv.status == 'sent':
                inv.status = 'overdue'
                inv.save()

            firm = inv.client.firm
            if not firm:
                continue
            rules = CollectionsRule.objects.filter(firm=firm).first()
            if not rules or not rules.send_client_emails:
                continue

            try:
                subject = rules.reminder_email_subject.replace('{{ firm_name }}', firm.name)
                body = rules.reminder_email_body
                body = body.replace('{{ client_name }}', inv.client.name)
                body = body.replace('{{ invoice_number }}', inv.invoice_number)
                body = body.replace('{{ amount }}', f'${float(inv.total_amount):.2f}')
                body = body.replace('{{ due_date }}', str(inv.due_date))
                body = body.replace('{{ payment_link }}', inv.stripe_payment_link or '#')

                send_mail(
                    subject=subject, message=body,
                    from_email='support@mortacc.com',
                    recipient_list=[inv.client.email],
                    fail_silently=True,
                )
                inv.reminder_count += 1
                inv.last_reminder_sent = timezone.now()
                inv.save()
                count += 1
            except Exception as e:
                logger.error('Failed to send reminder for invoice %s: %s', inv.invoice_number, e)
    except Exception as e:
        logger.error('process_collections_reminders failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Sent %d payment reminder(s).', count)


# ═══════════════════════════════════════════════════════════════════════
# NEW AUTOMATION JOBS
# ═══════════════════════════════════════════════════════════════════════

def t2_deadline_reminders():
    """
    Runs daily at 9:15am. Finds entities with fiscal year end dates
    and checks if the 6-month T2 filing deadline is within
    60, 30, 14, or 7 days. Sends branded email reminders.
    Creates compliance tasks for T2 if not already present.
    """
    log = _log_job_start('t2_deadline_reminders', 'T2 filing deadline reminders')
    count = 0
    try:
        from .models import CorporateProfile, ComplianceTask, Client
        from .automation_emails import send_t2_deadline_approaching
        from dateutil.relativedelta import relativedelta

        today = timezone.now().date()
        reminder_days = [60, 30, 14, 7]

        profiles = CorporateProfile.objects.filter(
            fiscal_year_end__isnull=False
        ).select_related('client__firm')

        for cp in profiles:
            if not cp.fiscal_year_end:
                continue

            # Calculate 6-month T2 deadline from fiscal year end
            try:
                fye_this_year = cp.fiscal_year_end.replace(year=today.year)
            except ValueError:
                continue

            # T2 is due 6 months after fiscal year end
            t2_deadline = fye_this_year + relativedelta(months=6)

            days_remaining = (t2_deadline - today).days

            for window in reminder_days:
                if days_remaining == window:
                    client = cp.client
                    # Create compliance task if not exists
                    task_exists = ComplianceTask.objects.filter(
                        client=client,
                        task_type='t2_filing',
                        due_date=t2_deadline,
                    ).exists()
                    if not task_exists:
                        ComplianceTask.objects.create(
                            client=client,
                            task_type='t2_filing',
                            title=f'T2 Corporate Tax Return — {today.year}',
                            description=f'T2 filing due {t2_deadline}. {days_remaining} days remaining.',
                            due_date=t2_deadline,
                            status='pending',
                        )

                    send_t2_deadline_approaching(client, days_remaining)
                    count += 1
                    logger.info(
                        'T2 reminder: %s — %d days until %s',
                        client.name, days_remaining, t2_deadline,
                    )
    except Exception as e:
        logger.error('t2_deadline_reminders failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Sent %d T2 deadline reminder(s).', count)


def generate_bookkeeping_tasks():
    """
    Runs on the 1st of each month at 6am. For each active entity,
    creates a BookkeepingTask for the current month if one doesn't exist.
    """
    log = _log_job_start('generate_bookkeeping_tasks', 'Generate monthly bookkeeping tasks')
    count = 0
    try:
        from .models import Client, BookkeepingTask
        from datetime import date

        today = timezone.now().date()
        month_name = today.strftime('%B')
        year = today.year

        active_clients = Client.objects.filter(status__in=['active', 'in_progress'])

        for client in active_clients:
            exists = BookkeepingTask.objects.filter(
                client=client,
                month=month_name,
                year=year,
            ).exists()
            if not exists:
                BookkeepingTask.objects.create(
                    client=client,
                    month=month_name,
                    year=year,
                    status='not_started',
                    notes=f'Auto-generated monthly bookkeeping task for {month_name} {year}.',
                )
                count += 1
    except Exception as e:
        logger.error('generate_bookkeeping_tasks failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Created %d monthly bookkeeping task(s).', count)


def gst_hst_reminder():
    """
    Runs on the 1st of each month at 8am. Reminds firms with pending
    GST/HST bookkeeping tasks to file.
    """
    log = _log_job_start('gst_hst_reminder', 'Monthly GST/HST filing reminders')
    count = 0
    try:
        from .models import BookkeepingTask, Client
        from .automation_emails import send_gst_hst_reminder

        today = timezone.now().date()
        last_month = (today.replace(day=1) - timezone.timedelta(days=1)).strftime('%B')
        last_month_year = (today.replace(day=1) - timezone.timedelta(days=1)).year

        pending_tasks = BookkeepingTask.objects.filter(
            status__in=['not_started', 'in_progress'],
        ).select_related('client__firm')

        reminded_clients = set()
        for task in pending_tasks:
            if task.client_id in reminded_clients:
                continue
            send_gst_hst_reminder(task.client, f'{last_month} {last_month_year}')
            reminded_clients.add(task.client_id)
            count += 1
    except Exception as e:
        logger.error('gst_hst_reminder failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Sent %d GST/HST reminder(s).', count)


def tax_installment_reminder():
    """
    Runs on the 15th of each month at 8am. Reminds firms about
    quarterly/monthly tax installment obligations.
    """
    log = _log_job_start('tax_installment_reminder', 'Monthly tax installment reminders')
    count = 0
    try:
        from .models import T2Return, Client
        from .automation_emails import send_tax_installment_reminder

        today = timezone.now().date()

        # Find entities with net tax owing > $3,000 (installment threshold)
        t2_returns = T2Return.objects.filter(
            net_tax_owing__gt=3000,
            status__in=['not_started', 'preparing', 'prepared'],
        ).select_related('client__firm')

        reminded_clients = set()
        for t2 in t2_returns:
            if t2.client_id in reminded_clients:
                continue
            send_tax_installment_reminder(t2.client, float(t2.net_tax_owing))
            reminded_clients.add(t2.client_id)
            count += 1
    except Exception as e:
        logger.error('tax_installment_reminder failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Sent %d tax installment reminder(s).', count)


def bookkeeping_reconciliation():
    """
    Weekly on Mondays at 7am. Reminds firms about bookkeeping tasks
    that are still pending for prior months.
    """
    log = _log_job_start('bookkeeping_reconciliation', 'Weekly bookkeeping reconciliation reminders')
    count = 0
    try:
        from .models import BookkeepingTask, Client
        from .automation_emails import send_bookkeeping_overdue

        today = timezone.now().date()

        # Find bookkeeping tasks for prior months that are still pending
        stale_tasks = BookkeepingTask.objects.filter(
            status__in=['not_started', 'in_progress'],
        ).select_related('client__firm')

        for task in stale_tasks:
            # Only remind if it's for a month that has already ended
            try:
                task_month_num = timezone.datetime.strptime(task.month, '%B').month
                task_date = timezone.datetime(task.year, task_month_num, 1).date()
                if task_date < today.replace(day=1):  # prior month
                    send_bookkeeping_overdue(task)
                    count += 1
            except (ValueError, TypeError):
                continue
    except Exception as e:
        logger.error('bookkeeping_reconciliation failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Sent %d bookkeeping reconciliation reminder(s).', count)


def incorporation_anniversary_reminder():
    """
    Runs daily at 8:45am. Checks for incorporation dates that have an
    anniversary within the next 60 days and the annual return hasn't
    been filed yet. Creates compliance tasks.
    """
    log = _log_job_start('incorporation_anniversary', 'Incorporation anniversary reminders')
    count = 0
    try:
        from .models import CorporateProfile, ComplianceTask, AnnualFiling, Client
        from .automation_emails import send_incorporation_anniversary
        from dateutil.relativedelta import relativedelta

        today = timezone.now().date()
        reminder_days = [60, 30, 14, 7]

        profiles = CorporateProfile.objects.filter(
            incorporation_date__isnull=False
        ).select_related('client__firm')

        for cp in profiles:
            if not cp.incorporation_date:
                continue
            client = cp.client

            # Calculate upcoming anniversary
            inc_month = cp.incorporation_date.month
            inc_day = cp.incorporation_date.day
            try:
                anniversary_this_year = cp.incorporation_date.replace(year=today.year)
            except ValueError:
                continue

            # If anniversary already passed this year, look at next year
            if anniversary_this_year < today:
                try:
                    anniversary_this_year = cp.incorporation_date.replace(year=today.year + 1)
                except ValueError:
                    continue

            days_remaining = (anniversary_this_year - today).days
            ann_year = today.year if anniversary_this_year.year == today.year else today.year + 1

            for window in reminder_days:
                if days_remaining == window:
                    # Check if annual return already filed for this year
                    already_filed = AnnualFiling.objects.filter(
                        client=client,
                        year=ann_year,
                        status='filed',
                    ).exists()

                    if not already_filed:
                        # Create compliance task if not exists
                        task_exists = ComplianceTask.objects.filter(
                            client=client,
                            task_type='annual_return',
                            due_date=anniversary_this_year,
                        ).exists()
                        if not task_exists:
                            ComplianceTask.objects.create(
                                client=client,
                                task_type='annual_return',
                                title=f'Annual Return Filing — {ann_year}',
                                description=f'Annual return due {anniversary_this_year}. Incorporation anniversary.',
                                due_date=anniversary_this_year,
                                status='pending',
                            )

                        send_incorporation_anniversary(client, cp, days_remaining)
                        count += 1
                        logger.info(
                            'Anniversary reminder: %s — %d days until %s',
                            client.name, days_remaining, anniversary_this_year,
                        )
    except Exception as e:
        logger.error('incorporation_anniversary_reminder failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Sent %d incorporation anniversary reminder(s).', count)


def auto_create_t2_returns():
    """
    Runs daily at 3am. Checks if any entity's fiscal year end was
    yesterday and auto-creates a T2Return for the tax year if one
    doesn't exist. Pre-fills from entity data.
    """
    log = _log_job_start('auto_create_t2_returns', 'Auto-create T2 returns after FYE')
    count = 0
    try:
        from .models import CorporateProfile, T2Return, Client

        today = timezone.now().date()
        yesterday = today - timezone.timedelta(days=1)

        profiles = CorporateProfile.objects.filter(
            fiscal_year_end__isnull=False
        ).select_related('client')

        for cp in profiles:
            # Check if FYE was yesterday (month + day match)
            if cp.fiscal_year_end.month == yesterday.month and cp.fiscal_year_end.day == yesterday.day:
                client = cp.client

                # Check if T2 already exists for this tax year
                tax_year = today.year
                exists = T2Return.objects.filter(
                    firm=client.firm,
                    client=client,
                    tax_year=tax_year,
                ).exists()

                if not exists:
                    t2 = T2Return.objects.create(
                        firm=client.firm,
                        client=client,
                        tax_year=tax_year,
                        fiscal_year_start=cp.fiscal_year_end.replace(year=today.year - 1) + timezone.timedelta(days=1),
                        fiscal_year_end=cp.fiscal_year_end.replace(year=today.year),
                        status='not_started',
                        notes=f'Auto-generated after fiscal year end {cp.fiscal_year_end}.',
                    )
                    # Deep pre-fill from all available data sources
                    try:
                        t2.deep_prefill()
                    except Exception:
                        pass
                    count += 1
                    logger.info('Auto-created T2Return for %s (tax year %d)', client.name, tax_year)
    except Exception as e:
        logger.error('auto_create_t2_returns failed: %s', e)
        _log_job_end(log, records=count, error=e)
        return
    _log_job_end(log, records=count)
    if count:
        logger.info('Auto-created %d T2 return(s).', count)


# ═══════════════════════════════════════════════════════════════════════
# ANNUAL RETURN & QUEBEC DECLARATION REMINDERS
# ═══════════════════════════════════════════════════════════════════════

def annual_return_reminders():
    """Send reminders for upcoming annual return deadlines at 30/14/7/1 days."""
    from datetime import date, timedelta
    from .models import CorporateProfile, ComplianceTask, Firm

    log = _log_job_start('annual_return_reminders', 'Annual return deadline reminders')
    today = date.today()
    count = 0

    for days in [30, 14, 7, 1]:
        target_date = today + timedelta(days=days)
        # Find corporations whose incorporation anniversary matches
        profiles = CorporateProfile.objects.filter(
            incorporation_date__isnull=False,
            incorporation_date__month=target_date.month,
            incorporation_date__day=target_date.day,
            status='active',
        ).select_related('client__firm')

        for profile in profiles:
            client = profile.client
            # Check if reminder already created for this year
            existing = ComplianceTask.objects.filter(
                client=client, task_type='annual_return',
                title__icontains=f'{days}-day',
                due_date=target_date,
            ).exists()
            if not existing:
                ComplianceTask.objects.create(
                    client=client, task_type='annual_return',
                    title=f'Annual Return Filing ({days}-day reminder)',
                    description=f'Annual return due for {client.name}. Incorporation date: {profile.incorporation_date}.',
                    due_date=target_date, status='pending',
                )
                count += 1

    _log_job_end(log, records=count)
    if count:
        logger.info('Created %d annual return reminder task(s).', count)


def quebec_declaration_reminders():
    """Send reminders for Quebec annual declarations at 30/14/7/1 days."""
    from datetime import date, timedelta
    from .models import CorporateProfile, ComplianceTask

    log = _log_job_start('quebec_declaration_reminders', 'Quebec declaration reminders')
    today = date.today()
    count = 0

    for days in [30, 14, 7, 1]:
        target_date = today + timedelta(days=days)
        profiles = CorporateProfile.objects.filter(
            jurisdiction='quebec',
            status='active',
        ).select_related('client')

        for profile in profiles:
            # Quebec declarations typically due annually based on incorporation
            if profile.incorporation_date and (
                profile.incorporation_date.month == target_date.month and
                profile.incorporation_date.day == target_date.day
            ):
                existing = ComplianceTask.objects.filter(
                    client=profile.client, task_type='quebec_declaration',
                    title__icontains=f'{days}-day',
                    due_date=target_date,
                ).exists()
                if not existing:
                    ComplianceTask.objects.create(
                        client=profile.client, task_type='quebec_declaration',
                        title=f'Quebec Annual Declaration ({days}-day reminder)',
                        description=f'Quebec annual updating declaration due for {profile.client.name}.',
                        due_date=target_date, status='pending',
                    )
                    count += 1

    _log_job_end(log, records=count)
    if count:
        logger.info('Created %d Quebec declaration reminder task(s).', count)


# ═══════════════════════════════════════════════════════════════════════
# SCHEDULER STARTUP
# ═══════════════════════════════════════════════════════════════════════

def start():
    """Start the scheduler — called from apps.py"""
    scheduler = BackgroundScheduler()

    # ── Existing jobs ──────────────────────────────────────────────
    scheduler.add_job(
        send_automated_reminders,
        trigger=CronTrigger(hour=9, minute=0),
        id='automated_reminders',
        name='Send automated client reminders',
        replace_existing=True,
    )
    scheduler.add_job(
        mark_overdue_compliance_tasks,
        trigger=CronTrigger(hour=0, minute=5),
        id='mark_overdue_tasks',
        name='Auto-mark overdue compliance tasks',
        replace_existing=True,
    )
    scheduler.add_job(
        send_weekly_compliance_digest,
        trigger=CronTrigger(day_of_week='mon', hour=8, minute=0),
        id='weekly_compliance_digest',
        name='Send weekly compliance digest to firms',
        replace_existing=True,
    )
    scheduler.add_job(
        process_subscription_renewals,
        trigger=CronTrigger(hour=2, minute=0),
        id='subscription_renewals',
        name='Process subscription renewals and billing',
        replace_existing=True,
    )
    scheduler.add_job(
        process_collections_reminders,
        trigger=CronTrigger(hour=8, minute=30),
        id='collections_reminders',
        name='Send payment reminders for overdue invoices',
        replace_existing=True,
    )

    # ── New automation jobs ────────────────────────────────────────
    scheduler.add_job(
        t2_deadline_reminders,
        trigger=CronTrigger(hour=9, minute=15),
        id='t2_deadline_reminders',
        name='T2 filing deadline reminders (60/30/14/7 days)',
        replace_existing=True,
    )
    scheduler.add_job(
        generate_bookkeeping_tasks,
        trigger=CronTrigger(day=1, hour=6, minute=0),
        id='generate_bookkeeping_tasks',
        name='Generate monthly bookkeeping tasks',
        replace_existing=True,
    )
    scheduler.add_job(
        gst_hst_reminder,
        trigger=CronTrigger(day=1, hour=8, minute=0),
        id='gst_hst_reminder',
        name='Monthly GST/HST filing reminders',
        replace_existing=True,
    )
    scheduler.add_job(
        tax_installment_reminder,
        trigger=CronTrigger(day=15, hour=8, minute=0),
        id='tax_installment_reminder',
        name='Monthly tax installment reminders',
        replace_existing=True,
    )
    scheduler.add_job(
        bookkeeping_reconciliation,
        trigger=CronTrigger(day_of_week='mon', hour=7, minute=0),
        id='bookkeeping_reconciliation',
        name='Weekly bookkeeping reconciliation reminders',
        replace_existing=True,
    )
    scheduler.add_job(
        incorporation_anniversary_reminder,
        trigger=CronTrigger(hour=8, minute=45),
        id='incorporation_anniversary',
        name='Incorporation anniversary and annual return reminders',
        replace_existing=True,
    )
    scheduler.add_job(
        auto_create_t2_returns,
        trigger=CronTrigger(hour=3, minute=0),
        id='auto_create_t2_returns',
        name='Auto-create T2 returns after fiscal year end',
        replace_existing=True,
    )

    # ── New: Annual return & Quebec declaration reminders ───────────
    scheduler.add_job(
        annual_return_reminders,
        trigger=CronTrigger(hour=8, minute=30),
        id='annual_return_reminders',
        name='Annual return deadline reminders (30/14/7/1 days)',
        replace_existing=True,
    )
    scheduler.add_job(
        quebec_declaration_reminders,
        trigger=CronTrigger(hour=8, minute=35),
        id='quebec_declaration_reminders',
        name='Quebec annual declaration reminders (30/14/7/1 days)',
        replace_existing=True,
    )

    # ── Register chasing reminders ──────────────────────────────────
    try:
        from .models.chasing import send_chasing_reminders
        scheduler.add_job(
            send_chasing_reminders,
            trigger=CronTrigger(hour=9, minute=30),
            id='chasing_reminders',
            name='Send auto-chasing reminders for outstanding items',
            replace_existing=True,
        )
    except ImportError:
        pass

    scheduler.start()
    logger.info(
        "Scheduler started with 15 jobs: "
        "automated reminders (9am), overdue marking (12:05am), "
        "weekly digest (Mon 8am), subscription renewals (2am), "
        "collections reminders (8:30am), T2 deadlines (9:15am), "
        "monthly bookkeeping (1st 6am), GST/HST (1st 8am), "
        "tax installments (15th 8am), bookkeeping rec (Mon 7am), "
        "anniversary reminders (8:45am), auto-create T2 (3am), "
        "annual return reminders (8:30am), Quebec declarations (8:35am), "
        "chasing reminders (9:30am)"
    )
