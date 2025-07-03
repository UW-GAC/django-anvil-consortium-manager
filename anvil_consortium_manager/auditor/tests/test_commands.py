"""Tests for management commands in `anvil_consortium_manager.auditor`."""

import pprint
from io import StringIO
from unittest import skip

import responses
from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import caches
from django.core.management import CommandError, call_command
from django.test import TestCase

from anvil_consortium_manager.tests.api_factories import (
    GetGroupMembershipAdminResponseFactory,
    GetGroupMembershipResponseFactory,
    GetGroupsResponseFactory,
    GroupDetailsAdminFactory,
)
from anvil_consortium_manager.tests.factories import AccountFactory, BillingProjectFactory
from anvil_consortium_manager.tests.utils import AnVILAPIMockTestMixin

from ... import app_settings
from ..audit import accounts, base, billing_projects, managed_groups
from ..management.commands.run_anvil_audit import ErrorTableWithLink
from . import factories


class RunAnvilAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the run_anvil_audit command"""

    def get_api_url_billing_project(self, billing_project_name):
        return self.api_client.rawls_entry_point + "/api/billing/v2/" + billing_project_name

    def get_api_workspace_json(self, billing_project_name, workspace_name, access, auth_domains=[]):
        """Return the json dictionary for a single workspace on AnVIL."""
        return {
            "accessLevel": access,
            "workspace": {
                "name": workspace_name,
                "namespace": billing_project_name,
                "authorizationDomain": [{"membersGroupName": x} for x in auth_domains],
                "isLocked": False,
            },
        }

    def get_api_workspace_acl_response(self):
        """Return a json for the workspace/acl method where no one else can access."""
        return {
            "acl": {
                self.service_account_email: {
                    "accessLevel": "OWNER",
                    "canCompute": True,
                    "canShare": True,
                    "pending": False,
                }
            }
        }

    def get_api_bucket_options_response(self):
        """Return a json for the workspace/acl method that is not requester pays."""
        return {"bucketOptions": {"requesterPays": False}}

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
        self.assertIn("BillingProjectAudit... ok!", out.getvalue())
        self.assertIn("AccountAudit... ok!", out.getvalue())
        self.assertIn("ManagedGroupAudit... ok!", out.getvalue())
        self.assertIn("WorkspaceAudit... ok!", out.getvalue())

    def test_command_output_multiple_models(self):
        """Can audit multiple models at the same time."""
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            models=["BillingProject", "Account"],
            stdout=out,
        )
        self.assertIn("BillingProjectAudit... ok!", out.getvalue())
        self.assertIn("AccountAudit... ok!", out.getvalue())

    def test_command_output_no_caching_by_default(self):
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            models=["BillingProject"],
            stdout=out,
        )
        self.assertIn("BillingProjectAudit... ok!", out.getvalue())
        self.assertIsNone(caches[app_settings.AUDIT_CACHE].get("billing_project_audit_results"))

    def test_command_output_caching(self):
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            "--cache-results",
            models=["BillingProject"],
            stdout=out,
        )
        self.assertIn("BillingProjectAudit... ok!", out.getvalue())
        cached_audit_results = caches[app_settings.AUDIT_CACHE].get("billing_project_audit_results")
        self.assertIsNotNone(cached_audit_results)
        self.assertIsInstance(cached_audit_results, billing_projects.BillingProjectAudit)

    def test_command_output_caching_multiple_models(self):
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            "--cache-results",
            models=["BillingProject", "Account"],
            stdout=out,
        )
        self.assertIn("BillingProjectAudit... ok!", out.getvalue())
        self.assertIn("AccountAudit... ok!", out.getvalue())
        cached_audit_results = caches[app_settings.AUDIT_CACHE].get("billing_project_audit_results")
        self.assertIsNotNone(cached_audit_results)
        self.assertIsInstance(cached_audit_results, billing_projects.BillingProjectAudit)
        cached_audit_results = caches[app_settings.AUDIT_CACHE].get("account_audit_results")
        self.assertIsNotNone(cached_audit_results)
        self.assertIsInstance(cached_audit_results, accounts.AccountAudit)

    def test_command_output_billing_project_no_instances(self):
        """Test command output."""
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", models=["BillingProject"], stdout=out)
        self.assertIn("BillingProjectAudit... ok!", out.getvalue())

    def test_command_output_account_no_instances(self):
        """Test command output."""
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", models=["Account"], stdout=out)
        self.assertIn("AccountAudit... ok!", out.getvalue())

    def test_command_output_managed_group_no_instances(self):
        """Test command output."""
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1",
            status=200,
            json=[],
        )
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", models=["ManagedGroup"], stdout=out)
        self.assertIn("ManagedGroupAudit... ok!", out.getvalue())

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
        self.assertIn("WorkspaceAudit... ok!", out.getvalue())

    def test_command_output_managed_groups_ignored_one_record(self):
        """Test command output."""
        factories.IgnoredManagedGroupMembershipFactory.create(group__name="test-group")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1",
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsAdminFactory(groupName="test-group")]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/member",
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/admin",
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", models=["ManagedGroup"], stdout=out)
        self.assertIn("ManagedGroupAudit... ok! (ignoring 1 records)", out.getvalue())

    def test_command_output_managed_groups_ignored_two_records(self):
        """Test command output."""
        factories.IgnoredManagedGroupMembershipFactory.create_batch(2, group__name="test-group")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1",
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsAdminFactory(groupName="test-group")]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/member",
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/admin",
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", models=["ManagedGroup"], stdout=out)
        self.assertIn("ManagedGroupAudit... ok! (ignoring 2 records)", out.getvalue())

    def test_command_output_workspaces_ignored_one_record(self):
        """Test command output."""
        factories.IgnoredWorkspaceSharingFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces",
            status=200,
            json=[self.get_api_workspace_json("test-bp", "test-ws", "OWNER")],
        )
        # Response to check workspace access.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl",
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws",
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", models=["Workspace"], stdout=out)
        self.assertIn("WorkspaceAudit... ok! (ignoring 1 records)", out.getvalue())

    def test_command_output_workspaces_ignored_two_records(self):
        """Test command output."""
        factories.IgnoredWorkspaceSharingFactory.create_batch(
            2,
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces",
            status=200,
            json=[self.get_api_workspace_json("test-bp", "test-ws", "OWNER")],
        )
        # Response to check workspace access.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl",
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws",
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", models=["Workspace"], stdout=out)
        self.assertIn("WorkspaceAudit... ok! (ignoring 2 records)", out.getvalue())

    def test_command_run_audit_one_instance_ok(self):
        """Test command output."""
        billing_project = BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(responses.GET, api_url, status=200)
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", models=["BillingProject"], stdout=out)
        self.assertIn("BillingProjectAudit... ok!", out.getvalue())
        self.assertNotIn("errors", out.getvalue())
        self.assertNotIn("not_in_app", out.getvalue())

    def test_command_run_audit_ok_email(self):
        """Test command output."""
        billing_project = BillingProjectFactory.create()
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
        self.assertIn("BillingProjectAudit... ok!", out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertIn("ok", email.subject)
        # Text body.
        audit_results = billing_projects.BillingProjectAudit()
        audit_results.run_audit()
        self.assertEqual(pprint.pformat(audit_results.export()), email.body)
        # HTML body.
        self.assertEqual(len(email.alternatives), 1)
        # Check that the number of "ok" instances is correct in email body.
        self.assertIn("1 instance(s) verified", email.alternatives[0][0])
        # Check ignored instances.
        self.assertIn("Ignoring 0 record(s)", email.alternatives[0][0])

    def test_command_run_audit_ok_email_errors_only(self):
        """Test command output when email and errors_only is set."""
        billing_project = BillingProjectFactory.create()
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
        self.assertIn("BillingProjectAudit... ok!", out.getvalue())
        # No message has been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_command_run_audit_ok_ignored_records_email(self):
        """Test command output."""
        factories.IgnoredManagedGroupMembershipFactory.create(group__name="test-group")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1",
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsAdminFactory(groupName="test-group")]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/member",
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/admin",
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            models=["ManagedGroup"],
            email="test@example.com",
            stdout=out,
        )
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertIn("ok", email.subject)
        # Text body.
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertEqual(pprint.pformat(audit_results.export()), email.body)
        # HTML body.
        self.assertEqual(len(email.alternatives), 1)
        # Check that the number of "ok" instances is correct in email body.
        self.assertIn("1 instance(s) verified", email.alternatives[0][0])
        # Check ignored instances.
        self.assertIn("Ignoring 1 record(s)", email.alternatives[0][0])

    def test_command_run_audit_ok_ignored_records_email_errors_only(self):
        """Test command output when email and errors_only is set, and there are ignored records."""
        factories.IgnoredManagedGroupMembershipFactory.create(group__name="test-group")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1",
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsAdminFactory(groupName="test-group")]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/member",
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/admin",
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            models=["ManagedGroup"],
            email="test@example.com",
            errors_only=True,
            stdout=out,
        )
        self.assertIn("ManagedGroupAudit... ok!", out.getvalue())
        # No message has been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_command_run_audit_not_ok(self):
        """Test command output when BillingProject audit is not ok."""
        billing_project = BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(responses.GET, api_url, status=404, json={"message": "error"})
        out = StringIO()
        call_command("run_anvil_audit", "--no-color", models=["BillingProject"], stdout=out)
        self.assertIn("BillingProjectAudit... problems found.", out.getvalue())
        self.assertIn("""'errors':""", out.getvalue())
        self.assertIn(billing_projects.BillingProjectAudit.ERROR_NOT_IN_ANVIL, out.getvalue())

    def test_command_run_audit_not_ok_email(self):
        """Test command output when BillingProject audit is not ok with email specified."""
        billing_project = BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(responses.GET, api_url, status=404, json={"message": "error"})
        out = StringIO()
        call_command(
            "run_anvil_audit",
            "--no-color",
            models=["BillingProject"],
            email="test@example.com",
            stdout=out,
        )
        self.assertIn("BillingProjectAudit... problems found.", out.getvalue())
        # Not printed to stdout.
        self.assertIn("""'errors':""", out.getvalue())
        # One message has been sent.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertIn("errors", email.subject)
        # Text body.
        audit_results = billing_projects.BillingProjectAudit()
        audit_results.run_audit()
        # HTML body.
        self.assertEqual(len(email.alternatives), 1)

    def test_command_run_audit_not_ok_email_has_html_link(self):
        """Test command output when BillingProject audit is not ok with email specified."""
        billing_project = BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(responses.GET, api_url, status=404, json={"message": "error"})
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

    def test_command_run_audit_not_ok_email_has_html_link_different_domain(self):
        """Test command output when BillingProject audit is not ok with email specified."""
        site = Site.objects.create(domain="foobar.com", name="test")
        site.save()
        with self.settings(SITE_ID=site.id):
            billing_project = BillingProjectFactory.create()
            # Add a response.
            api_url = self.get_api_url_billing_project(billing_project.name)
            self.anvil_response_mock.add(responses.GET, api_url, status=404, json={"message": "error"})
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
        billing_project = BillingProjectFactory.create()
        # Add a response.
        api_url = self.get_api_url_billing_project(billing_project.name)
        self.anvil_response_mock.add(responses.GET, api_url, status=500, json={"message": "error"})
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("run_anvil_audit", "--no-color", models=["BillingProject"], stdout=out)

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


class RunAnVILAuditTablesTest(TestCase):
    def setUp(self):
        super().setUp()

        class GenericAuditResults(base.AnVILAudit):
            TEST_ERROR_1 = "Test error 1"
            TEST_ERROR_2 = "Test error 2"

        self.audit_results = GenericAuditResults()
        # It doesn't matter what model we use at this point, so just pick Account.
        self.model_factory = AccountFactory

    def test_errors_table(self):
        """Errors table is correct."""
        obj_verified = self.model_factory.create()
        self.audit_results.add_result(base.ModelInstanceResult(obj_verified))
        obj_error = self.model_factory.create()
        error_result = base.ModelInstanceResult(obj_error)
        error_result.add_error(self.audit_results.TEST_ERROR_1)
        error_result.add_error(self.audit_results.TEST_ERROR_2)
        self.audit_results.add_result(error_result)
        self.audit_results.add_result(base.NotInAppResult("foo"))
        table = ErrorTableWithLink(self.audit_results.get_error_results())
        self.assertEqual(table.rows[0].get_cell("errors"), "Test error 1, Test error 2")
