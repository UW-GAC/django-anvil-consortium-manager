from unittest import mock

import google.auth.credentials
import google.auth.transport.requests
import responses
from django.test import TestCase

from .. import anvil_api, models
from . import factories


class AnVILAPIMockTest(TestCase):
    """Base class for AnVIL API mocked tests."""

    entry_point = "https://api.firecloud.org"

    def setUp(self):
        """Set up class -- mock credentials for AuthorizedSession."""
        # Patch the module that checks credentials.
        # See Google's tests:
        # https://github.com/googleapis/google-api-python-client/blob/main/tests/test__auth.py
        self.credential_patcher = mock.patch.object(
            google.auth, "default", autospec=True
        )
        self.credential_patcher.start()
        self.addCleanup(self.credential_patcher.stop)
        self.credential_patcher.return_value = (
            mock.sentinel.credentials,
            mock.sentinel.project,
        )
        responses.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        responses.stop()
        responses.reset()

    # def get_mock_response(self, status_code, message="mock message"):
    #     """Create a mock response."""
    #     return mock.Mock(status_code=status_code, json=lambda: {"message": message})


class BillingProjectAnVILAPIMockTest(AnVILAPIMockTest):
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


class GroupAnVILAPIMockTest(AnVILAPIMockTest):
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


class WorkspaceAnVILAPIMockTest(AnVILAPIMockTest):
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


class GroupGroupMembershipAnVILAPIMockTest(AnVILAPIMockTest):
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


class GroupAccountMembershipAnVILAPIMockTest(AnVILAPIMockTest):
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


class WorkspaceGroupAccessAnVILAPIMockTest(AnVILAPIMockTest):
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
