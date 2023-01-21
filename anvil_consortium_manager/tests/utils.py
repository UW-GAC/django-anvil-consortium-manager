from unittest import mock

import google.auth.credentials
import google.auth.transport.requests
import responses

from ..anvil_api import AnVILAPIClient


class AnVILAPIMockTestMixin:
    """Base class for AnVIL API mocked tests."""

    def setUp(self):
        """Set up class -- mock credentials for AuthorizedSession."""
        super().setUp()
        # Patch the module that checks credentials.
        # See Google's tests:
        # https://github.com/googleapis/google-api-python-client/blob/main/tests/test__auth.py
        self.credential_patcher = mock.patch.object(
            google.oauth2.service_account.Credentials,
            "from_service_account_file",
            autospec=True,
        )
        self.credential_patcher.start()
        self.addCleanup(self.credential_patcher.stop)
        self.credential_patcher.return_value = (
            mock.sentinel.credentials,
            mock.sentinel.project,
        )
        self.response_mock = responses.RequestsMock(assert_all_requests_are_fired=True)
        self.response_mock.start()
        # Get an instance of the API client to access entry points?
        self.api_client = AnVILAPIClient()

    def tearDown(self):
        super().tearDown()
        self.response_mock.stop()
        self.response_mock.reset()
