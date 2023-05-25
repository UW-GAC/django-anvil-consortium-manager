"""Tests for management commands in `anvil_consortium_manager`."""

import pprint
from io import StringIO
from unittest import skip

import responses
from django.contrib.sites.models import Site
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from .. import anvil_audit, models
from . import factories
from .utils import AnVILAPIMockTestMixin


class RunAnvilAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the run_anvil_audit command"""

    def get_api_url_billing_project(self, billing_project_name):
        return (
            self.api_client.rawls_entry_point
            + "/api/billing/v2/"
            + billing_project_name
        )

    def test_command_output_invalid_model(self):
        """Appropriate error is returned when an invalid model is specified."""
        out = StringIO()
        with self.assertRaises(CommandError) as e:
            # Call with the "--models=foo" so it goes through the argparse validation.
            # Calling with models=["foo"] does not throw an exception.
            call_command("run_anvil_audit", "--models=foo", stdout=out)
        self.assertIn("invalid choice", str(e.exception))

    def test_command_output_no_model_specified(self):
        """Runs on all models if no models are specified."""
        # Add API call responses.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1",
            status=200,
            json=[],
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces",
            status=200,
            json=[],
        )
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", stdout=out)
        self.assertIn("BillingProject... ok!", out.getvalue())
        self.assertIn("Account... ok!", out.getvalue())
        self.assertIn("ManagedGroup... ok!", out.getvalue())
        self.assertIn("Workspace... ok!", out.getvalue())

    def test_command_output_multiple_models(self):
        """Can audit multiple models at the same time."""
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            models=["BillingProject", "Account"],
            stdout=out,
        )
        self.assertIn("BillingProject... ok!", out.getvalue())
        self.assertIn("Account... ok!", out.getvalue())

    def test_command_output_billing_project_no_instances(self):
        """Test command output."""
        out = StringIO()
        call_command(
            "run_anvil_audit", "--no-color", models=["BillingProject"], stdout=out
        )
        self.assertIn("BillingProject... ok!", out.getvalue())

    def test_command_output_account_no_instances(self):
        """Test command output."""
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", models=["Account"], stdout=out)
        self.assertIn("Account... ok!", out.getvalue())

    def test_command_output_managed_group_no_instances(self):
        """Test command output."""
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1",
            status=200,
            json=[],
        )
        out = StringIO()
        call_command(
            "run_anvil_audit", "--no-color", models=["ManagedGroup"], stdout=out
        )
        self.assertIn("ManagedGroup... ok!", out.getvalue())

    def test_command_output_workspace_no_instances(self):
        """Test command output."""
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces",
            status=200,
            json=[],
        )
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", models=["Workspace"], stdout=out)
        self.assertIn("Workspace... ok!", out.getvalue())

    def test_command_run_audit_one_instance_ok(self):
        """Test command output."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(responses.GET, api_url, status=200)
        out = StringIO()
        call_command(
            "run_anvil_audit", "--no-color", models=["BillingProject"], stdout=out
        )
        self.assertIn("BillingProject... ok!", out.getvalue())
        self.assertNotIn("errors", out.getvalue())
        self.assertNotIn("not_in_app", out.getvalue())

    def test_command_run_audit_ok_email(self):
        """Test command output."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(responses.GET, api_url, status=200)
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            models=["BillingProject"],
            email="test@example.com",
            stdout=out,
        )
        self.assertIn("BillingProject... ok!", out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertIn("ok", email.subject)
        # Text body.
        audit_results = models.BillingProject.anvil_audit()
        self.assertEqual(pprint.pformat(audit_results.export()), email.body)
        # HTML body.
        self.assertEqual(len(email.alternatives), 1)

    def test_command_run_audit_ok_email_errors_only(self):
        """Test command output when email and errors_only is set."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(responses.GET, api_url, status=200)
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            models=["BillingProject"],
            email="test@example.com",
            errors_only=True,
            stdout=out,
        )
        self.assertIn("BillingProject... ok!", out.getvalue())
        # No message has been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_command_run_audit_not_ok(self):
        """Test command output when BillingProject audit is not ok."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET, api_url, status=404, json={"message": "error"}
        )
        out = StringIO()
        call_command(
            "run_anvil_audit", "--no-color", models=["BillingProject"], stdout=out
        )
        self.assertIn("BillingProject... problems found.", out.getvalue())
        self.assertIn("""'errors':""", out.getvalue())
        self.assertIn(
            anvil_audit.BillingProjectAuditResults.ERROR_NOT_IN_ANVIL, out.getvalue()
        )

    def test_command_run_audit_not_ok_email(self):
        """Test command output when BillingProject audit is not ok with email specified."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET, api_url, status=404, json={"message": "error"}
        )
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            models=["BillingProject"],
            email="test@example.com",
            stdout=out,
        )
        self.assertIn("BillingProject... problems found.", out.getvalue())
        # Not printed to stdout.
        self.assertIn("""'errors':""", out.getvalue())
        # One message has been sent.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertIn("errors", email.subject)
        # Text body.
        audit_results = models.BillingProject.anvil_audit()
        self.assertEqual(pprint.pformat(audit_results.export()), email.body)
        # HTML body.
        self.assertEqual(len(email.alternatives), 1)

    def test_command_run_audit_not_ok_email_has_html_link(self):
        """Test command output when BillingProject audit is not ok with email specified."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET, api_url, status=404, json={"message": "error"}
        )
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            models=["BillingProject"],
            email="test@example.com",
            stdout=out,
        )
        email = mail.outbox[0]
        self.assertEqual(len(email.alternatives), 1)
        html_fragment = """<a href="https://example.com{url}">{obj}</a>""".format(
            obj=str(billing_project), url=billing_project.get_absolute_url()
        )
        self.assertInHTML(html_fragment, email.alternatives[0][0])

    @override_settings(SITE_ID=2)
    def test_command_run_audit_not_ok_email_has_html_link_different_domain(self):
        """Test command output when BillingProject audit is not ok with email specified."""
        site = Site.objects.create(domain="foobar.com", name="test")
        site.save()
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET, api_url, status=404, json={"message": "error"}
        )
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            models=["BillingProject"],
            email="test@example.com",
            stdout=out,
        )
        email = mail.outbox[0]
        self.assertEqual(len(email.alternatives), 1)
        html_fragment = """<a href="https://foobar.com{url}">{obj}</a>""".format(
            obj=str(billing_project), url=billing_project.get_absolute_url()
        )
        self.assertInHTML(html_fragment, email.alternatives[0][0])

    def test_command_run_audit_api_error(self):
        """Test command output when BillingProject audit is not ok."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET, api_url, status=500, json={"message": "error"}
        )
        out = StringIO()
        call_command(
            "run_anvil_audit", "--no-color", models=["BillingProject"], stdout=out
        )
        self.assertIn("BillingProject... API error.", out.getvalue())

    # This test is complicated so skipping for now.
    # When trying to change the settings, the test attempts to repopulate the
    # workspace registry. This then causes an error. Skip it until we figure out
    # how best to handle this situation.
    @skip
    def test_command_without_sites(self):
        """Test command behavior without the Sites framework enabled."""
        out = StringIO()
        with self.modify_settings(INSTALLED_APPS={"remove": ["django.contrib.sites"]}):
            #            with self.assertRaises(ImproperlyConfigured):
            call_command(
                "run_anvil_audit",
                "--no-color",
                models=["BillingProject"],
                email="test@example.com",
                stdout=out,
            )
