import json

import django_tables2 as tables
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from ... import models
from ...anvil_api import AnVILAPIError


class ErrorsTable(tables.Table):
    id = tables.Column(orderable=False)
    instance = tables.Column(orderable=False)
    errors = tables.ManyToManyColumn(orderable=False)


class NotInAppTable(tables.Table):
    instance = tables.Column(orderable=False)


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
            self.stdout.write(self.style.ERROR("API error."))
        else:
            if not results.ok():
                self.stdout.write(self.style.ERROR("problems found."))
                json_results = results.to_json(include_verified=False)
                report = json.dumps(json_results, indent=2)
                if email:
                    # trying json2html
                    # table_attributes = table_attributes="class=\"table\""
                    # html_body = render_to_string(
                    #     "anvil_consortium_manager/email_audit_report.html",
                    #     context={
                    #         "model": model._meta.object_name,
                    #         "errors_table": json2html.convert(json_results["errors"]),
                    #         "not_in_app_table": json2html.convert(json_results["not_in_app"])
                    #     }
                    # )
                    # import ipdb; ipdb.set_trace()
                    # trying django-tables2 and failing
                    html_body = render_to_string(
                        "anvil_consortium_manager/email_audit_report.html",
                        context={
                            "errors_table": ErrorsTable(json_results["errors"]),
                            "not_in_app_table": NotInAppTable(
                                json_results["not_in_app"]
                            ),
                        },
                    )
                    # import ipdb; ipdb.set_trace()
                    send_mail(
                        "AnVIL Audit for {} -- errors".format(model_name),
                        report,
                        None,
                        [email],
                        fail_silently=False,
                        html_message=html_body,
                    )
                else:
                    self.stdout.write(report)
            else:
                self.stdout.write(self.style.SUCCESS("ok!"))
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
