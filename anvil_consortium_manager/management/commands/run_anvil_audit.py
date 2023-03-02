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
        email_group = parser.add_argument_group(title="Email reports")
        email_group.add_argument(
            "--email",
            help="""Email to which to send a report instead of printing to stdout.
            One email per model audited will be sent.""",
        )
        email_group.add_argument(
            "--errors-only",
            action="store_true",
            help="Only send email report when errors are found.",
        )
        parser.add_argument(
            "--models",
            nargs="*",
            type=str,
            choices=["BillingProject", "Account", "ManagedGroup", "Workspace"],
            help="If specified, run audit on a subset of models. Otherwise, the audit will be run on all models.",
        )

    def _run_audit(self, model, **options):
        """Run the audit for a specific model class."""
        email = options["email"]
        errors_only = options["errors_only"]

        model_name = model._meta.verbose_name_plural

        self.stdout.write("Running on {}... ".format(model_name), ending="")
        try:
            # Assume the method is called anvil_audit.
            results = model.anvil_audit()
        except AnVILAPIError:
            self.stdout.write("API error.")
        else:
            if not results.ok():
                self.stdout.write("problems found.")
                report = json.dumps(results.to_json(include_verified=False), indent=2)
                if email:
                    send_mail(
                        "AnVIL Audit for {} -- errors".format(model_name),
                        report,
                        None,
                        [email],
                        fail_silently=False,
                    )
                else:
                    self.stdout.write(report)
            else:
                self.stdout.write("ok!")
                if email and not errors_only:
                    send_mail(
                        "AnVIL Audit for {} -- ok".format(model_name),
                        "Audit ok ({} instances)".format(len(results.get_verified())),
                        None,
                        [email],
                        fail_silently=False,
                    )

    def handle(self, *args, **options):

        if options["models"]:
            models_to_audit = options["models"]
        else:
            models_to_audit = ["BillingProject", "Account", "ManagedGroup", "Workspace"]

        if "BillingProject" in models_to_audit:
            self._run_audit(models.BillingProject, **options)

        if "Account" in models_to_audit:
            self._run_audit(models.Account, **options)

        if "ManagedGroup" in models_to_audit:
            self._run_audit(models.ManagedGroup, **options)

        if "Workspace" in models_to_audit:
            self._run_audit(models.Workspace, **options)
