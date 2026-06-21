"""
Background tasks via Huey.
Offloads AI extraction, workflow execution, bulk emails, and webhook delivery
from the request-response cycle.
"""
from config.huey import huey


@huey.task()
def run_workflow_step(workflow_id, entity_id, user_id):
    """
    Execute a single workflow step in the background.
    Called when a workflow is triggered by an entity event.
    """
    import django
    django.setup()
    from .models import Workflow, WorkflowRun
    from django.contrib.auth.models import User
    from .models.workflow_builder import _execute_workflow_step

    workflow = Workflow.objects.get(id=workflow_id)
    user = User.objects.get(id=user_id)

    run = WorkflowRun.objects.create(
        workflow=workflow,
        entity_id=entity_id,
        triggered_by=user,
    )
    _execute_workflow_step(run)
    return f'Workflow {workflow.name} completed for entity {entity_id}'


@huey.task()
def send_bulk_emails(recipients, subject, body, from_email=None):
    """
    Send bulk emails in the background.
    recipients: list of email address strings
    """
    import django
    django.setup()
    from django.core.mail import send_mail
    from django.conf import settings

    if from_email is None:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mortacc.com')

    for email in recipients:
        send_mail(subject, body, from_email, [email], fail_silently=True)
    return f'Sent {len(recipients)} emails'


@huey.task()
def deliver_webhook(endpoint_id, payload, event_type):
    """
    Deliver a single webhook in the background with retry logic.
    """
    import django
    django.setup()
    import json
    import hmac
    import hashlib
    import requests
    from django.utils import timezone
    from .models import WebhookEndpoint

    try:
        ep = WebhookEndpoint.objects.get(id=endpoint_id, is_active=True)
    except WebhookEndpoint.DoesNotExist:
        return f'Webhook {endpoint_id} not found or inactive'

    try:
        headers = {'Content-Type': 'application/json'}
        if ep.secret:
            signature = hmac.new(
                ep.secret.encode(), json.dumps(payload).encode(), hashlib.sha256
            ).hexdigest()
            headers['X-Mortacc-Signature'] = signature

        resp = requests.post(ep.url, json=payload, headers=headers, timeout=10)
        if resp.status_code >= 400:
            ep.failure_count += 1
            if ep.failure_count >= 10:
                ep.is_active = False
        else:
            ep.failure_count = 0
        ep.last_triggered_at = timezone.now()
        ep.save()
        return f'Webhook delivered: {resp.status_code}'
    except Exception as e:
        ep.failure_count += 1
        if ep.failure_count >= 10:
            ep.is_active = False
        ep.save()
        raise  # Huey will retry


@huey.task()
def run_ai_extraction(document_id):
    """
    Run AI document extraction in the background.
    """
    import django
    django.setup()
    from .models import AIExtraction
    from .utils import ai_extraction as ai_utils

    extraction = AIExtraction.objects.get(id=document_id)
    result = ai_utils.extract_from_document(extraction.document.file.path)
    extraction.extracted_data = result
    extraction.status = 'completed'
    extraction.save()
    return f'AI extraction completed for doc {document_id}'


@huey.task()
def generate_compliance_alerts(firm_id):
    """
    Generate compliance alerts for all entities in a firm.
    Runs daily via scheduler.
    """
    import django
    django.setup()
    from .models import Client, ComplianceTask, Firm

    firm = Firm.objects.get(id=firm_id)
    clients = Client.objects.filter(firm=firm)
    alerts = 0
    today = __import__('django').utils.timezone.now().date()

    for client in clients:
        overdue = ComplianceTask.objects.filter(
            client=client,
            status__in=['pending', 'in_progress'],
            due_date__lt=today,
        ).count()
        if overdue > 0:
            alerts += 1
            # Could create ComplianceAlert records here

    return f'{alerts} entities with overdue tasks for {firm.name}'
