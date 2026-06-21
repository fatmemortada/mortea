from django.core.management.base import BaseCommand
from clients.models import Client, Firm

class Command(BaseCommand):
    help = 'Add a test client for demo purposes'

    def handle(self, *args, **options):
        firm = Firm.objects.first()
        if not firm:
            firm = Firm.objects.create(name='Demo Firm', code='DEM')
        client = Client.objects.create(
            firm=firm,
            name='Acme Corp Inc.',
            email='acme@example.com',
            phone='416-555-1000',
            client_type='business',
            business_type='Holding Company',
            status='not_started',
            language='english',
        )
        self.stdout.write(self.style.SUCCESS(f'Created client: {client.name} (ID: {client.id})'))
