"""
AI Billable Time Reconstruction.

Analyzes platform activity and auto-generates time entries
with client-ready narratives. Recovers 10-30% more billable hours.
"""
import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
from django.db.models import Sum, Count

from ..models import (
    Client, TimeEntry, UnbilledActivity, Invoice, BillingRate,
    ActivityLog, log_activity,
)
from ._helpers import _get_firm


@login_required
def ai_time_reconstruction(request):
    """AI-powered billable time reconstruction dashboard."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    # Get all unconverted activities
    activities = UnbilledActivity.objects.filter(
        client__firm=firm, is_converted=False
    ).select_related('client', 'user').order_by('-occurred_at')

    total_estimated_hours = sum(a.estimated_minutes for a in activities) / 60
    total_estimated_value = sum(
        (a.estimated_minutes / 60) * float(a.suggested_rate or 0)
        for a in activities
    )

    # Group by client
    by_client = {}
    for a in activities:
        cid = a.client_id
        if cid not in by_client:
            by_client[cid] = {
                'client': a.client,
                'activities': [],
                'total_minutes': 0,
                'estimated_value': 0,
            }
        by_client[cid]['activities'].append(a)
        by_client[cid]['total_minutes'] += a.estimated_minutes
        by_client[cid]['estimated_value'] += (a.estimated_minutes / 60) * float(a.suggested_rate or 0)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'reconstruct_all':
            # Convert all activities to time entries
            converted = 0
            for a in activities:
                entry = a.convert_to_time_entry()
                if entry:
                    converted += 1
            messages.success(request, f'Converted {converted} activities to billable time entries!')
            return redirect('time_tracking')

        elif action == 'reconstruct_client':
            client_id = request.POST.get('client_id')
            client_activities = activities.filter(client_id=client_id)
            converted = 0
            for a in client_activities:
                entry = a.convert_to_time_entry()
                if entry:
                    converted += 1
            messages.success(request, f'Converted {converted} activities for billing.')
            return redirect('time_tracking')

        elif action == 'scan_activity':
            # Scan recent activity and create unbilled activities
            count = _scan_platform_activity(firm, request.user)
            messages.success(request, f'Found {count} potentially billable activities.')

        elif action == 'generate_invoice':
            client_id = request.POST.get('client_id')
            entries = TimeEntry.objects.filter(
                client_id=client_id, client__firm=firm, billing_status='unbilled'
            )
            if entries.exists():
                from .billing import _generate_invoice_from_time_entries
                client = Client.objects.filter(id=client_id, firm=firm).first()
                if not client:
                    return redirect('ai_time')
                inv = _generate_invoice_from_time_entries(client, entries, status='sent', send_payment_link=True)
                messages.success(request, f'Invoice generated from {entries.count()} time entries.')

        return redirect('ai_time')

    return render(request, 'clients/ai_time_reconstruction.html', {
        'firm': firm,
        'activities': activities,
        'total_estimated_hours': round(total_estimated_hours, 1),
        'total_estimated_value': round(total_estimated_value, 2),
        'by_client': list(by_client.values()),
        'today': date.today(),
    })


def _scan_platform_activity(firm, user):
    """Scan recent platform activity and create UnbilledActivity records."""
    from django.contrib.auth.models import User

    created = 0
    today = timezone.now()
    week_ago = today - timedelta(days=7)

    # Get default billing rate for the user
    default_rate = BillingRate.objects.filter(
        firm=firm, is_default=True
    ).first()
    hourly_rate = float(default_rate.hourly_rate) if default_rate else 250.0

    # Scan activity logs for potentially billable events
    logs = ActivityLog.objects.filter(
        firm=firm, timestamp__gte=week_ago
    ).select_related('client').order_by('-timestamp')

    for log_entry in logs:
        if not log_entry.client:
            continue

        # Determine activity type and estimated time
        activity_type = _classify_activity(log_entry.action, log_entry.description or '')
        if not activity_type:
            continue

        estimated_minutes = _estimate_minutes(activity_type, log_entry.description or '')

        # Avoid duplicates
        if UnbilledActivity.objects.filter(
            client=log_entry.client,
            activity_type=activity_type,
            description=log_entry.description or '',
            occurred_at__date=log_entry.timestamp.date(),
        ).exists():
            continue

        UnbilledActivity.objects.create(
            client=log_entry.client,
            user=log_entry.user,
            activity_type=activity_type,
            description=log_entry.description or f'{activity_type} activity',
            occurred_at=log_entry.timestamp,
            estimated_minutes=estimated_minutes,
            suggested_rate=hourly_rate,
        )
        created += 1

    return created


def _classify_activity(action, description):
    """Classify an activity log action into an unbilled activity type."""
    mapping = {
        'create': {
            'AIExtraction': 'ai_draft_performed',
            'Document': 'document_generated',
        },
        'update': {
            'ComplianceTask': 'compliance_task_completed',
        },
    }
    # Simple keyword matching
    desc_lower = description.lower()
    if 'document' in desc_lower and ('generat' in desc_lower or 'creat' in desc_lower):
        return 'document_generated'
    if 'compliance' in desc_lower or 'task' in desc_lower:
        return 'compliance_task_completed'
    if 'email' in desc_lower or 'sent' in desc_lower:
        return 'email_sent'
    if 'filing' in desc_lower or 'filed' in desc_lower:
        return 'filing_submitted'
    if 'template' in desc_lower:
        return 'template_filled'
    if 'incorporation' in desc_lower:
        return 'document_generated'
    return None


def _estimate_minutes(activity_type, description):
    """Estimate billable minutes for an activity type."""
    estimates = {
        'document_generated': 30,
        'compliance_task_completed': 15,
        'email_sent': 10,
        'filing_submitted': 20,
        'template_filled': 15,
        'ai_draft_performed': 45,
        'review_completed': 20,
        'call_logged': 15,
        'meeting_held': 30,
    }
    return estimates.get(activity_type, 15)
