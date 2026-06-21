import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _site_url():
    return getattr(settings, 'SITE_URL', 'https://mortacc.com')

def _firm_name(client):
    try:
        return client.firm.name if client.firm else 'Your Firm'
    except Exception:
        return 'Your Firm'

def _send(subject, text_body, recipient_list, html_body=None):
    """Send email with optional HTML version."""
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mortacc.com'),
            to=recipient_list,
        )
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        logger.error("Email send failed to %s: %s", recipient_list, e)
        return False

def _base_html(title, preview, body_html):
    """Branded HTML email wrapper."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;color:#f1f5f9;">{preview}</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 16px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

      <!-- Header -->
      <tr>
        <td style="background:#0a0f1e;border-radius:12px 12px 0 0;padding:24px 36px;text-align:left;">
          <span style="font-size:22px;font-weight:800;color:#fff;letter-spacing:-0.5px;">Mort<span style="color:#3b82f6;">acc</span></span>
        </td>
      </tr>

      <!-- Body -->
      <tr>
        <td style="background:#ffffff;padding:36px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;">
          {body_html}
        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="background:#f8fafc;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;padding:20px 36px;text-align:center;">
          <p style="margin:0 0 6px;font-size:12px;color:#94a3b8;">Mortacc Solutions Inc. · support@mortacc.com</p>
          <p style="margin:0;font-size:11px;color:#cbd5e1;">This email was sent from a notification-only address. Please do not reply directly.</p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""

def _btn(url, label, color='#3b82f6'):
    return f'<a href="{url}" style="display:inline-block;background:{color};color:#fff;padding:13px 28px;border-radius:8px;font-size:14px;font-weight:700;text-decoration:none;margin:20px 0;">{label}</a>'

def _divider():
    return '<hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;">'

def _h1(text):
    return f'<h1 style="margin:0 0 12px;font-size:24px;font-weight:800;color:#0f172a;line-height:1.2;">{text}</h1>'

def _p(text, muted=False):
    color = '#64748b' if muted else '#334155'
    return f'<p style="margin:0 0 14px;font-size:15px;color:{color};line-height:1.7;">{text}</p>'

def _info_box(rows):
    items = ''.join(
        f'<tr><td style="padding:8px 14px;font-size:13px;color:#64748b;font-weight:500;white-space:nowrap;">{k}</td>'
        f'<td style="padding:8px 14px;font-size:13px;color:#0f172a;font-weight:600;">{v}</td></tr>'
        for k, v in rows
    )
    return f'<table style="width:100%;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;border-collapse:collapse;margin:16px 0;">{items}</table>'


# ─────────────────────────────────────────────
# 1. CLIENT INVITATION
# ─────────────────────────────────────────────

def send_client_invitation(client):
    site_url = _site_url()
    portal_url = f"{site_url}/onboarding/{client.onboarding_token}/"
    firm = _firm_name(client)
    subject = f"Your document portal is ready — {firm}"

    text = f"""Hi {client.name},

{firm} has set up a secure portal for you to submit your documents.

Use this link to access your portal:
{portal_url}

This link is unique to you — no password needed.

{firm}
Powered by Mortacc
"""
    html_body = (
        _h1(f"Your portal is ready, {client.name.split()[0]}.")
        + _p(f"<strong>{firm}</strong> has created a secure document portal for you. Click the button below to get started — no account or password required.")
        + _btn(portal_url, "Open My Portal →")
        + _divider()
        + _p("This link is unique to you. Please keep it private and do not share it.", muted=True)
    )
    html = _base_html(subject, f"{firm} has sent you a document portal.", html_body)
    _send(subject, text, [client.email], html)


# ─────────────────────────────────────────────
# 2. MISSING DOCS REMINDER
# ─────────────────────────────────────────────

def send_missing_docs_reminder(client, missing_items):
    site_url = _site_url()
    portal_url = f"{site_url}/onboarding/{client.onboarding_token}/"
    firm = _firm_name(client)
    subject = f"Action required: missing documents — {firm}"

    missing_list = '\n'.join(f"  • {item}" for item in missing_items)
    text = f"""Hi {client.name},

{firm} is waiting on the following documents to proceed:

{missing_list}

Please upload them using your portal:
{portal_url}

If you have any questions, contact your accountant directly.

{firm}
Powered by Mortacc
"""
    items_html = ''.join(
        f'<li style="padding:5px 0;font-size:14px;color:#334155;">{item}</li>'
        for item in missing_items
    )
    html_body = (
        _h1("Documents still needed.")
        + _p(f"<strong>{firm}</strong> is waiting on the following items before your file can be completed:")
        + f'<ul style="margin:0 0 20px;padding-left:20px;">{items_html}</ul>'
        + _btn(portal_url, "Upload Documents →")
        + _divider()
        + _p("Once all documents are received, your accountant will proceed with your file.", muted=True)
    )
    html = _base_html(subject, f"Action required: {len(missing_items)} document(s) still needed.", html_body)
    _send(subject, text, [client.email], html)


# ─────────────────────────────────────────────
# 3. SUBMISSION NOTIFICATION (to accountant)
# ─────────────────────────────────────────────

def send_submission_notification(client):
    site_url = _site_url()
    client_url = f"{site_url}/clients/{client.id}/"
    subject = f"New submission ready for review — {client.name}"

    text = f"""Hi,

{client.name} has submitted all their documents and their onboarding portal is complete.

Review their file here:
{client_url}

Mortacc
"""
    html_body = (
        _h1("New submission ready.")
        + _p(f"<strong>{client.name}</strong> has completed their onboarding portal. All documents have been submitted and are ready for your review.")
        + _info_box([
            ("Client", client.name),
            ("Email", client.email or "—"),
            ("Status", "Submitted"),
        ])
        + _btn(client_url, "Review Submission →")
    )
    html = _base_html(subject, f"{client.name} has submitted their documents.", html_body)
    try:
        accountant_email = client.firm.users.first().email if client.firm else None
        if accountant_email:
            _send(subject, text, [accountant_email], html)
    except Exception:
        pass


# ─────────────────────────────────────────────
# 4. COMPLIANCE REMINDERS
# ─────────────────────────────────────────────

def _send_compliance_reminder(task, client, days_remaining, label, recipient_list):
    site_url = _site_url()
    client_url = f"{site_url}/clients/{client.id}/?tab=compliance"
    subject = f"Compliance reminder: {task.title} — {client.name} ({label})"

    text = f"""Compliance reminder for {client.name}:

Task: {task.title}
Due: {task.due_date.strftime('%B %d, %Y')}
Urgency: {label}

{task.description or ''}

View task: {client_url}

Mortacc
"""
    urgency_color = '#dc2626' if days_remaining <= 7 else '#d97706' if days_remaining <= 14 else '#2563eb'
    html_body = (
        _h1(f"Compliance deadline: {label}")
        + _p(f"The following task for <strong>{client.name}</strong> requires attention:")
        + _info_box([
            ("Task", task.title),
            ("Due Date", task.due_date.strftime('%B %d, %Y')),
            ("Days Remaining", f'<span style="color:{urgency_color};font-weight:700;">{days_remaining} days</span>'),
            ("Client", client.name),
        ])
        + (f'<p style="margin:0 0 14px;font-size:14px;color:#334155;">{task.description}</p>' if task.description else '')
        + _btn(client_url, "View Task →")
    )
    html = _base_html(subject, f"{task.title} due in {days_remaining} days for {client.name}.", html_body)
    _send(subject, text, recipient_list, html)


def send_compliance_reminders():
    from django.utils import timezone
    from .models import ComplianceTask, Client
    import datetime

    today = timezone.now().date()
    thresholds = [(30, '30 days'), (14, '14 days'), (7, '7 days')]

    tasks = ComplianceTask.objects.filter(
        status='pending',
        due_date__gte=today,
        due_date__lte=today + datetime.timedelta(days=30),
    ).select_related('client', 'client__firm')

    for task in tasks:
        days = (task.due_date - today).days
        for threshold, label in thresholds:
            if days == threshold:
                client = task.client
                try:
                    firm = client.firm
                    emails = list(firm.users.values_list('email', flat=True)) if firm else []
                    if emails:
                        _send_compliance_reminder(task, client, days, label, emails)
                except Exception as e:
                    logger.error("Compliance reminder failed for task %s: %s", task.id, e)


# ─────────────────────────────────────────────
# 5. WELCOME EMAIL (after signup)
# ─────────────────────────────────────────────

def send_welcome_email(user, firm_name, plan_name='Professional'):
    site_url = _site_url()
    subject = f"Welcome to Mortacc, {user.first_name or user.email.split('@')[0]}!"

    text = f"""Hi {user.first_name or 'there'},

Welcome to Mortacc — your firm's new home for corporate governance.

Firm: {firm_name}
Plan: {plan_name}
Login: {site_url}/login/

Get started:
  • Add your first client and send them an onboarding portal link
  • Start an incorporation for Federal, Ontario, BC, or Québec
  • Generate your first minute book PDF

Questions? Reply to support@mortacc.com

The Mortacc Team
"""
    first = user.first_name or user.email.split('@')[0]
    html_body = (
        _h1(f"Welcome to Mortacc, {first}.")
        + _p("Your account is live. Here's everything you need to get started:")
        + _info_box([
            ("Firm", firm_name),
            ("Plan", plan_name),
            ("Login", f'<a href="{site_url}/login/" style="color:#3b82f6;">{site_url}/login/</a>'),
        ])
        + '<p style="margin:16px 0 8px;font-size:13px;font-weight:700;color:#0f172a;text-transform:uppercase;letter-spacing:.5px;">Quick start</p>'
        + '<ul style="margin:0 0 20px;padding-left:18px;">'
        + '<li style="padding:4px 0;font-size:14px;color:#334155;">Add your first client and send them a portal link</li>'
        + '<li style="padding:4px 0;font-size:14px;color:#334155;">Start a Federal, Ontario, BC, or Québec incorporation</li>'
        + '<li style="padding:4px 0;font-size:14px;color:#334155;">Generate your first minute book PDF</li>'
        + '</ul>'
        + _btn(f"{site_url}/dashboard/", "Go to Dashboard →")
        + _divider()
        + _p("Questions or feedback? Email us at <a href='mailto:support@mortacc.com' style='color:#3b82f6;'>support@mortacc.com</a> — we read every message.", muted=True)
    )
    html = _base_html(subject, f"Welcome to Mortacc, {first}. Your account is ready.", html_body)
    _send(subject, text, [user.email], html)


# ─────────────────────────────────────────────
# 6. AGREEMENT CONFIRMATION
# ─────────────────────────────────────────────

def send_agreement_confirmation(user, firm_name, signed_name, signed_at):
    subject = "Mortacc Platform Agreement — Signed Confirmation"

    text = f"""Hi {user.first_name or 'there'},

This confirms that the Mortacc Platform Services Agreement has been signed.

Firm: {firm_name}
Signed by: {signed_name}
Email: {user.email}
Date & Time: {signed_at.strftime('%B %d, %Y at %H:%M UTC')}
Version: v1.0

Keep this email for your records.

If you did not sign this agreement, contact support@mortacc.com immediately.

The Mortacc Team
"""
    html_body = (
        '<div style="text-align:center;margin-bottom:24px;">'
        '<div style="display:inline-flex;align-items:center;justify-content:center;width:56px;height:56px;background:#dcfce7;border-radius:50%;font-size:26px;margin-bottom:12px;">✓</div>'
        '</div>'
        + _h1("Agreement signed.")
        + _p("This email confirms that the <strong>Mortacc Platform Services Agreement</strong> has been signed for your account. Please keep this for your records.")
        + _info_box([
            ("Firm", firm_name),
            ("Signed by", signed_name),
            ("Email", user.email),
            ("Date", signed_at.strftime('%B %d, %Y at %H:%M UTC')),
            ("Version", "v1.0"),
        ])
        + _divider()
        + _p("If you did not sign this agreement or have any concerns, contact us immediately at <a href='mailto:support@mortacc.com' style='color:#3b82f6;'>support@mortacc.com</a>.", muted=True)
    )
    html = _base_html(subject, "Your Mortacc Platform Agreement has been signed.", html_body)
    _send(subject, text, [user.email], html)


# ─────────────────────────────────────────────
# STAFF INVITE
# ─────────────────────────────────────────────

def send_staff_invite(invite):
    site_url = _site_url()
    accept_url = f"{site_url}/staff/accept/{invite.token}/"
    inviter_name = invite.invited_by.get_full_name() if invite.invited_by else "Your firm admin"
    first = invite.first_name or invite.email.split("@")[0]

    subject = f"You've been invited to join {invite.firm.name} on Mortacc"

    text = f"""Hi {first},

{inviter_name} has invited you to join {invite.firm.name} on Mortacc as {invite.get_role_display()}.

Accept your invitation here:
{accept_url}

This link expires in 7 days.

The Mortacc Team
"""
    html_body = (
        _h1(f"You're invited to {invite.firm.name}")
        + _p(f"{inviter_name} has invited you to join <strong>{invite.firm.name}</strong> on Mortacc as <strong>{invite.get_role_display()}</strong>.")
        + _btn(accept_url, "Accept Invitation →")
        + _divider()
        + _p("This invitation expires in 7 days. If you weren't expecting this, you can ignore it.", muted=True)
    )
    html = _base_html(subject, f"You've been invited to join {invite.firm.name} on Mortacc.", html_body)
    _send(subject, text, [invite.email], html)
