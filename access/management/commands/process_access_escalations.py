from django.core.management.base import BaseCommand

from access.views import process_escalations


class Command(BaseCommand):
    help = "Escalate pending patient access requests whose response window has expired."

    def handle(self, *args, **options):
        created, contacts = process_escalations()
        self.stdout.write(self.style.SUCCESS(f"Processed escalations: {created} created; {contacts} emergency contacts queued for notification."))
