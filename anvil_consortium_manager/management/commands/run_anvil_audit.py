import json

from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from ... import models
from ...anvil_api import AnVILAPIError

# TODO:
# - Add auditing for different models.
# - Modify model command arg to run on multiple models.
# - Add syntax coloring to output
# - Add reporting level - only if errors found or upon any successful run


class Command(BaseCommand):

    help = """Management command to run an AnVIL audit."""

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            required=False,
            help="Email to which to send a report instead of printing to stdout.",
        )
        parser.add_argument(
            "--errors-only",
            action="store_true",
            help="Only send a report when errors are found.",
        )
        parser.add_argument("models", nargs=1, type=str)

    def handle(self, *args, **options):

        models_to_audit = options["models"]

        email = options["email"]

        # Billing projects.
        if "BillingProject" in models_to_audit:
            self.stdout.write("Running on BillingProjects... ", ending="")
            try:
                results = models.BillingProject.anvil_audit()
            except AnVILAPIError:
                self.stdout.write("API error.")
            else:
                if not results.ok():
                    self.stdout.write("problems found.")
                    report = json.dumps(
                        results.to_json(include_verified=False), indent=2
                    )
                    if email:
                        send_mail(
                            "AnVIL Audit for BillingProjects -- errors",
                            report,
                            None,
                            [email],
                            fail_silently=False,
                        )
                    else:
                        self.stdout.write(report)
                else:
                    if email and not options["errors_only"]:
                        send_mail(
                            "AnVIL Audit for BillingProjects -- ok",
                            "Audit ok",
                            None,
                            [email],
                            fail_silently=False,
                        )
                    self.stdout.write("ok!")
