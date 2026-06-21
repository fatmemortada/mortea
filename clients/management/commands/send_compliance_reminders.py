"""
Management command to send compliance task reminder emails.

Run manually:
    python manage.py send_compliance_reminders

On Fly.io (daily cron):
    fly ssh console --app mortacc
    python manage.py send_compliance_reminders

Sends reminders to accountants for tasks due in:
    - 30 days
    - 14 days
    -  7 days

Safe to run daily — each threshold is only sent once per task.
"""

from django.core.management.base import BaseCommand
from clients.emails import send_compliance_reminders


class Command(BaseCommand):
    help = "Send compliance task reminder emails (30d, 14d, 7d thresholds)"

    def handle(self, *args, **options):
        self.stdout.write("Running compliance reminder check...")
        count = send_compliance_reminders()
        self.stdout.write(
            self.style.SUCCESS(f"Done. {count} reminder(s) sent.")
        )
