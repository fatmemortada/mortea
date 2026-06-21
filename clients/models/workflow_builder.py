"""
No-Code Workflow Builder.

Firms define custom workflows: triggers → conditions → actions.
"When incorporation complete → create compliance tasks →
send engagement letter → create invoice."

This is the enterprise automation layer.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .client import Firm


class Workflow(models.Model):
    """A custom automated workflow defined by a firm."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('archived', 'Archived'),
    ]
    TRIGGER_CHOICES = [
        ('client_created', 'Client Created'),
        ('incorporation_complete', 'Incorporation Complete'),
        ('onboarding_submitted', 'Onboarding Submitted'),
        ('compliance_task_completed', 'Compliance Task Completed'),
        ('invoice_paid', 'Invoice Paid'),
        ('subscription_activated', 'Subscription Activated'),
        ('registration_filed', 'Registration Filed'),
        ('document_signed', 'Document Signed'),
        ('risk_scan_complete', 'Risk Scan Complete'),
        ('remediation_complete', 'Remediation Complete'),
        ('custom_date', 'Scheduled Date'),
        ('manual', 'Manual Trigger'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='workflows')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Trigger
    trigger_event = models.CharField(max_length=50, choices=TRIGGER_CHOICES, default='manual')
    trigger_config = models.JSONField(default=dict, blank=True, help_text='Additional trigger conditions')

    # Steps (ordered list of actions)
    steps_config = models.JSONField(default=list, blank=True, help_text='Ordered list of action steps')

    # Stats
    run_count = models.PositiveIntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['firm', 'status']),
        ]
        verbose_name = 'Workflow'
        verbose_name_plural = 'Workflows'

    def __str__(self):
        return f"{self.name} — {self.firm.name} ({self.get_status_display()})"

    def execute(self, context=None):
        """Execute the workflow steps in order."""
        import logging
        logger = logging.getLogger(__name__)

        executed = 0
        for step_config in self.steps_config:
            try:
                _execute_workflow_step(step_config, context or {}, self.firm_id)
                executed += 1
            except Exception as e:
                logger.error(f'Workflow {self.name} step failed: {e}')
                WorkflowRun.objects.create(
                    workflow=self,
                    status='failed',
                    steps_executed=executed,
                    error_message=str(e),
                    context=context or {},
                )
                return executed

        self.run_count += 1
        self.last_run_at = timezone.now()
        self.save()

        WorkflowRun.objects.create(
            workflow=self,
            status='completed',
            steps_executed=executed,
            context=context or {},
        )
        return executed


def _execute_workflow_step(step_config, context, firm_id):
    """Execute a single workflow step."""
    action = step_config.get('action', '')
    config = step_config.get('config', {})

    if action == 'create_compliance_tasks':
        _wf_create_compliance_tasks(context, config)
    elif action == 'send_engagement_letter':
        _wf_send_engagement_letter(context, config, firm_id)
    elif action == 'create_invoice':
        _wf_create_invoice(context, config, firm_id)
    elif action == 'send_email':
        _wf_send_email(context, config, firm_id)
    elif action == 'assign_task':
        _wf_assign_task(context, config)
    elif action == 'update_client_status':
        _wf_update_client_status(context, config)
    elif action == 'generate_documents':
        _wf_generate_documents(context, config)
    elif action == 'create_subscription':
        _wf_create_subscription(context, config)
    else:
        raise ValueError(f'Unknown workflow action: {action}')


def _wf_create_compliance_tasks(context, config):
    client_id = context.get('client_id')
    if client_id:
        from .compliance import _create_compliance_tasks
        from .corporate import CorporateProfile
        profile = CorporateProfile.objects.filter(client_id=client_id).first()
        if profile:
            _create_compliance_tasks(profile)


def _wf_send_engagement_letter(context, config, firm_id):
    client_id = context.get('client_id')
    if client_id:
        from django.core.mail import send_mail
        from .client import Client
        client = Client.objects.filter(id=client_id).first()
        if client:
            template = config.get('template', 'Standard engagement terms apply.')
            send_mail(
                subject=f'Engagement Letter — {client.name}',
                message=template,
                from_email='support@mortacc.com',
                recipient_list=[client.email],
                fail_silently=True,
            )


def _wf_create_invoice(context, config, firm_id):
    client_id = context.get('client_id')
    if client_id:
        from .billing import Invoice
        from datetime import date, timedelta
        Invoice.objects.create(
            client_id=client_id,
            description=config.get('description', 'Professional services'),
            service_type=config.get('service_type', 'other'),
            amount=float(config.get('amount', 0)),
            status='sent',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
        )


def _wf_send_email(context, config, firm_id):
    from django.core.mail import send_mail
    recipient = config.get('recipient', context.get('client_email', ''))
    if recipient:
        send_mail(
            subject=config.get('subject', 'Update from your accountant'),
            message=config.get('body', ''),
            from_email='notifications@mortacc.com',
            recipient_list=[recipient],
            fail_silently=True,
        )


def _wf_assign_task(context, config):
    user_id = config.get('user_id')
    client_id = context.get('client_id')
    if user_id and client_id:
        from .platform import ChasingTask
        ChasingTask.objects.create(
            client_id=client_id,
            title=config.get('title', 'Follow up'),
            description=config.get('description', ''),
        )


def _wf_update_client_status(context, config):
    client_id = context.get('client_id')
    new_status = config.get('status')
    if client_id and new_status:
        from .client import Client
        Client.objects.filter(id=client_id).update(status=new_status)


def _wf_generate_documents(context, config):
    """
    Generate documents for a client based on document_types in config.
    Creates Document records that can be filled/finalized from the document manager.
    Uses existing DocumentTemplate system when templates are available.
    """
    doc_types = config.get('document_types', [])
    client_id = context.get('client_id')

    if not client_id or not doc_types:
        return

    from .client import Client
    from .platform import Document
    from django.utils import timezone

    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        return

    # Map document types to titles and categories
    DOC_META = {
        'articles': ('Articles of Incorporation', 'incorporation'),
        'bylaws': ('By-Laws', 'incorporation'),
        'resolutions': ('Corporate Resolutions', 'minutes'),
        'annual_resolutions': ('Annual Resolutions', 'minutes'),
        'directors_register': ('Register of Directors', 'registers'),
        'shareholders_register': ('Register of Shareholders', 'registers'),
        'officers_register': ('Register of Officers', 'registers'),
        'securities_register': ('Central Securities Register', 'registers'),
        'share_certificates': ('Share Certificates', 'shares'),
        'directors_consent': ('Consent to Act as Director', 'incorporation'),
        'shareholder_agreement': ('Shareholder Agreement', 'agreements'),
        'minute_book_update': ('Minute Book Update', 'minutes'),
        'compliance_report': ('Compliance Summary Report', 'compliance'),
        'entity_summary': ('Entity Summary', 'general'),
    }

    created = 0
    for doc_type in doc_types:
        title, category = DOC_META.get(doc_type, (doc_type.replace('_', ' ').title(), 'general'))

        # Check if a DocumentTemplate exists for this type
        from .templates import DocumentTemplate
        template = DocumentTemplate.objects.filter(
            name__icontains=doc_type
        ).first()

        Document.objects.create(
            client=client,
            title=f'{title} — {client.name}',
            category=category,
            description=f'Auto-generated by workflow. Template: {template.name if template else "Standard"}',
            created_by=None,  # System-generated
            uploaded_at=timezone.now(),
        )
        created += 1

    # Log the generation
    from .activity import log_activity
    log_activity(
        None, 'generate', 'Document', client.id, client.name,
        f'Workflow generated {created} document(s) for {client.name}',
        firm=client.firm,
    )


def _wf_create_subscription(context, config):
    client_id = context.get('client_id')
    plan_id = config.get('plan_id')
    if client_id and plan_id:
        from .subscription import EntitySubscription, SubscriptionPlan
        plan = SubscriptionPlan.objects.filter(id=plan_id).first()
        if plan:
            from datetime import date, timedelta
            EntitySubscription.objects.create(
                client_id=client_id,
                plan=plan,
                firm_id=plan.firm_id if hasattr(plan, 'firm_id') else None,
                billing_cycle=config.get('billing_cycle', 'annual'),
                current_period_start=date.today(),
                current_period_end=date.today() + timedelta(days=365),
                next_billing_date=date.today() + timedelta(days=365),
            )


class WorkflowRun(models.Model):
    """Record of a workflow execution."""
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='runs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    steps_executed = models.PositiveIntegerField(default=0)
    total_steps = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    context = models.JSONField(default=dict, blank=True, help_text='Context data used for this run')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Workflow Run'
        verbose_name_plural = 'Workflow Runs'

    def __str__(self):
        return f"{self.workflow.name} — Run #{self.id} ({self.get_status_display()})"


# Built-in workflow templates
BUILT_IN_WORKFLOWS = [
    {
        'name': 'New Incorporation Flow',
        'description': 'Standard workflow when a new incorporation is completed.',
        'trigger_event': 'incorporation_complete',
        'steps_config': [
            {'action': 'create_compliance_tasks', 'config': {}},
            {'action': 'generate_documents', 'config': {'document_types': ['articles', 'bylaws', 'resolutions']}},
            {'action': 'create_invoice', 'config': {'description': 'Incorporation services', 'service_type': 'incorporation', 'amount': 1499}},
            {'action': 'send_email', 'config': {'subject': 'Your incorporation is complete!', 'body': 'Your new corporation has been set up. Welcome package to follow.'}},
        ],
    },
    {
        'name': 'Annual Maintenance Renewal',
        'description': 'Triggered when a subscription is activated for annual maintenance.',
        'trigger_event': 'subscription_activated',
        'steps_config': [
            {'action': 'create_compliance_tasks', 'config': {}},
            {'action': 'generate_documents', 'config': {'document_types': ['annual_resolutions', 'minute_book_update']}},
            {'action': 'create_invoice', 'config': {'description': 'Annual corporate maintenance', 'service_type': 'annual_maintenance', 'amount': 799}},
        ],
    },
    {
        'name': 'Onboarding Follow-Up',
        'description': 'When a new client submits onboarding, send engagement letter and create tasks.',
        'trigger_event': 'onboarding_submitted',
        'steps_config': [
            {'action': 'send_engagement_letter', 'config': {'template': 'Thank you for submitting your information. Our standard engagement terms are attached.'}},
            {'action': 'assign_task', 'config': {'title': 'Review onboarding submission', 'description': 'Review the submitted documents and information.'}},
        ],
    },
]
