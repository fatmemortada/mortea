"""AI Email Triage + Auto-Response views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.utils import timezone
from datetime import date, timedelta

from ..models import (
    Client, EmailTriage, AutoResponseTemplate, EmailRule,
    TimeEntry, log_activity,
)
from ._helpers import _get_firm


@login_required
def email_triage_inbox(request):
    """AI-powered email triage inbox."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    triages = EmailTriage.objects.filter(
        firm=firm
    ).select_related('client').order_by('-received_at')

    pending = triages.filter(status='pending')
    approved = triages.filter(status='approved')
    escalated = triages.filter(status='escalated')

    # Stats
    today = date.today()
    week_ago = today - timedelta(days=7)
    this_week = triages.filter(received_at__date__gte=week_ago).count()
    auto_handled = triages.filter(status='approved', response_sent=True).count()

    # Templates and rules
    templates = AutoResponseTemplate.objects.filter(firm=firm, is_active=True)
    rules = EmailRule.objects.filter(firm=firm, is_active=True)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'ingest_email':
            # Simulate AI triage of a new email
            from_email = request.POST.get('from_email', '').strip()
            subject = request.POST.get('subject', '').strip()
            body = request.POST.get('body', '').strip()
            client_id = request.POST.get('client_id')

            if from_email and subject:
                client = Client.objects.filter(id=client_id, firm=firm).first()
                triage = _ai_triage_email(client, firm, from_email, subject, body)
                messages.success(request, f'Email triaged: {triage.get_category_display()} (confidence: {triage.confidence:.0%})')

        elif action == 'approve_response':
            triage_id = request.POST.get('triage_id')
            triage = get_object_or_404(EmailTriage, id=triage_id, firm=firm, status='pending')
            triage.status = 'approved'
            triage.reviewed_by = request.user
            triage.reviewed_at = timezone.now()
            triage.final_response = triage.draft_response
            triage.save()

            # Send the response
            send_mail(
                subject=triage.draft_subject or f'Re: {triage.subject}',
                message=triage.draft_response,
                from_email='support@mortacc.com',
                recipient_list=[triage.from_email],
                fail_silently=True,
            )
            triage.response_sent = True
            triage.response_sent_at = timezone.now()
            triage.save()

            # Create time entry if suggested
            if triage.suggested_time_entry:
                TimeEntry.objects.create(
                    client=triage.client or triage.matched_client,
                    user=request.user,
                    description=f'Email response: {triage.subject[:100]}',
                    date=today, hours=triage.suggested_minutes / 60,
                    hourly_rate=250, category='consultation',
                    auto_generated=True,
                )

            log_activity(triage.client, f'AI-drafted response approved and sent', request.user)
            messages.success(request, 'Response sent!')

        elif action == 'modify_response':
            triage_id = request.POST.get('triage_id')
            triage = get_object_or_404(EmailTriage, id=triage_id, firm=firm)
            triage.status = 'modified'
            triage.reviewed_by = request.user
            triage.reviewed_at = timezone.now()
            triage.final_response = request.POST.get('final_response', triage.draft_response)
            triage.save()

            send_mail(
                subject=request.POST.get('final_subject', f'Re: {triage.subject}'),
                message=triage.final_response,
                from_email='support@mortacc.com',
                recipient_list=[triage.from_email],
                fail_silently=True,
            )
            triage.response_sent = True
            triage.response_sent_at = timezone.now()
            triage.save()
            messages.success(request, 'Modified response sent!')

        elif action == 'dismiss':
            triage_id = request.POST.get('triage_id')
            triage = get_object_or_404(EmailTriage, id=triage_id, firm=firm)
            triage.status = 'dismissed'
            triage.reviewed_by = request.user
            triage.reviewed_at = timezone.now()
            triage.save()

        elif action == 'escalate':
            triage_id = request.POST.get('triage_id')
            triage = get_object_or_404(EmailTriage, id=triage_id, firm=firm)
            triage.status = 'escalated'
            triage.save()
            messages.warning(request, 'Email escalated for manual review.')

        elif action == 'save_template':
            name = request.POST.get('template_name', '').strip()
            category = request.POST.get('template_category', 'inquiry')
            subject = request.POST.get('template_subject', '')
            body = request.POST.get('template_body', '')
            if name:
                AutoResponseTemplate.objects.create(firm=firm, name=name, category=category, subject_template=subject, body_template=body)
                messages.success(request, f'Template "{name}" saved.')

        elif action == 'save_rule':
            name = request.POST.get('rule_name', '').strip()
            match_field = request.POST.get('rule_match_field', 'subject')
            match_pattern = request.POST.get('rule_match_pattern', '').strip()
            action_type = request.POST.get('rule_action', 'categorize')
            action_value = request.POST.get('rule_action_value', '').strip()
            if name and match_pattern:
                EmailRule.objects.create(firm=firm, name=name, match_field=match_field, match_pattern=match_pattern, action=action_type, action_value=action_value)
                messages.success(request, f'Rule "{name}" created.')

        return redirect('email_triage')

    return render(request, 'clients/email_triage_inbox.html', {
        'firm': firm, 'triages': triages, 'pending': pending,
        'approved': approved, 'escalated': escalated,
        'this_week': this_week, 'auto_handled': auto_handled,
        'templates': templates, 'rules': rules,
        'clients': Client.objects.filter(firm=firm),
        'categories': EmailTriage.CATEGORY_CHOICES,
    })


def _ai_triage_email(client, firm, from_email, subject, body):
    """AI-powered email classification and response drafting."""
    import re

    # Simple keyword-based classification (production would use Claude API)
    subject_lower = subject.lower()
    body_lower = body.lower()

    # Classify
    category = 'inquiry'
    confidence = 0.7

    if any(w in subject_lower for w in ['urgent', 'asap', 'deadline', 'immediately']):
        category = 'urgent'; confidence = 0.85
    elif any(w in subject_lower + ' ' + body_lower for w in ['document', 'copy', 'certificate', 'need a']):
        category = 'document_request'; confidence = 0.8
    elif any(w in subject_lower for w in ['status', 'update', 'progress', 'what is happening']):
        category = 'status_update'; confidence = 0.75
    elif any(w in subject_lower for w in ['invoice', 'bill', 'payment', 'charge']):
        category = 'billing'; confidence = 0.85
    elif any(w in subject_lower for w in ['tax', 't2', 'hst', 'gst', 'cra']):
        category = 'tax'; confidence = 0.8
    elif any(w in subject_lower for w in ['compliance', 'deadline', 'filing', 'annual']):
        category = 'compliance'; confidence = 0.8
    elif any(w in subject_lower for w in ['address', 'change', 'update director', 'new director']):
        category = 'change_request'; confidence = 0.85
    elif any(w in subject_lower for w in ['incorporat', 'new company', 'startup']):
        category = 'incorporation'; confidence = 0.8
    elif any(w in subject_lower for w in ['complaint', 'unhappy', 'disappointed', 'problem']):
        category = 'complaint'; confidence = 0.9

    # Sentiment
    sentiment = 'neutral'
    if any(w in body_lower for w in ['thank', 'great', 'appreciate', 'excellent']):
        sentiment = 'positive'
    elif any(w in body_lower for w in ['urgent', 'asap', 'immediately', 'critical']):
        sentiment = 'urgent'
    elif any(w in body_lower for w in ['unhappy', 'complaint', 'problem', 'issue', 'wrong']):
        sentiment = 'negative'

    # Extract key topics
    topics = []
    for keyword in ['annual return', 'minute book', 'director', 'shareholder', 'tax', 'invoice', 'incorporation',
                     'filing', 'resolution', 'dividend', 'address', 'banking']:
        if keyword in body_lower:
            topics.append(keyword)

    # Draft response
    client_name = client.name if client else 'there'
    draft = f"Dear {client_name},\n\n"
    if category == 'document_request':
        draft += f"Thank you for your request. I will prepare the requested document and send it to you shortly.\n\n"
    elif category == 'status_update':
        draft += f"Thank you for checking in. Your file is progressing well. I will provide a detailed update by the end of the week.\n\n"
    elif category == 'urgent':
        draft += f"I have received your urgent inquiry and will address it as a priority. I will respond by end of business today.\n\n"
    elif category == 'billing':
        draft += f"Thank you for your inquiry regarding your invoice. I will review and respond with the details shortly.\n\n"
    elif category == 'change_request':
        draft += f"Thank you for notifying us of this change. We will prepare the necessary documentation and file the update with the registry.\n\n"
    elif category == 'compliance':
        draft += f"Thank you for your compliance question. I am reviewing your filing status and will confirm the deadlines.\n\n"
    else:
        draft += f"Thank you for your email. I have received your message and will respond in detail within 1-2 business days.\n\n"
    draft += f"Best regards,\n{firm.name if firm else 'Your Team'}\n\n---\nThis response was AI-drafted and is pending your review."

    # Extract action items
    actions = []
    if category in ['document_request', 'change_request']:
        actions.append({'action': 'Prepare requested document', 'priority': 'normal', 'deadline': str(date.today() + timedelta(days=2))})
    if category == 'urgent':
        actions.append({'action': 'Respond to urgent client inquiry', 'priority': 'high', 'deadline': str(date.today())})

    # Create triage record
    triage = EmailTriage.objects.create(
        client=client, firm=firm,
        from_email=from_email, from_name='', subject=subject, body=body,
        received_at=timezone.now(), category=category, confidence=confidence,
        sentiment=sentiment, key_topics=topics,
        draft_response=draft, draft_subject=f'Re: {subject}',
        action_items=actions,
        suggested_time_entry=True,
        suggested_minutes=15 if category != 'urgent' else 30,
        suggested_category='consultation',
    )

    return triage
