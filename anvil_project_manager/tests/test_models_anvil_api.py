from unittest import mock

from django.test import TestCase

from .. import anvil_api
from . import factories


class GroupAnVILAPIMockTest(TestCase):
    def setUp(self):
        """Setup method to mock requests."""
        super().setUp()
        # Mock the superclass get method, not my subclass get method. This lets us test that exceptions are raised.
        # Get requests.
        get_patcher = mock.patch("google.auth.transport.requests.AuthorizedSession.get")
        self.mock_get = get_patcher.start()
        self.addCleanup(get_patcher.stop)
        # Post requests.
        post_patcher = mock.patch(
            "google.auth.transport.requests.AuthorizedSession.post"
        )
        self.mock_post = post_patcher.start()
        self.addCleanup(post_patcher.stop)

    def set_mock_get(self, status_code):
        """Set the mock response status code and json message of a GET request."""
        self.mock_get.return_value = mock.Mock(
            status_code=status_code, json=lambda: {"message": "mock get message"}
        )

    def set_mock_post(self, status_code):
        """Set the mock response status code and json message of a POST request."""
        self.mock_post.return_value = mock.Mock(
            status_code=status_code, json=lambda: {"message": "mock post message"}
        )

    def test_anvil_exists_group_exists(self):
        group = factories.GroupFactory()
        # self.mock_get.return_value = mock.Mock(status_code = 200, json=lambda: {})
        self.set_mock_get(200)
        self.assertIs(group.anvil_exists(), True)
        self.mock_get.assert_called_once()

    def test_anvil_exists_group_does_not_exist(self):
        group = factories.GroupFactory()
        # self.mock_get.return_value = mock.Mock(status_code = 200, json=lambda: {})
        self.set_mock_get(404)
        self.assertIs(group.anvil_exists(), False)
        self.mock_get.assert_called_once()

    def test_anvil_exists_forbidden(self):
        group = factories.GroupFactory()
        self.set_mock_get(403)
        with self.assertRaises(anvil_api.AnVILAPIError403):
            group.anvil_exists()
        self.mock_get.assert_called_once()

    def test_anvil_exists_internal_error(self):
        group = factories.GroupFactory()
        self.set_mock_get(500)
        with self.assertRaises(anvil_api.AnVILAPIError500):
            group.anvil_exists()
        self.mock_get.assert_called_once()

    def test_anvil_create_successful(self):
        group = factories.GroupFactory()
        self.set_mock_post(201)
        group.anvil_create()
        self.mock_post.assert_called_once()

    def test_anvil_create_already_exists(self):
        """Returns documented response code when a group already exists. Unfortunately the actual return code is 201."""
        group = factories.GroupFactory()
        self.set_mock_post(409)
        with self.assertRaises(anvil_api.AnVILAPIError409):
            group.anvil_create()
        self.mock_post.assert_called_once()

    def test_anvil_create_internal_error(self):
        group = factories.GroupFactory()
        self.set_mock_post(500)
        with self.assertRaises(anvil_api.AnVILAPIError500):
            group.anvil_create()
        self.mock_post.assert_called_once()

    def test_anvil_create_other(self):
        group = factories.GroupFactory()
        self.set_mock_post(404)
        with self.assertRaises(anvil_api.AnVILAPIError):
            group.anvil_create()
        self.mock_post.assert_called_once()
