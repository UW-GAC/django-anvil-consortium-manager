"""Tests for management commands in `anvil_consortium_manager`."""

from io import StringIO

import responses
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase

from .. import anvil_audit
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
        call_command("run_anvil_audit", stdout=out)
        self.assertIn("billing projects... ok!", out.getvalue())
        self.assertIn("accounts... ok!", out.getvalue())
        self.assertIn("managed groups... ok!", out.getvalue())
        self.assertIn("workspaces... ok!", out.getvalue())

    def test_command_output_multiple_models(self):
        """Can audit multiple models at the same time."""
        out = StringIO()
        call_command(
            "run_anvil_audit", models=["BillingProject", "Account"], stdout=out
        )
        self.assertIn("billing projects... ok!", out.getvalue())
        self.assertIn("accounts... ok!", out.getvalue())

    def test_command_output_billing_project_no_instances(self):
        """Test command output."""
        out = StringIO()
        call_command("run_anvil_audit", models=["BillingProject"], stdout=out)
        self.assertIn("billing projects... ok!", out.getvalue())

    def test_command_output_account_no_instances(self):
        """Test command output."""
        out = StringIO()
        call_command("run_anvil_audit", models=["Account"], stdout=out)
        self.assertIn("accounts... ok!", out.getvalue())

    def test_command_output_managed_group_no_instances(self):
        """Test command output."""
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1",
            status=200,
            json=[],
        )
        out = StringIO()
        call_command("run_anvil_audit", models=["ManagedGroup"], stdout=out)
        self.assertIn("managed groups... ok!", out.getvalue())

    def test_command_output_workspace_no_instances(self):
        """Test command output."""
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces",
            status=200,
            json=[],
        )
        out = StringIO()
        call_command("run_anvil_audit", models=["Workspace"], stdout=out)
        self.assertIn("workspaces... ok!", out.getvalue())

    def test_command_run_audit_one_instance_ok(self):
        """Test command output."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(responses.GET, api_url, status=200)
        out = StringIO()
        call_command("run_anvil_audit", models=["BillingProject"], stdout=out)
        self.assertIn("billing projects... ok!", out.getvalue())
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
            models=["BillingProject"],
            email="test@example.com",
            stdout=out,
        )
        self.assertIn("billing projects... ok!", out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("ok", mail.outbox[0].subject)

    def test_command_run_audit_ok_email_errors_only(self):
        """Test command output when email and errors_only is set."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(responses.GET, api_url, status=200)
        out = StringIO()
        call_command(
            "run_anvil_audit",
            models=["BillingProject"],
            email="test@example.com",
            errors_only=True,
            stdout=out,
        )
        self.assertIn("billing projects... ok!", out.getvalue())
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
        call_command("run_anvil_audit", models=["BillingProject"], stdout=out)
        self.assertIn("billing projects... problems found.", out.getvalue())
        self.assertIn(""""errors":""", out.getvalue())
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
            models=["BillingProject"],
            email="test@example.com",
            stdout=out,
        )
        self.assertIn("billing projects... problems found.", out.getvalue())
        # Not printed to stdout.
        self.assertNotIn(""""errors":""", out.getvalue())
        # One message has been sent.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["test@example.com"])
        self.assertIn("errors", mail.outbox[0].subject)
        # Instead in the email body:
        self.assertIn(""""errors":""", mail.outbox[0].body)
        self.assertIn(
            anvil_audit.BillingProjectAuditResults.ERROR_NOT_IN_ANVIL,
            mail.outbox[0].body,
        )

    def test_command_run_audit_api_error(self):
        """Test command output when BillingProject audit is not ok."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET, api_url, status=500, json={"message": "error"}
        )
        out = StringIO()
        call_command("run_anvil_audit", models=["BillingProject"], stdout=out)
        self.assertIn("billing projects... API error.", out.getvalue())
