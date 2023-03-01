from django.core.management.base import BaseCommand

from ... import models


class Command(BaseCommand):

    help = """Management command to run an AnVIL audit."""

    def handle(self, *args, **options):
        print("running!")
