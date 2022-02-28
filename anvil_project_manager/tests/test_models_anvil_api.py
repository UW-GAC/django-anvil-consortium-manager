from unittest import mock

from django.test import TestCase

from .. import anvil_api, models
from . import factories


class AnVILAPIMockTest(TestCase):
    """Base class for AnVIL API mocked tests."""

    def get_mock_response(self, status_code, message="mock message"):
        """Create a mock response."""
        return mock.Mock(status_code=status_code, json=lambda: {"message": message})


class GroupAnVILAPIMockTest(AnVILAPIMockTest):
    def setUp(self, *args, **kwargs):
        self.object = factories.GroupFactory()

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_does_exist(self, mock_get):
        mock_get.return_value = self.get_mock_response(200)
        self.assertIs(self.object.anvil_exists(), True)
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_does_not_exist(self, mock_get):
        mock_get.return_value = self.get_mock_response(404)
        self.assertIs(self.object.anvil_exists(), False)
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_forbidden(self, mock_get):
        mock_get.return_value = self.get_mock_response(403)
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_exists()
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_internal_error(self, mock_get):
        mock_get.return_value = self.get_mock_response(500)
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_exists()
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_successful(self, mock_post):
        mock_post.return_value = self.get_mock_response(201)
        self.object.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_already_exists(self, mock_post):
        """Returns documented response code when a group already exists. Unfortunately the actual return code is 201."""
        mock_post.return_value = self.get_mock_response(409)
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_internal_error(self, mock_post):
        mock_post.return_value = self.get_mock_response(500)
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_other(self, mock_post):
        mock_post.return_value = self.get_mock_response(404)
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_existing(self, mock_delete):
        mock_delete.return_value = self.get_mock_response(204)
        self.object.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_forbidden(self, mock_delete):
        mock_delete.return_value = self.get_mock_response(403)
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_not_found(self, mock_delete):
        mock_delete.return_value = self.get_mock_response(404)
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_in_use(self, mock_delete):
        mock_delete.return_value = self.get_mock_response(409)
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_other(self, mock_delete):
        mock_delete.return_value = self.get_mock_response(499)
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + self.object.name
        )


class WorkspaceAnVILAPIMockTest(AnVILAPIMockTest):
    def setUp(self, *args, **kwargs):
        self.object = factories.WorkspaceFactory()

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_does_exist(self, mock_get):
        mock_get.return_value = self.get_mock_response(200)
        self.assertIs(self.object.anvil_exists(), True)
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces/"
            + self.object.billing_project.name
            + "/"
            + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_does_not_exist(self, mock_get):
        mock_get.return_value = self.get_mock_response(404)
        self.assertIs(self.object.anvil_exists(), False)
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces/"
            + self.object.billing_project.name
            + "/"
            + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_forbidden(self, mock_get):
        mock_get.return_value = self.get_mock_response(403)
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_exists()
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces/"
            + self.object.billing_project.name
            + "/"
            + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_internal_error(self, mock_get):
        mock_get.return_value = self.get_mock_response(500)
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_exists()
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces/"
            + self.object.billing_project.name
            + "/"
            + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_successful(self, mock_post):
        mock_post.return_value = self.get_mock_response(201)
        self.object.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces",
            json={
                "namespace": self.object.billing_project.name,
                "name": self.object.name,
                "attributes": {},
            },
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_bad_request(self, mock_post):
        """Returns documented response code when workspace already exists."""
        mock_post.return_value = self.get_mock_response(400)
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces",
            json={
                "namespace": self.object.billing_project.name,
                "name": self.object.name,
                "attributes": {},
            },
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_forbidden(self, mock_post):
        """Returns documented response code when a workspace can't be created."""
        mock_post.return_value = self.get_mock_response(403)
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces",
            json={
                "namespace": self.object.billing_project.name,
                "name": self.object.name,
                "attributes": {},
            },
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_already_exists(self, mock_post):
        """Returns documented response code when a workspace already exists."""
        mock_post.return_value = self.get_mock_response(409)
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces",
            json={
                "namespace": self.object.billing_project.name,
                "name": self.object.name,
                "attributes": {},
            },
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_internal_error(self, mock_post):
        mock_post.return_value = self.get_mock_response(500)
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces",
            json={
                "namespace": self.object.billing_project.name,
                "name": self.object.name,
                "attributes": {},
            },
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_other(self, mock_post):
        mock_post.return_value = self.get_mock_response(404)
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces",
            json={
                "namespace": self.object.billing_project.name,
                "name": self.object.name,
                "attributes": {},
            },
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_existing(self, mock_delete):
        mock_delete.return_value = self.get_mock_response(202)
        self.object.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces/"
            + self.object.billing_project.name
            + "/"
            + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_forbidden(self, mock_delete):
        mock_delete.return_value = self.get_mock_response(403)
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces/"
            + self.object.billing_project.name
            + "/"
            + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_not_found(self, mock_delete):
        mock_delete.return_value = self.get_mock_response(404)
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces/"
            + self.object.billing_project.name
            + "/"
            + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_in_use(self, mock_delete):
        mock_delete.return_value = self.get_mock_response(500)
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces/"
            + self.object.billing_project.name
            + "/"
            + self.object.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_other(self, mock_delete):
        mock_delete.return_value = self.get_mock_response(499)
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces/"
            + self.object.billing_project.name
            + "/"
            + self.object.name
        )


class GroupGroupMembershipAnVILAPIMockTest(AnVILAPIMockTest):
    def setUp(self, *args, **kwargs):
        parent_group = factories.GroupFactory(name="parent-group")
        child_group = factories.GroupFactory(name="child-group")
        self.object = factories.GroupGroupMembershipFactory(
            parent_group=parent_group, child_group=child_group
        )


class WorkspaceGroupAccessAnVILAPIMockTest(AnVILAPIMockTest):
    def setUp(self, *args, **kwargs):
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

    @mock.patch("google.auth.transport.requests.AuthorizedSession.patch")
    def test_anvil_create_or_update_successful(self, mock_patch):
        mock_patch.return_value = self.get_mock_response(200)
        self.object.anvil_create_or_update()
        mock_patch.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false",  # noqa
            headers={"Content-type": "application/json"},
            data='[{"email": "test-group@firecloud.org", "accessLevel": "READER", "canShare": false, "canCompute": false}]',  # noqa
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.patch")
    def test_anvil_create_or_update_unsuccessful_400(self, mock_patch):
        mock_patch.return_value = self.get_mock_response(400)
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.object.anvil_create_or_update()
        mock_patch.assert_called_once()

    @mock.patch("google.auth.transport.requests.AuthorizedSession.patch")
    def test_anvil_create_or_update_unsuccessful_workspace_not_found(self, mock_patch):
        mock_patch.return_value = self.get_mock_response(404)
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create_or_update()
        mock_patch.assert_called_once()

    @mock.patch("google.auth.transport.requests.AuthorizedSession.patch")
    def test_anvil_create_or_update_unsuccessful_internal_error(self, mock_patch):
        mock_patch.return_value = self.get_mock_response(500)
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create_or_update()
        mock_patch.assert_called_once()

    @mock.patch("google.auth.transport.requests.AuthorizedSession.patch")
    def test_anvil_create_or_update_unsuccessful_other(self, mock_patch):
        mock_patch.return_value = self.get_mock_response(401)
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create_or_update()
        mock_patch.assert_called_once()

    @mock.patch("google.auth.transport.requests.AuthorizedSession.patch")
    def test_anvil_delete_successful(self, mock_patch):
        mock_patch.return_value = self.get_mock_response(200)
        self.object.anvil_delete()
        mock_patch.assert_called_once_with(
            "https://api.firecloud.org/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false",  # noqa
            headers={"Content-type": "application/json"},
            data='[{"email": "test-group@firecloud.org", "accessLevel": "NO ACCESS", "canShare": false, "canCompute": false}]',  # noqa
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.patch")
    def test_anvil_delete_unsuccessful_400(self, mock_patch):
        mock_patch.return_value = self.get_mock_response(400)
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.object.anvil_delete()
        mock_patch.assert_called_once()

    @mock.patch("google.auth.transport.requests.AuthorizedSession.patch")
    def test_anvil_delete_unsuccessful_workspace_not_found(self, mock_patch):
        mock_patch.return_value = self.get_mock_response(404)
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        mock_patch.assert_called_once()

    @mock.patch("google.auth.transport.requests.AuthorizedSession.patch")
    def test_anvil_delete_unsuccessful_internal_error(self, mock_patch):
        mock_patch.return_value = self.get_mock_response(500)
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()
        mock_patch.assert_called_once()

    @mock.patch("google.auth.transport.requests.AuthorizedSession.patch")
    def test_anvil_delete_unsuccessful_other(self, mock_patch):
        mock_patch.return_value = self.get_mock_response(401)
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        mock_patch.assert_called_once()
