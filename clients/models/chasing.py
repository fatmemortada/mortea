"""
Auto Client Chasing System — Level 1 of Mortacc automation.

Zero-touch document follow-up:
- Generate request lists automatically
- Send reminders automatically at escalating intervals
- Escalate to accountant after threshold
- Track completeness automatically
"""
from django.db import models
from django.utils import timezone
from .client import Client, Firm


class ChasingCampaign(models.Model):
    """A document-chasing campaign for a specific client."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('escalated', 'Escalated to Accountant'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='chasing_campaigns')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='chasing_campaigns')
    title = models.CharField(max_length=255, help_text='e.g. "2026 Annual Maintenance Documents"')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Escalation settings
    max_reminders = models.PositiveIntegerField(default=5)
    escalate_after_days = models.PositiveIntegerField(default=14)
    escalate_to_email = models.EmailField(blank=True)

    # Tracking
    reminder_count = models.PositiveIntegerField(default=0)
    last_reminder_sent = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.client.name} — {self.title} ({self.get_status_display()})'


class ChasingItem(models.Model):
    """A single requested item within a chasing campaign."""

    ITEM_TYPES = [
        ('document', 'Document Upload'),
        ('signature', 'E-Signature'),
        ('form', 'Form Completion'),
        ('information', 'Information Request'),
        ('payment', 'Payment'),
    ]

    campaign = models.ForeignKey(ChasingCampaign, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES, default='document')
    description = models.CharField(max_length=500)
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending'),
        ('received', 'Received'),
        ('waived', 'Waived'),
    ])
    due_date = models.DateField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['status', 'due_date']

    def __str__(self):
        return f'{self.description} ({self.get_status_display()})'


def generate_chasing_campaign(client, title=None, items=None):
    """
    Auto-generate a chasing campaign with items based on what's missing.
    Called from views, scheduler, or signals.
    """
    from .compliance import ComplianceTask
    from .corporate import CorporateProfile, AnnualFiling, Director
    from .billing import Invoice

    today = timezone.now().date()

    if title is None:
        title = f'Document Request — {today.strftime("%B %Y")}'

    campaign = ChasingCampaign.objects.create(
        firm=client.firm,
        client=client,
        title=title,
        status='active',
    )

    if items is None:
        items = []

    generated_items = []

    # Auto-detect missing documents
    if not getattr(client, 'onboarding_submitted_at', None):
        generated_items.append({
            'item_type': 'document',
            'description': 'Complete onboarding submission (ID, tax docs, banking info)',
            'due_date': today + timezone.timedelta(days=7),
        })

    # Check compliance tasks
    overdue_tasks = ComplianceTask.objects.filter(
        client=client, status__in=['pending', 'overdue'],
        due_date__lte=today + timezone.timedelta(days=30),
    )
    for task in overdue_tasks[:5]:
        generated_items.append({
            'item_type': 'information',
            'description': f'{task.title} — provide supporting documents',
            'due_date': task.due_date,
        })

    # Check annual filings
    cp = getattr(client, 'corporate_profile', None)
    if cp and cp.incorporation_date:
        current_filing = AnnualFiling.objects.filter(
            client=client, year__gte=today.year,
            status='filed',
        ).exists()
        if not current_filing:
            generated_items.append({
                'item_type': 'form',
                'description': 'Annual Return filing information for current year',
                'due_date': today + timezone.timedelta(days=30),
            })

    # Check invoices
    overdue_invoices = Invoice.objects.filter(
        client=client, status__in=['sent', 'overdue'],
        due_date__lt=today,
    )
    if overdue_invoices.exists():
        generated_items.append({
            'item_type': 'payment',
            'description': f'Settle {overdue_invoices.count()} overdue invoice(s)',
            'due_date': today + timezone.timedelta(days=3),
        })

    # Check director consents
    directors_missing_consent = Director.objects.filter(
        client=client, consent_signed=False,
    ) if hasattr(Director, 'consent_signed') else Director.objects.none()
    for d in directors_missing_consent:
        generated_items.append({
            'item_type': 'signature',
            'description': f'Director consent form — {d.full_name}',
            'due_date': today + timezone.timedelta(days=14),
        })

    # Add custom items
    generated_items.extend(items)

    # Create ChasingItems
    for item in generated_items:
        ChasingItem.objects.create(
            campaign=campaign,
            item_type=item.get('item_type', 'document'),
            description=item['description'],
            due_date=item.get('due_date', today + timezone.timedelta(days=14)),
        )

    return campaign


def send_chasing_reminders():
    """
    Scheduler job — runs daily. Sends reminders for active campaigns.
    Escalates campaigns that exceed their threshold.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    import logging

    logger = logging.getLogger(__name__)
    today = timezone.now().date()

    active_campaigns = ChasingCampaign.objects.filter(
        status='active',
        reminder_count__lt=models.F('max_reminders'),
    ).select_related('client__firm')

    sent = 0
    escalated = 0

    for campaign in active_campaigns:
        days_since_created = (today - campaign.created_at.date()).days
        site_url = getattr(settings, 'SITE_URL', 'https://mortacc.com')

        # Determine escalation level
        if days_since_created >= campaign.escalate_after_days:
            campaign.status = 'escalated'
            campaign.escalated_at = timezone.now()
            campaign.save()

            # Notify accountant
            from django.contrib.auth.models import User
            accountants = User.objects.filter(
                userprofile__firm=campaign.firm,
                is_active=True,
            ).values_list('email', flat=True)

            pending_items = campaign.items.filter(status='pending')
            item_list = '\n'.join([f'  • {i.description}' for i in pending_items[:10]])

            for email in accountants:
                try:
                    send_mail(
                        subject=f'⚠ ESCALATED: {campaign.client.name} — {campaign.title}',
                        message=f"""CLIENT FOLLOW-UP ESCALATED

{campaign.client.name} has not responded after {days_since_created} days.

Campaign: {campaign.title}
Reminders sent: {campaign.reminder_count}
Items still pending ({pending_items.count()}):
{item_list}

You should follow up directly.
View: {site_url}/clients/{campaign.client.id}/

Mortacc Auto-Chasing""",
                        from_email='support@mortacc.com',
                        recipient_list=[email],
                        fail_silently=True,
                    )
                except Exception:
                    pass
            escalated += 1
            continue

        # Send reminder on days 1, 3, 7, 10, 14
        reminder_days = [1, 3, 7, 10, 14]
        should_send = days_since_created in reminder_days
        last_sent_date = campaign.last_reminder_sent.date() if campaign.last_reminder_sent else None

        if should_send and last_sent_date != today:
            pending_items = campaign.items.filter(status='pending')
            if not pending_items.exists():
                # All items received — auto-complete
                campaign.status = 'completed'
                campaign.completed_at = timezone.now()
                campaign.save()
                continue

            item_list = '\n'.join([f'  {i+1}. {item.description}' for i, item in enumerate(pending_items[:10])])
            if pending_items.count() > 10:
                item_list += f'\n  ...and {pending_items.count() - 10} more items'

            urgency = 'friendly' if days_since_created <= 3 else 'important' if days_since_created <= 7 else 'urgent'
            urgency_lines = {
                'friendly': 'Just a quick reminder about the items below. Please upload them at your earliest convenience.',
                'important': 'We still need the following items from you. Your file cannot proceed without them.',
                'urgent': 'URGENT: These items are now overdue. Please provide them immediately to avoid delays in your file.',
            }

            try:
                send_mail(
                    subject=f'[Mortacc] {campaign.client.name} — {urgency.title()} Reminder: {campaign.title}',
                    message=f"""Hi {campaign.client.name},

{urgency_lines[urgency]}

Requested items:
{item_list}

Upload here: {site_url}/onboarding/{campaign.client.onboarding_token if campaign.client.onboarding_token else '#'}/

If you have questions, reply to this email.

Mortacc Auto-Chasing""",
                    from_email='support@mortacc.com',
                    recipient_list=[campaign.client.email],
                    fail_silently=True,
                )
                campaign.reminder_count += 1
                campaign.last_reminder_sent = timezone.now()
                campaign.save()
                sent += 1
            except Exception as e:
                logger.error('Failed to send chasing reminder: %s', e)

    if sent or escalated:
        logger.info('Chasing: %d reminder(s) sent, %d escalated', sent, escalated)
    return sent, escalated
