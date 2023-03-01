import json

from django.core.management.base import BaseCommand

from ... import models
from ...anvil_api import AnVILAPIError


class Command(BaseCommand):

    help = """Management command to run an AnVIL audit."""

    def add_arguments(self, parser):
        parser.add_argument("models", nargs=1, type=str)

    def handle(self, *args, **options):

        models_to_audit = options["models"]

        # Billing projects.
        if "BillingProject" in models_to_audit:
            self.stdout.write("Running on BillingProjects...", ending="")
            try:
                results = models.BillingProject.anvil_audit()
            except AnVILAPIError:
                self.stdout.write(" API error.")
            else:
                if not results.ok():
                    self.stdout.write("")
                    report = json.dumps(
                        results.to_json(include_verified=False), indent=2
                    )
                    self.stdout.write(report)
                else:
                    self.stdout.write(" ok!")
