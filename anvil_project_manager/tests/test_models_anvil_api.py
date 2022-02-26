from unittest import mock

from django.test import TestCase

from .. import anvil_api
from . import factories


class GroupAnVILAPIMockTest(TestCase):
    def get_mock_response(self, status_code, message="mock message"):
        """Create a mock response."""
        return mock.Mock(status_code=status_code, json=lambda: {"message": message})

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_group_exists(self, mock_get):
        group = factories.GroupFactory()
        mock_get.return_value = self.get_mock_response(200)
        self.assertIs(group.anvil_exists(), True)
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_group_does_not_exist(self, mock_get):
        group = factories.GroupFactory()
        mock_get.return_value = self.get_mock_response(404)
        self.assertIs(group.anvil_exists(), False)
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_forbidden(self, mock_get):
        group = factories.GroupFactory()
        mock_get.return_value = self.get_mock_response(403)
        with self.assertRaises(anvil_api.AnVILAPIError403):
            group.anvil_exists()
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.get")
    def test_anvil_exists_internal_error(self, mock_get):
        group = factories.GroupFactory()
        mock_get.return_value = self.get_mock_response(500)
        with self.assertRaises(anvil_api.AnVILAPIError500):
            group.anvil_exists()
        mock_get.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_successful(self, mock_post):
        group = factories.GroupFactory()
        mock_post.return_value = self.get_mock_response(201)
        group.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_already_exists(self, mock_post):
        """Returns documented response code when a group already exists. Unfortunately the actual return code is 201."""
        group = factories.GroupFactory()
        mock_post.return_value = self.get_mock_response(409)
        with self.assertRaises(anvil_api.AnVILAPIError409):
            group.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_internal_error(self, mock_post):
        group = factories.GroupFactory()
        mock_post.return_value = self.get_mock_response(500)
        with self.assertRaises(anvil_api.AnVILAPIError500):
            group.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.post")
    def test_anvil_create_other(self, mock_post):
        group = factories.GroupFactory()
        mock_post.return_value = self.get_mock_response(404)
        with self.assertRaises(anvil_api.AnVILAPIError):
            group.anvil_create()
        mock_post.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_existing_group(self, mock_delete):
        group = factories.GroupFactory()
        mock_delete.return_value = self.get_mock_response(204)
        group.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_forbidden(self, mock_delete):
        group = factories.GroupFactory()
        mock_delete.return_value = self.get_mock_response(403)
        with self.assertRaises(anvil_api.AnVILAPIError403):
            group.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_not_found(self, mock_delete):
        group = factories.GroupFactory()
        mock_delete.return_value = self.get_mock_response(404)
        with self.assertRaises(anvil_api.AnVILAPIError404):
            group.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_in_use(self, mock_delete):
        group = factories.GroupFactory()
        mock_delete.return_value = self.get_mock_response(409)
        with self.assertRaises(anvil_api.AnVILAPIError409):
            group.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )

    @mock.patch("google.auth.transport.requests.AuthorizedSession.delete")
    def test_anvil_delete_other(self, mock_delete):
        group = factories.GroupFactory()
        mock_delete.return_value = self.get_mock_response(499)
        with self.assertRaises(anvil_api.AnVILAPIError):
            group.anvil_delete()
        mock_delete.assert_called_once_with(
            "https://api.firecloud.org/api/groups/" + group.name
        )
