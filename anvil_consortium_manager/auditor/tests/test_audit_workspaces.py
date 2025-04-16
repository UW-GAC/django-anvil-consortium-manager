import responses
from django.test import TestCase
from faker import Faker

from anvil_consortium_manager.models import WorkspaceGroupSharing
from anvil_consortium_manager.tests.factories import (
    WorkspaceAuthorizationDomainFactory,
    WorkspaceFactory,
    WorkspaceGroupSharingFactory,
)
from anvil_consortium_manager.tests.utils import AnVILAPIMockTestMixin

from ..audit import workspaces as workspaces
from . import factories

fake = Faker()


class WorkspaceAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the Workspace.anvil_audit method."""

    def get_api_url(self):
        return self.api_client.rawls_entry_point + "/api/workspaces"

    def get_api_workspace_json(
        self,
        billing_project_name,
        workspace_name,
        access,
        auth_domains=[],
        is_locked=False,
        public=False,
    ):
        """Return the json dictionary for a single workspace on AnVIL."""
        return {
            "accessLevel": access,
            "workspace": {
                "name": workspace_name,
                "namespace": billing_project_name,
                "authorizationDomain": [{"membersGroupName": x} for x in auth_domains],
                "isLocked": is_locked,
            },
            "public": public,
        }

    def get_api_workspace_acl_url(self, billing_project_name, workspace_name):
        return (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
            + "/acl"
        )

    def get_api_workspace_acl_response(self, service_account_access="OWNER", can_share=True, can_compute=True):
        """Return a json for the workspace/acl method where no one else can access."""
        acl = {}
        if service_account_access:
            acl[self.service_account_email] = {
                "accessLevel": service_account_access,
                "canCompute": can_compute,
                "canShare": can_share,
                "pending": False,
            }
        return {"acl": acl}

    def get_api_bucket_options_url(self, billing_project_name, workspace_name):
        return self.api_client.rawls_entry_point + "/api/workspaces/" + billing_project_name + "/" + workspace_name

    def get_api_bucket_options_response(self):
        """Return a json for the workspace/acl method that is not requester pays."""
        return {"bucketOptions": {"requesterPays": False}}

    def test_anvil_audit_no_workspaces(self):
        """anvil_audit works correct if there are no Workspaces in the app."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_workspace_no_errors(self):
        """anvil_audit works correct if there is one workspace in the app and it exists on AnVIL."""
        workspace = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json(workspace.billing_project.name, workspace.name, "OWNER")],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_workspace_not_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app but not on AnVIL."""
        workspace = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_one_workspace_owner_in_app_reader_on_anvil(self):
        """anvil_audit raises exception if one workspace exists in the app but the access on AnVIL is READER."""
        workspace = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json(workspace.billing_project.name, workspace.name, "READER")],
        )
        # We only check other API calls if the app is an owner.
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_OWNER_ON_ANVIL]))

    def test_anvil_audit_one_workspace_owner_in_app_writer_on_anvil(self):
        """anvil_audit raises exception if one workspace exists in the app but the access on AnVIL is WRITER."""
        workspace = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json(workspace.billing_project.name, workspace.name, "WRITER")],
        )
        # We only check other API calls if the app is an owner.
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_OWNER_ON_ANVIL]))

    def test_anvil_audit_one_workspace_is_locked_in_app_not_on_anvil(self):
        """anvil_audit raises exception if workspace is locked in the app but not on AnVIL."""
        workspace = WorkspaceFactory.create(is_locked=True)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    is_locked=False,
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_LOCK]))

    def test_anvil_audit_one_workspace_is_not_locked_in_app_but_is_on_anvil(self):
        """anvil_audit raises exception if workspace is locked in the app but not on AnVIL."""
        workspace = WorkspaceFactory.create(is_locked=False)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    is_locked=True,
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_LOCK]))

    def test_anvil_audit_one_workspace_is_requester_pays_in_app_not_on_anvil(self):
        """anvil_audit raises exception if workspace is requester_pays in the app but not on AnVIL."""
        workspace = WorkspaceFactory.create(is_requester_pays=True)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    is_locked=False,
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_REQUESTER_PAYS]))

    def test_anvil_audit_one_workspace_is_not_requester_pays_in_app_but_is_on_anvil(self):
        """anvil_audit raises exception if workspace is requester_pays in the app but not on AnVIL."""
        workspace = WorkspaceFactory.create(is_requester_pays=False)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    is_locked=False,
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        response = self.get_api_bucket_options_response()
        response["bucketOptions"]["requesterPays"] = True
        self.anvil_response_mock.add(responses.GET, workspace_acl_url, status=200, json=response)
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_REQUESTER_PAYS]))

    def test_anvil_audit_two_workspaces_no_errors(self):
        """anvil_audit returns None if if two workspaces exist in both the app and AnVIL."""
        workspace_1 = WorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(workspace_1.billing_project.name, workspace_1.name, "OWNER"),
                self.get_api_workspace_json(workspace_2.billing_project.name, workspace_2.name, "OWNER"),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_groups_json_response_order_does_not_matter(self):
        """Order of groups in the json response does not matter."""
        workspace_1 = WorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(workspace_2.billing_project.name, workspace_2.name, "OWNER"),
                self.get_api_workspace_json(workspace_1.billing_project.name, workspace_1.name, "OWNER"),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_workspaces_first_not_on_anvil(self):
        """anvil_audit raises exception if two workspaces exist in the app but the first is not not on AnVIL."""
        workspace_1 = WorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(workspace_2.billing_project.name, workspace_2.name, "OWNER"),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_workspaces_first_different_access(self):
        """anvil_audit when if two workspaces exist in the app but access to the first is different on AnVIL."""
        workspace_1 = WorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(workspace_1.billing_project.name, workspace_1.name, "READER"),
                self.get_api_workspace_json(workspace_2.billing_project.name, workspace_2.name, "OWNER"),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_OWNER_ON_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_workspaces_both_missing_in_anvil(self):
        """anvil_audit when there are two workspaces that exist in the app but not in AnVIL."""
        workspace_1 = WorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_one_workspace_missing_in_app(self):
        """anvil_audit returns not_in_app info if a workspace exists on AnVIL but not in the app."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp", "test-ws", "OWNER")],
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-bp/test-ws")

    def test_anvil_audit_two_workspaces_missing_in_app(self):
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json("test-bp-1", "test-ws-1", "OWNER"),
                self.get_api_workspace_json("test-bp-2", "test-ws-2", "OWNER"),
            ],
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-bp-1/test-ws-1")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "test-bp-2/test-ws-2")

    def test_different_billing_project(self):
        """A workspace is reported as missing if it has the same name but a different billing project in app."""
        workspace = WorkspaceFactory.create(billing_project__name="test-bp-app", name="test-ws")
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp-anvil", "test-ws", "OWNER")],
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-bp-anvil/test-ws")

    def test_ignores_workspaces_where_app_is_reader_on_anvil(self):
        """Audit ignores workspaces on AnVIL where app is a READER on AnVIL."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp", "test-ws", "READER")],
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_ignores_workspaces_where_app_is_writer_on_anvil(self):
        """Audit ignores workspaces on AnVIL where app is a WRITER on AnVIL."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp", "test-ws", "WRITER")],
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_one_workspace_one_auth_domain(self):
        """anvil_audit works properly when there is one workspace with one auth domain."""
        auth_domain = WorkspaceAuthorizationDomainFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    auth_domain.workspace.billing_project.name,
                    auth_domain.workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(auth_domain.workspace)
        self.assertTrue(record_result.ok())

    def test_one_workspace_two_auth_domains(self):
        """anvil_audit works properly when there is one workspace with two auth domains."""
        workspace = WorkspaceFactory.create()
        auth_domain_1 = WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        auth_domain_2 = WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain_1.group.name, auth_domain_2.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertTrue(record_result.ok())

    def test_one_workspace_two_auth_domains_order_does_not_matter(self):
        """anvil_audit works properly when there is one workspace with two auth domains."""
        workspace = WorkspaceFactory.create()
        auth_domain_1 = WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="aa")
        auth_domain_2 = WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="zz")
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain_2.group.name, auth_domain_1.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertTrue(record_result.ok())

    def test_one_workspace_no_auth_domain_in_app_one_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with no auth domain in the app but one on AnVIL."""
        workspace = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=["auth-anvil"],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_one_auth_domain_in_app_no_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with one auth domain in the app but none on AnVIL."""
        auth_domain = WorkspaceAuthorizationDomainFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    auth_domain.workspace.billing_project.name,
                    auth_domain.workspace.name,
                    "OWNER",
                    auth_domains=[],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(auth_domain.workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_no_auth_domain_in_app_two_auth_domains_on_anvil(self):
        """anvil_audit works properly when there is one workspace with no auth domain in the app but two on AnVIL."""
        workspace = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=["auth-domain"],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_two_auth_domains_in_app_no_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with two auth domains in the app but none on AnVIL."""
        workspace = WorkspaceFactory.create()
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_two_auth_domains_in_app_one_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with two auth domains in the app but one on AnVIL."""
        workspace = WorkspaceFactory.create()
        auth_domain_1 = WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain_1.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_different_auth_domains(self):
        """anvil_audit works properly when the app and AnVIL have different auth domains for the same workspace."""
        auth_domain = WorkspaceAuthorizationDomainFactory.create(group__name="app")
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    auth_domain.workspace.billing_project.name,
                    auth_domain.workspace.name,
                    "OWNER",
                    auth_domains=["anvil"],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(auth_domain.workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_two_workspaces_first_auth_domains_do_not_match(self):
        """anvil_audit works properly when there are two workspaces in the app and the first has auth domain issues."""
        workspace_1 = WorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace_1.billing_project.name,
                    workspace_1.name,
                    "OWNER",
                    auth_domains=["anvil"],
                ),
                self.get_api_workspace_json(
                    workspace_2.billing_project.name,
                    workspace_2.name,
                    "OWNER",
                    auth_domains=[],
                ),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertTrue(record_result.ok())

    def test_two_workspaces_auth_domains_do_not_match_for_both(self):
        """anvil_audit works properly when there are two workspaces in the app and both have auth domain issues."""
        workspace_1 = WorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace_1.billing_project.name,
                    workspace_1.name,
                    "OWNER",
                    auth_domains=["anvil-1"],
                ),
                self.get_api_workspace_json(
                    workspace_2.billing_project.name,
                    workspace_2.name,
                    "OWNER",
                    auth_domains=["anvil-2"],
                ),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_with_two_errors(self):
        """One workspace has two errors: different auth domains and different lock status."""
        workspace = WorkspaceFactory.create()
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json(workspace.billing_project.name, workspace.name, "OWNER", is_locked=True)],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors,
            set(
                [
                    audit_results.ERROR_DIFFERENT_LOCK,
                    audit_results.ERROR_DIFFERENT_AUTH_DOMAINS,
                ]
            ),
        )

    def test_fails_sharing_audit(self):
        """anvil_audit works properly when one workspace fails its sharing audit."""
        workspace = WorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(workspace=workspace)
        # Response for the main call about workspaces.
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = workspaces.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_WORKSPACE_SHARING]))


class WorkspaceSharingAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the WorkspaceSharingAudit class."""

    def setUp(self):
        super().setUp()
        # Set this variable here because it will include the service account.
        # Tests can update it with the update_api_response method.
        self.api_response = {"acl": {}}
        # Create a workspace for use in tests.
        self.workspace = WorkspaceFactory.create()
        self.api_url = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + self.workspace.billing_project.name
            + "/"
            + self.workspace.name
            + "/acl"
        )

    def update_api_response(self, email, access, can_compute=False, can_share=False):
        """Return a paired down json for a single ACL, including the service account."""
        self.api_response["acl"].update(
            {
                email: {
                    "accessLevel": access,
                    "canCompute": can_compute,
                    "canShare": can_share,
                    "pending": False,
                }
            }
        )

    def test_no_access(self):
        """anvil_audit works correctly if this workspace is not shared with any groups."""
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_one_reader(self):
        """anvil_audit works correctly if this group has one group member."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        self.update_api_response(access.group.email, access.access)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_two_readers(self):
        """anvil_audit works correctly if this workspace has two group readers."""
        access_1 = WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        access_2 = WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        self.update_api_response(access_1.group.email, "READER")
        self.update_api_response(access_2.group.email, "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertTrue(model_result.ok())
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertTrue(model_result.ok())

    def test_one_reader_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has one group reader not in anvil."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_two_readers_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has two group readers not in anvil."""
        access_1 = WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        access_2 = WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_one_reader_not_in_app(self):
        """anvil_audit works correctly if this workspace has one group reader not in the app."""
        self.update_api_response("test-member@firecloud.org", "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "READER")
        self.assertEqual(model_result.email, "test-member@firecloud.org")
        self.assertFalse(model_result.can_compute)
        self.assertFalse(model_result.can_share)

    def test_two_readers_not_in_app(self):
        """anvil_audit works correctly if this workspace has two group readers not in the app."""
        self.update_api_response("test-member-1@firecloud.org", "READER")
        self.update_api_response("test-member-2@firecloud.org", "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "READER")
        self.assertEqual(model_result.email, "test-member-1@firecloud.org")
        self.assertFalse(model_result.can_compute)
        self.assertFalse(model_result.can_share)
        model_result = audit_results.get_not_in_app_results()[1]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "READER")
        self.assertEqual(model_result.email, "test-member-2@firecloud.org")
        self.assertFalse(model_result.can_compute)
        self.assertFalse(model_result.can_share)

    def test_one_reader_ignored(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.update_api_response(obj.ignored_email, "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj)
        self.assertEqual(record_result.current_access, "READER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)

    def test_two_readers_ignored(self):
        obj_1 = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        obj_2 = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.update_api_response(obj_1.ignored_email, "READER")
        self.update_api_response(obj_2.ignored_email, "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 2)
        record_results = audit_results.get_ignored_results()
        record_result = [record_result for record_result in record_results if record_result.model_instance == obj_1][0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj_1)
        self.assertEqual(record_result.current_access, "READER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)
        record_result = [record_result for record_result in record_results if record_result.model_instance == obj_2][0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj_2)
        self.assertEqual(record_result.current_access, "READER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)

    def test_one_reader_case_insensitive(self):
        """anvil_audit ignores case."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace, group__name="tEsT-mEmBeR")
        self.update_api_response("Test-Member@firecloud.org", "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_one_reader_ignored_case_insensitive(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create(
            workspace=self.workspace, ignored_email="test-member@firecloud.org"
        )
        self.update_api_response("Test-Member@firecloud.org", "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj)
        self.assertEqual(record_result.current_access, "READER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)

    def test_one_writer(self):
        """anvil_audit works correctly if this workspace has one group writer."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.WRITER)
        self.update_api_response(access.group.email, "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_two_writers(self):
        """anvil_audit works correctly if this workspace has two group writers."""
        access_1 = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.WRITER)
        access_2 = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.WRITER)
        self.update_api_response(access_1.group.email, "WRITER")
        self.update_api_response(access_2.group.email, "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertTrue(model_result.ok())
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertTrue(model_result.ok())

    def test_one_writer_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has one group writer not in anvil."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.WRITER)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_two_writers_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has two group writers not in anvil."""
        access_1 = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.WRITER)
        access_2 = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.WRITER)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_one_writer_not_in_app(self):
        """anvil_audit works correctly if this workspace has one group writer not in the app."""
        self.update_api_response("test-writer@firecloud.org", "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "WRITER")
        self.assertEqual(model_result.email, "test-writer@firecloud.org")
        self.assertFalse(model_result.can_compute)
        self.assertFalse(model_result.can_share)

    def test_two_writers_not_in_app(self):
        """anvil_audit works correctly if this workspace has two group writers not in the app."""
        self.update_api_response("test-writer-1@firecloud.org", "WRITER")
        self.update_api_response("test-writer-2@firecloud.org", "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "WRITER")
        self.assertEqual(model_result.email, "test-writer-1@firecloud.org")
        self.assertFalse(model_result.can_compute)
        self.assertFalse(model_result.can_share)
        model_result = audit_results.get_not_in_app_results()[1]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "WRITER")
        self.assertEqual(model_result.email, "test-writer-2@firecloud.org")
        self.assertFalse(model_result.can_compute)
        self.assertFalse(model_result.can_share)

    def test_one_writer_not_in_app_can_compute(self):
        """anvil_audit works correctly if this workspace has one group writer not in the app."""
        self.update_api_response("test-writer@firecloud.org", "WRITER", can_compute=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "WRITER")
        self.assertEqual(model_result.email, "test-writer@firecloud.org")
        self.assertTrue(model_result.can_compute)
        self.assertFalse(model_result.can_share)

    def test_one_writer_not_in_app_can_share(self):
        """anvil_audit works correctly if this workspace has one group writer not in the app."""
        self.update_api_response("test-writer@firecloud.org", "WRITER", can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "WRITER")
        self.assertEqual(model_result.email, "test-writer@firecloud.org")
        self.assertFalse(model_result.can_compute)
        self.assertTrue(model_result.can_share)

    def test_one_writer_ignored(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.update_api_response(obj.ignored_email, "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj)
        self.assertEqual(record_result.current_access, "WRITER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)

    def test_two_writer_ignored(self):
        obj_1 = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        obj_2 = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.update_api_response(obj_1.ignored_email, "WRITER")
        self.update_api_response(obj_2.ignored_email, "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 2)
        record_results = audit_results.get_ignored_results()
        record_result = [record_result for record_result in record_results if record_result.model_instance == obj_1][0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj_1)
        self.assertEqual(record_result.current_access, "WRITER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)
        record_result = [record_result for record_result in record_results if record_result.model_instance == obj_2][0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj_2)
        self.assertEqual(record_result.current_access, "WRITER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)

    def test_one_writer_case_insensitive(self):
        """anvil_audit works correctly if this workspace has one group member not in the app."""
        access = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            group__name="tEsT-wRiTeR",
            access=WorkspaceGroupSharing.WRITER,
        )
        self.update_api_response("Test-Writer@firecloud.org", "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_one_writer_ignored_case_insensitive(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create(
            workspace=self.workspace, ignored_email="test@firecloud.org"
        )
        self.update_api_response("Test@firecloud.org", "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj)
        self.assertEqual(record_result.current_access, "WRITER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)

    def test_one_owner(self):
        """anvil_audit works correctly if this workspace has one group owner."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.OWNER)
        self.update_api_response(access.group.email, "OWNER", can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_two_owners(self):
        """anvil_audit works correctly if this workspace has two group owners."""
        access_1 = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.OWNER)
        access_2 = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.OWNER)
        self.update_api_response(access_1.group.email, "OWNER", can_share=True)
        self.update_api_response(access_2.group.email, "OWNER", can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertTrue(model_result.ok())
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertTrue(model_result.ok())

    def test_one_owner_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has one group owners not in anvil."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.OWNER)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_two_owners_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has two group owners not in anvil."""
        access_1 = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.OWNER)
        access_2 = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.OWNER)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_one_owner_not_in_app(self):
        """anvil_audit works correctly if this workspace has one group owner not in the app."""
        self.update_api_response("test-writer@firecloud.org", "OWNER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "OWNER")
        self.assertEqual(model_result.email, "test-writer@firecloud.org")
        self.assertFalse(model_result.can_compute)
        self.assertFalse(model_result.can_share)

    def test_two_owners_not_in_app(self):
        """anvil_audit works correctly if this workspace has two group owners not in the app."""
        self.update_api_response("test-writer-1@firecloud.org", "OWNER")
        self.update_api_response("test-writer-2@firecloud.org", "OWNER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "OWNER")
        self.assertEqual(model_result.email, "test-writer-1@firecloud.org")
        self.assertFalse(model_result.can_compute)
        self.assertFalse(model_result.can_share)
        model_result = audit_results.get_not_in_app_results()[1]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "OWNER")
        self.assertEqual(model_result.email, "test-writer-2@firecloud.org")
        self.assertFalse(model_result.can_compute)
        self.assertFalse(model_result.can_share)

    def test_one_owner_ignored(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.update_api_response(obj.ignored_email, "OWNER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj)
        self.assertEqual(record_result.current_access, "OWNER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)

    def test_two_owner_ignored(self):
        obj_1 = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        obj_2 = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.update_api_response(obj_1.ignored_email, "OWNER")
        self.update_api_response(obj_2.ignored_email, "OWNER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 2)
        record_results = audit_results.get_ignored_results()
        record_result = [record_result for record_result in record_results if record_result.model_instance == obj_1][0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj_1)
        self.assertEqual(record_result.current_access, "OWNER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)
        record_result = [record_result for record_result in record_results if record_result.model_instance == obj_2][0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj_2)
        self.assertEqual(record_result.current_access, "OWNER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)

    def test_one_owner_case_insensitive(self):
        """anvil_audit works correctly with different cases for owner emails."""
        access = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            group__name="tEsT-oWnEr",
            access=WorkspaceGroupSharing.OWNER,
        )
        self.update_api_response("Test-Owner@firecloud.org", "OWNER", can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_one_owner_ignored_case_insensitive(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create(
            workspace=self.workspace, ignored_email="test@firecloud.org"
        )
        self.update_api_response("Test@firecloud.org", "OWNER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj)
        self.assertEqual(record_result.current_access, "OWNER")
        self.assertFalse(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)

    def test_different_access_reader_in_app_writer_in_anvil(self):
        """anvil_audit works correctly if a group has different access to a workspace in AnVIL."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.READER)
        self.update_api_response(access.group.email, "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_DIFFERENT_ACCESS]))

    def test_different_access_reader_in_app_owner_in_anvil(self):
        """anvil_audit works correctly if a group has different access to a workspace in AnVIL."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.READER)
        self.update_api_response(access.group.email, "OWNER", can_compute=True, can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(
            model_result.errors,
            set(
                [
                    audit_results.ERROR_DIFFERENT_ACCESS,
                    audit_results.ERROR_DIFFERENT_CAN_COMPUTE,
                    audit_results.ERROR_DIFFERENT_CAN_SHARE,
                ]
            ),
        )

    def test_different_can_compute(self):
        """anvil_audit works correctly if can_compute is different between the app and AnVIL."""
        access = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        self.update_api_response(access.group.email, "WRITER", can_compute=False)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_DIFFERENT_CAN_COMPUTE]))

    def test_different_can_share(self):
        """anvil_audit works correctly if can_share is True in AnVIL."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace, access=WorkspaceGroupSharing.WRITER)
        self.update_api_response(access.group.email, "WRITER", can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_DIFFERENT_CAN_SHARE]))

    def test_removes_service_account(self):
        """Removes the service account from acl if it exists."""
        self.update_api_response(self.service_account_email, "OWNER", can_compute=True, can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_owner_can_share_true(self):
        """Owners must have can_share=True."""
        access = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=WorkspaceGroupSharing.OWNER,
            can_compute=True,
        )
        self.update_api_response(access.group.email, "OWNER", can_compute=True, can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_writer_can_share_false(self):
        """Writers must have can_share=False."""
        access = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        self.update_api_response(access.group.email, "WRITER", can_compute=True, can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_DIFFERENT_CAN_SHARE]))

    def test_reader_can_share_false(self):
        """Readers must have can_share=False."""
        access = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=WorkspaceGroupSharing.READER,
            can_compute=False,
        )
        self.update_api_response(access.group.email, "READER", can_compute=False, can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_DIFFERENT_CAN_SHARE]))

    def test_ignored_can_share(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.update_api_response(obj.ignored_email, "WRITER", can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj)
        self.assertEqual(record_result.current_access, "WRITER")
        self.assertFalse(record_result.current_can_compute)
        self.assertTrue(record_result.current_can_share)

    def test_ignored_can_compute(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.update_api_response(obj.ignored_email, "WRITER", can_compute=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj)
        self.assertEqual(record_result.current_access, "WRITER")
        self.assertTrue(record_result.current_can_compute)
        self.assertFalse(record_result.current_can_share)

    def test_ignored_same_email_different_workspace(self):
        """The email is ignored for a different workspace."""
        # Create an ignored record for this email, but for a different workspace.
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.update_api_response(obj.ignored_email, "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "READER")
        self.assertEqual(model_result.email, obj.ignored_email)
        self.assertFalse(model_result.can_compute)
        self.assertFalse(model_result.can_share)

    def test_ignored_different_email_same_workspace(self):
        """A different email is ignored for this workspace."""
        # Create an ignored record for this email, but for a different workspace.
        obj = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.update_api_response("other-email@example.com", "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(model_result, workspaces.WorkspaceSharingNotInAppResult)
        self.assertEqual(model_result.access, "READER")
        self.assertEqual(model_result.email, "other-email@example.com")
        self.assertFalse(model_result.can_compute)
        self.assertFalse(model_result.can_share)
        record_result = audit_results.get_ignored_results()[0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj)
        self.assertIsNone(record_result.current_access)
        self.assertIsNone(record_result.current_can_compute)
        self.assertIsNone(record_result.current_can_share)

    def test_ignored_still_reports_records_when_not_shared_with_email(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj)
        self.assertIsNone(record_result.current_access)
        self.assertIsNone(record_result.current_can_compute)
        self.assertIsNone(record_result.current_can_share)

    def test_ignored_order_by_email(self):
        obj_1 = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace, ignored_email="foo-2@bar.com")
        obj_2 = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace, ignored_email="foo-1@bar.com")
        self.update_api_response(obj_1.ignored_email, "READER")
        self.update_api_response(obj_2.ignored_email, "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = workspaces.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 2)
        record_result = audit_results.get_ignored_results()[0]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj_2)
        record_result = audit_results.get_ignored_results()[1]
        self.assertIsInstance(record_result, workspaces.WorkspaceSharingIgnoredResult)
        self.assertEqual(record_result.model_instance, obj_1)
