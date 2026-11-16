from django.core.management.base import BaseCommand

from common.publish import publish_all


class Command(BaseCommand):
    help = "Write every site's configuration to Redis and remove what's left of deleted ones (after a deploy or a Redis loss)."

    def handle(self, *args, **options):
        count = publish_all()
        self.stdout.write(self.style.SUCCESS(f"Published {count} site(s)."))
