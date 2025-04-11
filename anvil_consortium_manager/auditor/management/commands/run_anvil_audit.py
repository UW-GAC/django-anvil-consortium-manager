import logging
import pprint

import django_tables2 as tables
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string

from anvil_consortium_manager.anvil_api import AnVILAPIError

from ... import models
from ...audit import accounts as account_audit
from ...audit import base as base_audit
from ...audit import billing_projects as billing_project_audit
from ...audit import managed_groups as managed_group_audit
from ...audit import workspaces as workspace_audit

logger = logging.getLogger(__name__)


class ErrorTableWithLink(base_audit.ErrorTable):
    model_instance = tables.Column(
        orderable=False,
        linkify=lambda value, table: "https://{domain}{url}".format(
            domain=table.site.domain, url=value.get_absolute_url()
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the site here so it only hits the db once.
        self.site = Site.objects.get_current()


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

    def _run_audit(self, audit_results, ignore_model=None, **options):
        """Run the audit for a specific model class."""
        email = options["email"]
        errors_only = options["errors_only"]

        # Track the number of ignored records.
        n_ignored = 0

        audit_name = audit_results.__class__.__name__
        self.stdout.write("Running on {}... ".format(audit_name), ending="")
        try:
            # Assume the method is called anvil_audit.
            audit_results.run_audit()
        except AnVILAPIError as e:
            api_error_msg = str(e)
            logger.exception(f"[run_anvil_audit] Encountered api error {api_error_msg}")
            raise CommandError(f"API error: {api_error_msg}")

        else:
            if not audit_results.ok():
                self.stdout.write(self.style.ERROR("problems found."))
                self.stdout.write(pprint.pformat(audit_results.export(include_verified=False)))
            else:
                msg = "ok!"
                if ignore_model:
                    n_ignored = ignore_model.objects.all().count()
                    if n_ignored:
                        msg += " (ignoring {n_ignored} records)".format(n_ignored=n_ignored)
                self.stdout.write(self.style.SUCCESS(msg))

            if email and (not errors_only) or (errors_only and not audit_results.ok()):
                # Set up the email message.
                subject = "AnVIL audit {} -- {}".format(audit_name, "ok" if audit_results.ok() else "errors!")
                exported_results = audit_results.export()
                html_body = render_to_string(
                    "auditor/email_audit_report.html",
                    context={
                        "model_name": audit_name,
                        "audit_results": audit_results,
                        "n_ignored": n_ignored,
                        "errors_table": ErrorTableWithLink(audit_results.get_error_results()),
                        "not_in_app_table": base_audit.NotInAppTable(audit_results.get_not_in_app_results()),
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
            self._run_audit(billing_project_audit.BillingProjectAudit(), **options)

        if "Account" in models_to_audit:
            self._run_audit(account_audit.AccountAudit(), **options)

        if "ManagedGroup" in models_to_audit:
            self._run_audit(
                managed_group_audit.ManagedGroupAudit(), ignore_model=models.IgnoredManagedGroupMembership, **options
            )

        if "Workspace" in models_to_audit:
            self._run_audit(workspace_audit.WorkspaceAudit(), ignore_model=models.IgnoredWorkspaceSharing, **options)
