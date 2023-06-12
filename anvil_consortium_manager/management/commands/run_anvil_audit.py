import pprint

import django_tables2 as tables
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from ... import models
from ...anvil_api import AnVILAPIError


class ErrorsTable(tables.Table):
    id = tables.Column(orderable=False)
    instance = tables.Column(
        orderable=False,
        linkify=lambda value, table: "https://{domain}{url}".format(
            domain=table.site.domain, url=value.get_absolute_url()
        ),
    )
    errors = tables.Column(orderable=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the site here so it only hits the db once.
        self.site = Site.objects.get_current()

    def render_errors(self, value):
        return ", ".join(value)


class NotInAppTable(tables.Table):
    instance = tables.Column(orderable=False, empty_values=())

    def render_instance(self, record):
        return record


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

        model_name = model._meta.object_name

        self.stdout.write("Running on {}... ".format(model_name), ending="")
        try:
            # Assume the method is called anvil_audit.
            results = model.anvil_audit()
        except AnVILAPIError:
            self.stdout.write(self.style.ERROR("API error."))
        else:
            if not results.ok():
                self.stdout.write(self.style.ERROR("problems found."))
                self.stdout.write(
                    pprint.pformat(results.export(include_verified=False))
                )
            else:
                self.stdout.write(self.style.SUCCESS("ok!"))

            if email and (not errors_only) or (errors_only and not results.ok()):
                # Set up the email message.
                subject = "AnVIL audit for {} -- {}".format(
                    model_name, "ok" if results.ok() else "errors!"
                )
                exported_results = results.export()
                html_body = render_to_string(
                    "anvil_consortium_manager/email_audit_report.html",
                    context={
                        "model_name": model_name,
                        "verified_results": exported_results["verified"],
                        "errors_table": ErrorsTable(exported_results["errors"]),
                        "not_in_app_table": NotInAppTable(
                            exported_results["not_in_app"]
                        ),
                    },
                )
                send_mail(
                    subject,
                    pprint.pformat(exported_results),
                    None,
                    [email],
                    fail_silently=False,
                    html_message=html_body,
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
