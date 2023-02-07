from unittest import mock

import google.auth.credentials
import google.auth.transport.requests
import responses
from faker import Faker

from ..anvil_api import AnVILAPIClient

fake = Faker()


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
        self.anvil_response_mock = responses.RequestsMock(
            assert_all_requests_are_fired=True
        )
        self.anvil_response_mock.start()
        # Get an instance of the API client to access entry points?
        self.api_client = AnVILAPIClient()
        # Set the auth session service account email here, since some functions need it.
        self.service_account_email = fake.email()
        AnVILAPIClient().auth_session.credentials.service_account_email = (
            self.service_account_email
        )

    def tearDown(self):
        super().tearDown()
        self.anvil_response_mock.stop()
        self.anvil_response_mock.reset()
