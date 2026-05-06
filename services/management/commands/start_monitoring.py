from django.core.management.base import BaseCommand
from services.views import start_monitoring_thread

class Command(BaseCommand):
    help = 'Start monitoring thread'

    def handle(self, *args, **options):
        start_monitoring_thread()
        self.stdout.write(self.style.SUCCESS('Monitoring thread started'))