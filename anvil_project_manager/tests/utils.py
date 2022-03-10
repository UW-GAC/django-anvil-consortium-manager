from unittest import mock

import google.auth.credentials
import google.auth.transport.requests
import responses


class AnVILAPIMockTestMixin:
    """Base class for AnVIL API mocked tests."""

    entry_point = "https://api.firecloud.org"

    def setUp(self):
        """Set up class -- mock credentials for AuthorizedSession."""
        super().setUp()
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

    def tearDown(self):
        super().tearDown()
        responses.stop()
        responses.reset()
