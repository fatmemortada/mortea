"""
Management command to seed default entity subscription plans.
Run: python manage.py seed_subscription_plans
"""
from django.core.management.base import BaseCommand
from clients.models.subscription import seed_default_plans


class Command(BaseCommand):
    help = 'Create default entity subscription plans (Basic, Standard, Premium, Enterprise)'

    def handle(self, *args, **options):
        count = seed_default_plans()
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f'Created {count} new subscription plan(s).'))
        else:
            self.stdout.write(self.style.SUCCESS('All default subscription plans already exist.'))
