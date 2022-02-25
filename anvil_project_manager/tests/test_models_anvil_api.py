from unittest import mock

from django.test import TestCase

from .. import anvil_api
from . import factories


class GroupAnVILAPIMockTest(TestCase):
    def setUp(self):
        """Setup method to mock requests."""
        super().setUp()
        # Mock the superclass get method, not my subclass get method. This lets us test that exceptions are raised.
        patcher = mock.patch("google.auth.transport.requests.AuthorizedSession.get")
        self.mock_get = patcher.start()
        self.addCleanup(patcher.stop)

    def set_mock_get(self, status_code, json_message=""):
        """Method to set the mock response status code and json data."""
        self.mock_get.return_value = mock.Mock(
            status_code=status_code, json=lambda: {"message": json_message}
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
