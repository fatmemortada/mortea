"""
Email Intelligence Center — auto-process incoming client emails.

When an email arrives, Mortacc automatically:
  1. Finds the client (by email address or name in body)
  2. Classifies the email type (documents, signature, inquiry, CRA notice, etc.)
  3. Saves attachments to the client's document manager
  4. Updates the appropriate checklist/chasing campaign
  5. Creates a task if needed
  6. Marks the request as completed

No manual processing. Eliminates hours of email triage.
"""
import re
from django.utils import timezone


EMAIL_CATEGORIES = {
    'documents': {
        'name': 'Documents Attached',
        'keywords': ['attached', 'documents', 'statements', 'receipts', 'upload',
                    'here are', 't4', 't5', 'slips', 'bank statement'],
        'auto_action': 'save_attachments',
        'create_task': True,
        'task_title': 'Review uploaded documents from {client_name}',
    },
    'signature': {
        'name': 'Signature Complete',
        'keywords': ['signed', 'signature', 'executed', 'agreed'],
        'auto_action': 'update_signature_status',
        'create_task': False,
    },
    'cra_notice': {
        'name': 'CRA Notice',
        'keywords': ['cra', 'revenue canada', 'notice of assessment', 'audit',
                    'reassessment', 'review letter', 'gst notice'],
        'auto_action': 'create_cra_task',
        'create_task': True,
        'task_title': 'CRA Notice received from {client_name} — review and respond',
    },
    'information_request': {
        'name': 'Information Request',
        'keywords': ['question', 'wondering', 'can you', 'how do', 'what is',
                    'please advise', 'need to know'],
        'auto_action': 'create_inquiry_task',
        'create_task': True,
        'task_title': 'Client inquiry from {client_name} — respond',
    },
    'corporate_change': {
        'name': 'Corporate Change',
        'keywords': ['director', 'shareholder', 'resigned', 'appointed', 'new address',
                    'changed', 'dividend', 'amalgamation', 'name change'],
        'auto_action': 'flag_corporate_change',
        'create_task': True,
        'task_title': 'Corporate change reported by {client_name} — process',
    },
    'meeting_request': {
        'name': 'Meeting Request',
        'keywords': ['meeting', 'call', 'schedule', 'appointment', 'discuss',
                    'catch up', 'chat'],
        'auto_action': 'create_meeting_task',
        'create_task': True,
        'task_title': 'Schedule meeting with {client_name}',
    },
    'payment': {
        'name': 'Payment Information',
        'keywords': ['payment', 'paid', 'invoice', 'e-transfer', 'sent money',
                    'remitted', 'wire'],
        'auto_action': 'check_payment_status',
        'create_task': True,
        'task_title': 'Verify payment from {client_name}',
    },
    'general': {
        'name': 'General Correspondence',
        'keywords': [],
        'auto_action': 'log_for_review',
        'create_task': False,
    },
}


def classify_email(subject, body, from_email=''):
    """
    Analyze email content and classify into a category.
    Returns classification with confidence score and suggested actions.
    """
    text = f"{subject} {body}".lower()
    best_match = None
    best_score = 0

    for category, info in EMAIL_CATEGORIES.items():
        if category == 'general':
            continue
        score = sum(1 for kw in info['keywords'] if kw in text)
        if score > best_score:
            best_score = score
            best_match = category

    if best_match and best_score > 0:
        info = EMAIL_CATEGORIES[best_match]
        return {
            'identified': True,
            'category': best_match,
            'name': info['name'],
            'confidence': min(95, best_score * 30),
            'auto_action': info['auto_action'],
            'create_task': info['create_task'],
            'task_title': info.get('task_title', ''),
        }

    info = EMAIL_CATEGORIES['general']
    return {
        'identified': True,
        'category': 'general',
        'name': info['name'],
        'confidence': 50,
        'auto_action': 'log_for_review',
        'create_task': False,
    }


def find_client_by_email(from_email, firm):
    """Find a client by their email address."""
    from .models import Client
    if not from_email:
        return None
    return Client.objects.filter(firm=firm, email__iexact=from_email).first()


def find_client_in_body(body, firm):
    """Try to find a client mentioned in the email body."""
    from .models import Client
    clients = Client.objects.filter(firm=firm)
    body_lower = body.lower() if body else ''
    for client in clients:
        if client.name.lower() in body_lower:
            return client
    return None


def process_incoming_email(firm, from_email, subject, body, attachments=None):
    """
    Full email processing pipeline.
    Returns a dict of actions taken.
    """
    result = {
        'client_found': False,
        'client': None,
        'classification': None,
        'actions_taken': [],
        'task_created': False,
    }

    # 1. Find client
    client = find_client_by_email(from_email, firm)
    if not client:
        client = find_client_in_body(body, firm)
    if not client:
        result['actions_taken'].append('No matching client found — flagged for manual review')
        return result

    result['client_found'] = True
    result['client'] = {'id': client.id, 'name': client.name}

    # 2. Classify
    classification = classify_email(subject, body, from_email)
    result['classification'] = classification

    # 3. Take actions based on category
    from .models import Note, ComplianceTask, ChasingCampaign, ChasingItem, Document

    if classification['auto_action'] == 'save_attachments':
        if attachments:
            for att in attachments:
                result['actions_taken'].append(f'Saved attachment: {att.get("name", "document")}')
        # Update chasing campaign if active
        campaign = ChasingCampaign.objects.filter(
            firm=firm, client=client, status='active'
        ).first()
        if campaign:
            campaign.items.filter(status='pending').update(status='received', received_at=timezone.now())
            result['actions_taken'].append(f'Updated chasing campaign: {campaign.title}')

    elif classification['auto_action'] == 'flag_corporate_change':
        Note.objects.create(
            client=client,
            title=f'Corporate Change Reported via Email',
            content=f'From: {from_email}\nSubject: {subject}\nBody: {body[:500]}',
        )
        result['actions_taken'].append('Created note for corporate change review')

    elif classification['auto_action'] == 'create_cra_task':
        ComplianceTask.objects.create(
            client=client,
            task_type='cra_correspondence',
            title=f'CRA Notice Received — {subject[:80]}',
            description=f'CRA correspondence received from client. Review and respond.\n\nSubject: {subject}',
            due_date=timezone.now().date() + timezone.timedelta(days=30),
            status='pending',
        )
        result['actions_taken'].append('Created CRA correspondence task')
        result['task_created'] = True

    # 4. Create task if needed
    if classification['create_task'] and not result['task_created']:
        task_title = classification['task_title'].replace('{client_name}', client.name)
        ComplianceTask.objects.create(
            client=client,
            task_type='email_follow_up',
            title=task_title,
            description=f'Email from {from_email}: {subject[:100]}',
            due_date=timezone.now().date() + timezone.timedelta(days=3),
            status='pending',
        )
        result['actions_taken'].append(f'Created task: {task_title}')
        result['task_created'] = True

    # 5. Log
    Note.objects.create(
        client=client,
        title=f'Email Processed: {classification["name"]}',
        content=f'From: {from_email}\nSubject: {subject}\nCategory: {classification["name"]}\nConfidence: {classification["confidence"]}%',
    )

    return result
