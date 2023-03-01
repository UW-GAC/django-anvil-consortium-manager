"""Tests for management commands in `anvil_consortium_manager`."""

from io import StringIO

import responses
from django.core.management import call_command
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

    def test_command_output_no_instances(self):
        """Test command output."""
        out = StringIO()
        call_command("run_anvil_audit", "BillingProject", stdout=out)
        self.assertIn("BillingProjects... ok!", out.getvalue())

    def test_command_output_with_billing_project_ok(self):
        """Test command output."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(responses.GET, api_url, status=200)
        out = StringIO()
        call_command("run_anvil_audit", "BillingProject", stdout=out)
        self.assertIn("BillingProjects... ok!", out.getvalue())
        self.assertNotIn("errors", out.getvalue())
        self.assertNotIn("not_in_app", out.getvalue())

    def test_command_output_with_billing_project_not_ok(self):
        """Test command output when BillingProject audit is not ok."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET, api_url, status=404, json={"message": "error"}
        )
        out = StringIO()
        call_command("run_anvil_audit", "BillingProject", stdout=out)
        self.assertIn("BillingProjects", out.getvalue())
        self.assertIn(""""errors":""", out.getvalue())
        self.assertIn(
            anvil_audit.BillingProjectAuditResults.ERROR_NOT_IN_ANVIL, out.getvalue()
        )

    def test_command_output_with_billing_project_api_error(self):
        """Test command output when BillingProject audit is not ok."""
        billing_project = factories.BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET, api_url, status=500, json={"message": "error"}
        )
        out = StringIO()
        call_command("run_anvil_audit", "BillingProject", stdout=out)
        self.assertIn("BillingProjects... API error.", out.getvalue())
