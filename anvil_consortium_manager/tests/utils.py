from unittest import mock

import google.auth.credentials
import google.auth.transport.requests
import responses
from django import VERSION as DJANGO_VERSION
from django.test import TestCase as DjangoTestCase
from faker import Faker

from ..anvil_api import AnVILAPIClient

fake = Faker()


if DJANGO_VERSION >= (4, 2):
    TestCase = DjangoTestCase
else:
    # As of Django 4.2 TestCase.assertQuerysetEqual is deprecated and in favor of assertQuerySetEqual.
    # If we are running Django < 4.2, define assertQuerySetEqual, which calls self.assertQuerysetEqual.
    # consistent across all versions.
    class TestCase(DjangoTestCase):
        def assertQuerySetEqual(self, *args, **kwargs):
            return self.assertQuerysetEqual(*args, **kwargs)


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
