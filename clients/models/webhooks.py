"""Webhook system for third-party integrations."""
from django.db import models
from .client import Firm


class WebhookEndpoint(models.Model):
    """A registered webhook URL that receives event notifications."""
    EVENT_CHOICES = [
        ('client.created', 'Client Created'),
        ('client.updated', 'Client Updated'),
        ('client.deleted', 'Client Deleted'),
        ('task.completed', 'Compliance Task Completed'),
        ('task.overdue', 'Compliance Task Overdue'),
        ('document.uploaded', 'Document Uploaded'),
        ('document.approved', 'Document Approved'),
        ('invoice.paid', 'Invoice Paid'),
        ('invoice.sent', 'Invoice Sent'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='webhooks')
    url = models.URLField(max_length=500)
    events = models.JSONField(default=list, help_text='List of event types to subscribe to')
    secret = models.CharField(max_length=64, blank=True, help_text='Optional secret for HMAC signature verification')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    failure_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.firm.code} → {self.url}"


def trigger_webhook(event_type, firm, payload, async_delivery=True):
    """
    Fire webhooks for a given event. Call from views after significant actions.

    When async_delivery=True (default), dispatches via Huey background task
    so slow/unreachable endpoints don't block the user's request.
    """
    endpoints = WebhookEndpoint.objects.filter(
        firm=firm, is_active=True,
    )
    for ep in endpoints:
        if event_type not in (ep.events or []):
            continue

        if async_delivery:
            try:
                from clients.tasks import deliver_webhook
                deliver_webhook(ep.id, payload, event_type)
            except Exception:
                # Fallback to synchronous delivery if Huey is unavailable
                _deliver_webhook_sync(ep, payload)
        else:
            _deliver_webhook_sync(ep, payload)


def _deliver_webhook_sync(ep, payload):
    """Synchronous webhook delivery (fallback)."""
    import requests
    import json
    import hmac
    import hashlib
    from django.utils import timezone

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
    except Exception:
        ep.failure_count += 1
        if ep.failure_count >= 10:
            ep.is_active = False
        ep.save()
