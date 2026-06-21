"""iCal feed for compliance deadlines — subscribe in Google Calendar / Outlook."""
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime, timedelta

from ..models import ComplianceTask
from ._helpers import _get_firm


@login_required
def compliance_ical_feed(request):
    """Return an iCal feed of the user's firm compliance deadlines."""
    firm = _get_firm(request.user)
    if not firm:
        return HttpResponse("Not authorized", status=403)

    tasks = ComplianceTask.objects.filter(
        client__firm=firm,
        status__in=['pending', 'in_progress'],
    ).select_related('client').order_by('due_date')

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Mortacc//Compliance Calendar//EN',
        'X-WR-CALNAME:Mortacc Compliance Deadlines',
        'X-WR-CALDESC:Compliance deadlines from Mortacc',
    ]

    for task in tasks:
        uid = f'mortacc-task-{task.id}@mortacc.com'
        created = task.created_at.strftime('%Y%m%dT%H%M%SZ') if task.created_at else datetime.now().strftime('%Y%m%dT%H%M%SZ')
        due = task.due_date.strftime('%Y%m%d')
        status_text = 'OVERDUE ' if task.is_overdue else ''
        title = f'{status_text}{task.client.name}: {task.title}'

        lines.extend([
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTAMP:{created}',
            f'DTSTART;VALUE=DATE:{due}',
            f'DTEND;VALUE=DATE:{due}',
            f'SUMMARY:{title}',
            f'DESCRIPTION:{task.description or task.get_task_type_display()}\\nClient: {task.client.name}\\nStatus: {task.get_status_display()}',
            'END:VEVENT',
        ])

    lines.append('END:VCALENDAR')
    ics = '\r\n'.join(lines)

    response = HttpResponse(ics, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="mortacc_compliance.ics"'
    return response
