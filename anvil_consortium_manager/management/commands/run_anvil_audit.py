import json

from django.core.management.base import BaseCommand

from ... import models


class Command(BaseCommand):

    help = """Management command to run an AnVIL audit."""

    def add_arguments(self, parser):
        parser.add_argument("models", nargs=1, type=str)

    def handle(self, *args, **options):

        models_to_audit = options["models"]

        # Billing projects.
        if "BillingProject" in models_to_audit:
            self.stdout.write("Running on BillingProjects...")
            billing_project_results = models.BillingProject.anvil_audit()
            report = json.dumps(
                billing_project_results.to_json(include_verified=False), indent=2
            )
            self.stdout.write(report)

        self.stdout.write("Done!")
