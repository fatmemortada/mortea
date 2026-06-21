"""Unified Notification Center views."""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import date, timedelta

from ..models import Notification, NotificationPreference, create_notification
from ._helpers import _get_firm


@login_required
def notification_center(request):
    """Unified notification center — all alerts in one place."""
    firm = _get_firm(request.user)
    if not firm:
        return redirect('login')

    notifications = Notification.objects.filter(
        firm=firm, user=request.user, is_archived=False
    ).order_by('-created_at')

    unread = notifications.filter(is_read=False)
    read = notifications.filter(is_read=True)
    critical = unread.filter(priority='critical')

    # Preferences
    pref, _ = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'mark_read':
            notif_id = request.POST.get('notif_id')
            Notification.objects.filter(id=notif_id, user=request.user).update(
                is_read=True, read_at=timezone.now()
            )
        elif action == 'mark_all_read':
            unread.update(is_read=True, read_at=timezone.now())
        elif action == 'archive':
            notif_id = request.POST.get('notif_id')
            Notification.objects.filter(id=notif_id, user=request.user).update(is_archived=True)
        elif action == 'clear_all':
            notifications.update(is_archived=True)
        elif action == 'save_preferences':
            pref.enable_in_app = request.POST.get('enable_in_app') == '1'
            pref.enable_email = request.POST.get('enable_email') == '1'
            pref.daily_digest = request.POST.get('daily_digest') == '1'
            pref.weekly_digest = request.POST.get('weekly_digest') == '1'
            pref.notify_compliance = request.POST.get('notify_compliance') == '1'
            pref.notify_billing = request.POST.get('notify_billing') == '1'
            pref.notify_document = request.POST.get('notify_document') == '1'
            pref.notify_client = request.POST.get('notify_client') == '1'
            pref.notify_subscription = request.POST.get('notify_subscription') == '1'
            pref.notify_risk = request.POST.get('notify_risk') == '1'
            pref.notify_collaboration = request.POST.get('notify_collaboration') == '1'
            pref.email_priority_threshold = request.POST.get('email_threshold', 'high')
            pref.quiet_hours_enabled = request.POST.get('quiet_hours') == '1'
            pref.save()
            messages.success(request, 'Notification preferences saved.')

        return redirect('notification_center')

    return render(request, 'clients/notification_center.html', {
        'firm': firm, 'notifications': notifications,
        'unread': unread, 'read': read, 'critical': critical, 'pref': pref,
    })


@login_required
def notification_api(request):
    """API endpoint for notification badge count (for header bell icon)."""
    firm = _get_firm(request.user)
    if not firm:
        return JsonResponse({'count': 0})

    count = Notification.objects.filter(
        firm=firm, user=request.user, is_read=False, is_archived=False
    ).count()

    latest = Notification.objects.filter(
        firm=firm, user=request.user, is_read=False, is_archived=False
    ).order_by('-created_at')[:5]

    return JsonResponse({
        'count': count,
        'latest': [{
            'id': n.id, 'title': n.title, 'category': n.category,
            'priority': n.priority, 'created': n.created_at.isoformat(),
            'link': n.link_url,
        } for n in latest],
    })


def send_bulk_notification(firm, users, title, message, category='announcement', priority='normal', link_url=''):
    """Send a notification to multiple users."""
    count = 0
    for user in users:
        create_notification(
            firm=firm, user=user, title=title, message=message,
            category=category, priority=priority, link_url=link_url, channel='both',
        )
        count += 1
    return count
