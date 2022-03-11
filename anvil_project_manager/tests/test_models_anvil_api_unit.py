import responses
from django.core.exceptions import ValidationError
from django.test import TestCase

from .. import anvil_api, exceptions, models
from . import factories
from .utils import AnVILAPIMockTestMixin


class BillingProjectAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.object = factories.BillingProjectFactory()
        self.url = self.entry_point + "/api/billing/v2/" + self.object.name

    def test_anvil_exists_does_exist(self):
        responses.add(responses.GET, self.url, status=200)
        self.assertIs(self.object.anvil_exists(), True)
        responses.assert_call_count(self.url, 1)

    def test_anvil_exists_does_not_exist(self):
        self.url = self.entry_point + "/api/billing/v2/" + self.object.name
        responses.add(
            responses.GET, self.url, status=404, json={"message": "mock message"}
        )
        self.assertIs(self.object.anvil_exists(), False)
        responses.assert_call_count(self.url, 1)


class GroupAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        self.object = factories.GroupFactory()
        self.url = self.entry_point + "/api/groups/" + self.object.name

    def test_anvil_exists_does_exist(self):
        responses.add(responses.GET, self.url, status=200)
        self.assertIs(self.object.anvil_exists(), True)
        responses.assert_call_count(self.url, 1)

    def test_anvil_exists_does_not_exist(self):
        responses.add(
            responses.GET, self.url, status=404, json={"message": "mock message"}
        )
        self.assertIs(self.object.anvil_exists(), False)
        responses.assert_call_count(self.url, 1)

    def test_anvil_exists_forbidden(self):
        responses.add(
            responses.GET, self.url, status=403, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_exists()
        responses.assert_call_count(self.url, 1)

    def test_anvil_exists_internal_error(self):
        responses.add(
            responses.GET, self.url, status=500, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_exists()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_successful(self):
        responses.add(
            responses.POST, self.url, status=201, json={"message": "mock message"}
        )
        self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_already_exists(self):
        """Returns documented response code when a group already exists. Unfortunately the actual return code is 201."""
        responses.add(
            responses.POST, self.url, status=409, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_internal_error(
        self,
    ):
        responses.add(
            responses.POST, self.url, status=500, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_other(self):
        responses.add(
            responses.POST, self.url, status=499, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_existing(self):
        responses.add(
            responses.DELETE, self.url, status=204, json={"message": "mock message"}
        )
        self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_forbidden(self):
        responses.add(
            responses.DELETE, self.url, status=403, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_not_found(self):
        responses.add(
            responses.DELETE, self.url, status=404, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_in_use(self):
        responses.add(
            responses.DELETE, self.url, status=409, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_other(self):
        responses.add(
            responses.DELETE, self.url, status=499, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)


class WorkspaceAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        self.object = factories.WorkspaceFactory()
        self.url_create = self.entry_point + "/api/workspaces"
        self.url_workspace = (
            self.entry_point
            + "/api/workspaces/"
            + self.object.billing_project.name
            + "/"
            + self.object.name
        )

    def test_anvil_exists_does_exist(self):
        responses.add(responses.GET, self.url_workspace, status=200)
        self.assertIs(self.object.anvil_exists(), True)
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_exists_does_not_exist(self):
        responses.add(
            responses.GET,
            self.url_workspace,
            status=404,
            json={"message": "mock message"},
        )
        self.assertIs(self.object.anvil_exists(), False)
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_exists_forbidden(self):
        responses.add(
            responses.GET,
            self.url_workspace,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_exists()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_exists_internal_error(self):
        responses.add(
            responses.GET,
            self.url_workspace,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_exists()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_create_successful(self):
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=201,
            match=[responses.matchers.json_params_matcher(json)],
        )
        self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_bad_request(self):
        """Returns documented response code when workspace already exists."""
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=400,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_forbidden(self):
        """Returns documented response code when a workspace can't be created."""
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=403,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_already_exists(self):
        """Returns documented response code when a workspace already exists."""
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=409,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_internal_error(self):
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=500,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_other(self):
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=404,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_one_auth_domain_success(self):
        """Returns documented response code when trying to create a workspace with a valid auth domain."""
        auth_domain = factories.GroupFactory.create()
        self.object.authorization_domains.add(auth_domain)
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
            "authorizationDomain": [{"membersGroupName": auth_domain.name}],
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=201,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_two_auth_domains_success(self):
        """Returns documented response code when trying to create a workspace with two valid auth domains."""
        auth_domain_1 = factories.GroupFactory.create()
        auth_domain_2 = factories.GroupFactory.create()
        self.object.authorization_domains.add(auth_domain_1)
        self.object.authorization_domains.add(auth_domain_2)
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
            "authorizationDomain": [
                {"membersGroupName": auth_domain_1.name},
                {"membersGroupName": auth_domain_2.name},
            ],
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=201,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_one_auth_domain_error(self):
        """Returns documented response code when trying to create a workspace with a valid auth domain."""
        auth_domain = factories.GroupFactory.create()
        self.object.authorization_domains.add(auth_domain)
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
            "authorizationDomain": [{"membersGroupName": auth_domain.name}],
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=400,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_delete_existing(self):
        responses.add(responses.DELETE, self.url_workspace, status=202)
        self.object.anvil_delete()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_delete_forbidden(self):
        responses.add(
            responses.DELETE,
            self.url_workspace,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_delete_not_found(self):
        responses.add(
            responses.DELETE,
            self.url_workspace,
            status=404,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_delete_in_use(self):
        responses.add(
            responses.DELETE,
            self.url_workspace,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_delete_other(self):
        responses.add(
            responses.DELETE,
            self.url_workspace,
            status=499,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        responses.assert_call_count(self.url_workspace, 1)


class WorkspaceClassMethodsAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests of class methods for the Workspace model."""

    def get_api_url(self, billing_project_name, workspace_name):
        return (
            self.entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
        )

    def get_api_json_response(self, billing_project, workspace, access="OWNER"):
        """Return a pared down version of the json response from the AnVIL API with only fields we need."""
        json_data = {
            "accessLevel": access,
            "owners": [],
            "workspace": {
                "authorizationDomain": [],
                "name": workspace,
                "namespace": billing_project,
            },
        }
        return json_data

    def test_anvil_import_billing_project_already_exists_in_django_db(self):
        """A workspace can be imported from AnVIL if we are owners and if the billing project exists."""
        workspace_name = "test-workspace"
        billing_project = factories.BillingProjectFactory.create()
        responses.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        workspace = models.Workspace.anvil_import(billing_project.name, workspace_name)
        # Check workspace values.
        self.assertEqual(workspace.billing_project, billing_project)
        self.assertEqual(workspace.name, workspace_name)
        # Check that it was saved.
        self.assertEqual(models.Workspace.objects.count(), 1)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)
        # No additional billing projects were created.
        self.assertEqual(models.BillingProject.objects.count(), 1)

    def test_anvil_import_billing_project_does_not_exist_in_django_db(self):
        """A workspace can be imported from AnVIL if we are owners and if the billing project does not exist."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        workspace = models.Workspace.anvil_import(billing_project_name, workspace_name)
        # A billing project was created.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        billing_project = models.BillingProject.objects.get()
        self.assertEqual(billing_project.name, billing_project_name)
        # Check workspace values.
        self.assertEqual(workspace.billing_project, billing_project)
        self.assertEqual(workspace.name, workspace_name)
        # Check that it was saved.
        self.assertEqual(models.Workspace.objects.count(), 1)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)

    def test_anvil_import_not_owners_of_workspace(self):
        """A workspace cannot be imported from AnVIL if we are not owners."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(
                billing_project_name, workspace_name, access="READER"
            ),
        )
        with self.assertRaises(exceptions.AnVILNotWorkspaceOwnerError):
            models.Workspace.anvil_import(billing_project_name, workspace_name)
        # Check workspace values.
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_no_access_to_anvil_workspace(self):
        """A workspace cannot be imported from AnVIL if we do not have access."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=404,  # successful response code.
            json={
                "message": billing_project_name
                + "/"
                + workspace_name
                + " does not exist or you do not have permission to use it"
            },
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            models.Workspace.anvil_import(billing_project_name, workspace_name)
        # Check workspace values.
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_workspace_exists_in_django_db(self):
        workspace = factories.WorkspaceFactory.create()
        # No API calls should be made.
        with self.assertRaises(exceptions.AnVILAlreadyImported):
            models.Workspace.anvil_import(
                workspace.billing_project.name, workspace.name
            )
        # No additional objects were created.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        self.assertEqual(models.Workspace.objects.count(), 1)

    def test_anvil_import_api_internal_error(self):
        """No workspaces are created if there is an internal error from the AnVIL API."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=500,  # successful response code.
            json={"message": "error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            models.Workspace.anvil_import(billing_project_name, workspace_name)
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_api_error_other(self):
        """No workspaces are created if there is some other error from the AnVIL API."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=499,  # successful response code.
            json={"message": "error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            models.Workspace.anvil_import(billing_project_name, workspace_name)
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_invalid_billing_project_name(self):
        """No workspaces are created if the billing project name is invalid."""
        with self.assertRaises(ValidationError):
            models.Workspace.anvil_import("test billing project", "test-workspace")
        # # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_invalid_workspace_name(self):
        """No workspaces are created if the workspace name is invalid."""
        with self.assertRaises(ValidationError):
            models.Workspace.anvil_import("test-billing-project", "test workspace")
        # # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_different_billing_project_same_workspace_name(self):
        """Can import a workspace in a different billing project with the same name as another workspace."""
        workspace_name = "test-workspace"
        other_billing_project = factories.BillingProjectFactory.create(
            name="billing-project-1"
        )
        factories.WorkspaceFactory.create(
            billing_project=other_billing_project, name=workspace_name
        )
        billing_project_name = "billing-project-2"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        workspace = models.Workspace.anvil_import(billing_project_name, workspace_name)
        # A billing project was created and that the previous billing project exists.
        self.assertEqual(models.BillingProject.objects.count(), 2)
        billing_project = models.BillingProject.objects.latest("pk")
        self.assertEqual(billing_project.name, billing_project_name)
        # Check workspace.
        self.assertEqual(models.Workspace.objects.count(), 2)
        self.assertEqual(workspace.billing_project, billing_project)
        self.assertEqual(workspace.name, workspace_name)

    def test_anvil_import_same_billing_project_different_workspace_name(self):
        """Can import a workspace in the same billing project with with a different name as another workspace."""
        workspace_name = "test-workspace-2"
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(
            billing_project=billing_project, name="test-workspace-1"
        )
        responses.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        workspace = models.Workspace.anvil_import(billing_project.name, workspace_name)
        # No new billing projects were created.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        # Check workspace.
        self.assertEqual(models.Workspace.objects.count(), 2)
        self.assertEqual(workspace.billing_project, billing_project)
        self.assertEqual(workspace.name, workspace_name)


class GroupGroupMembershipAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        parent_group = factories.GroupFactory(name="parent-group")
        child_group = factories.GroupFactory(name="child-group")
        self.object = factories.GroupGroupMembershipFactory(
            parent_group=parent_group,
            child_group=child_group,
            role=models.GroupGroupMembership.MEMBER,
        )
        self.url = (
            self.entry_point
            + "/api/groups/parent-group/MEMBER/child-group@firecloud.org"
        )

    def test_anvil_create_successful(self):
        responses.add(responses.PUT, self.url, status=204)
        self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_403(self):
        responses.add(
            responses.PUT, self.url, status=403, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_404(self):
        responses.add(
            responses.PUT, self.url, status=404, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_500(self):
        responses.add(
            responses.PUT, self.url, status=500, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_other(self):
        responses.add(
            responses.PUT, self.url, status=499, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_successful(self):
        responses.add(responses.DELETE, self.url, status=204)
        self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_403(self):
        responses.add(
            responses.DELETE, self.url, status=403, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_404(self):
        responses.add(
            responses.DELETE, self.url, status=404, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_500(self):
        responses.add(
            responses.DELETE, self.url, status=500, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_other(self):
        responses.add(
            responses.DELETE, self.url, status=499, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)


class GroupAccountMembershipAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        group = factories.GroupFactory(name="test-group")
        account = factories.AccountFactory(email="test-account@example.com")
        self.object = factories.GroupAccountMembershipFactory(
            group=group, account=account, role=models.GroupAccountMembership.MEMBER
        )
        self.url = (
            self.entry_point + "/api/groups/test-group/MEMBER/test-account@example.com"
        )

    def test_anvil_create_successful(self):
        responses.add(responses.PUT, self.url, status=204)
        self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_403(self):
        responses.add(
            responses.PUT, self.url, status=403, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_404(self):
        responses.add(
            responses.PUT, self.url, status=404, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_500(self):
        responses.add(
            responses.PUT, self.url, status=500, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_other(self):
        responses.add(
            responses.PUT, self.url, status=499, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_successful(self):
        responses.add(
            responses.DELETE, self.url, status=204, json={"message": "mock message"}
        )
        self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_403(self):
        responses.add(
            responses.DELETE, self.url, status=403, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_404(self):
        responses.add(
            responses.DELETE, self.url, status=404, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_500(self):
        responses.add(
            responses.DELETE, self.url, status=500, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_other(self):
        responses.add(
            responses.DELETE, self.url, status=499, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)


class WorkspaceGroupAccessAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project=billing_project, name="test-workspace"
        )
        group = factories.GroupFactory.create(name="test-group")
        self.object = factories.WorkspaceGroupAccessFactory(
            workspace=workspace, group=group, access=models.WorkspaceGroupAccess.READER
        )
        self.url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        self.headers = {"Content-type": "application/json"}
        self.data_add = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.data_delete = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]

    def test_anvil_create_or_update_successful(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_or_update_unsuccessful_400(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=400,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_or_update_unsuccessful_workspace_not_found(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=404,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_or_update_unsuccessful_internal_error(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=500,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_or_update_unsuccessful_other(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=499,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_successful(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_400(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=400,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_workspace_not_found(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=404,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_internal_error(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=500,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_other(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=499,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)
