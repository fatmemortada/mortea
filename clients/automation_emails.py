"""
Event-driven email automation.
Reuses the branded HTML email helpers from emails.py.
Each function sends a specific notification email when triggered by
a scheduler job, workflow step, or view action.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def _send(subject, message, recipient_list, from_email=None):
    """Thin wrapper around Django's send_mail — fail_silently in production."""
    from django.core.mail import send_mail
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email or 'support@mortacc.com',
            recipient_list=recipient_list if isinstance(recipient_list, list) else [recipient_list],
            fail_silently=True,
        )
        return True
    except Exception as e:
        logger.error('Failed to send email "%s": %s', subject, e)
        return False


def send_t2_deadline_approaching(client, days_remaining, firm_name=''):
    """T2 filing deadline is approaching — notify the firm's accountants."""
    from django.contrib.auth.models import User

    site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
    firm_label = firm_name or (client.firm.name if client.firm else 'Your firm')

    subject = f'⚠ T2 Filing Deadline: {client.name} — {days_remaining} days remaining'

    message = f"""T2 CORPORATE TAX RETURN — DEADLINE APPROACHING

Client: {client.name}
Days until T2 deadline: {days_remaining}

The 6-month T2 filing window for {client.name} is closing soon.
Prepare and file the T2 Corporate Tax Return to avoid CRA penalties.

View and prepare: {site_url}/t2/prepare/{client.id}/

{firm_label} · Powered by Mortacc"""

    recipients = User.objects.filter(
        userprofile__firm=client.firm,
        is_active=True,
    ).values_list('email', flat=True)

    return _send(subject, message, list(recipients))


def send_bookkeeping_overdue(bookkeeping_task):
    """Monthly bookkeeping is overdue — remind the firm."""
    from django.contrib.auth.models import User

    site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
    client = bookkeeping_task.client
    firm = client.firm

    subject = f'📊 Bookkeeping Overdue: {client.name} — {bookkeeping_task.month} {bookkeeping_task.year}'

    message = f"""BOOKKEEPING TASK OVERDUE

Client: {client.name}
Period: {bookkeeping_task.month} {bookkeeping_task.year}
Status: {bookkeeping_task.get_status_display()}

Monthly bookkeeping for {client.name} has not been completed.
Reconciliation, GST/HST reporting, and financial statements are pending.

View tasks: {site_url}/time-tracking/

{firm.name if firm else 'Your firm'} · Powered by Mortacc"""

    recipients = User.objects.filter(
        userprofile__firm=firm,
        is_active=True,
    ).values_list('email', flat=True)

    return _send(subject, message, list(recipients))


def send_incorporation_anniversary(client, profile, days_remaining):
    """Annual return is due soon for an incorporated entity."""
    from django.contrib.auth.models import User

    site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
    firm = client.firm

    subject = f'🎂 Incorporation Anniversary: {client.name} — Annual Return due in {days_remaining} days'

    message = f"""INCORPORATION ANNIVERSARY — ANNUAL RETURN DUE

Client: {client.name}
Incorporated: {profile.incorporation_date}
Jurisdiction: {profile.get_jurisdiction_display()}
Days until annual return due: {days_remaining}

An annual return must be filed with {profile.get_jurisdiction_display() if hasattr(profile, 'get_jurisdiction_display') else 'the applicable registry'} within 60 days of the incorporation anniversary.

View entity: {site_url}/clients/{client.id}/

{firm.name if firm else 'Your firm'} · Powered by Mortacc"""

    recipients = User.objects.filter(
        userprofile__firm=firm,
        is_active=True,
    ).values_list('email', flat=True)

    return _send(subject, message, list(recipients))


def send_invoice_escalation(invoice, level):
    """Escalating collections email based on overdue severity."""
    from django.contrib.auth.models import User

    site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
    client = invoice.client
    firm = client.firm

    level_info = {
        1: {'label': 'First Notice', 'urgency': 'is now overdue'},
        2: {'label': 'Second Notice', 'urgency': 'is 30+ days past due'},
        3: {'label': 'Final Notice', 'urgency': 'is 60+ days past due — action required'},
    }
    info = level_info.get(level, level_info[1])

    subject = f'💰 {info["label"]}: Invoice {invoice.invoice_number} — {client.name}'

    message = f"""PAYMENT REMINDER — {info['label'].upper()}

Client: {client.name}
Invoice: {invoice.invoice_number}
Amount: ${float(invoice.total_amount):.2f}
Due Date: {invoice.due_date}
Status: {info['urgency']}

Reminder #{invoice.reminder_count}

View invoice: {site_url}/billing/

{firm.name if firm else 'Your firm'} · Powered by Mortacc"""

    recipients = User.objects.filter(
        userprofile__firm=firm,
        is_active=True,
    ).values_list('email', flat=True)

    return _send(subject, message, list(recipients))


def send_gst_hst_reminder(client, period_label):
    """GST/HST filing period reminder."""
    from django.contrib.auth.models import User

    site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
    firm = client.firm

    subject = f'📋 GST/HST Filing Reminder: {client.name} — {period_label}'

    message = f"""GST/HST FILING REMINDER

Client: {client.name}
Period: {period_label}

It's time to prepare and file the GST/HST return for {client.name}.
Review ITCs, sales summary, and Quick Method eligibility.

View: {site_url}/automation/tax/{client.id}/

{firm.name if firm else 'Your firm'} · Powered by Mortacc"""

    recipients = User.objects.filter(
        userprofile__firm=firm,
        is_active=True,
    ).values_list('email', flat=True)

    return _send(subject, message, list(recipients))


def send_tax_installment_reminder(client, estimated_tax):
    """Monthly/quarterly tax installment reminder."""
    from django.contrib.auth.models import User

    site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')
    firm = client.firm

    subject = f'🏛 Tax Installment Reminder: {client.name}'

    message = f"""TAX INSTALLMENT REMINDER

Client: {client.name}
Estimated Annual Tax: ${estimated_tax:,.2f}

If the net tax owing exceeds $3,000, monthly or quarterly installments may be required by the CRA. The next installment is due on the 15th.

View T2: {site_url}/t2/prepare/{client.id}/

{firm.name if firm else 'Your firm'} · Powered by Mortacc"""

    recipients = User.objects.filter(
        userprofile__firm=firm,
        is_active=True,
    ).values_list('email', flat=True)

    return _send(subject, message, list(recipients))
