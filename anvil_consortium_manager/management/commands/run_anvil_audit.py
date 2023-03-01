from django.core.management.base import BaseCommand


class Command(BaseCommand):

    help = """Management command to run an AnVIL audit."""

    def handle(self, *args, **options):
        self.stdout.write("Done!")
