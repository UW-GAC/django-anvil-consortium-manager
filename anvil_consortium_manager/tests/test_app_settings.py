from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.test.utils import override_settings

from .. import app_settings


class TestAppSettings(TestCase):
    def test_api_service_account_file(self):
        # Using test settings.
        self.assertEqual(app_settings.API_SERVICE_ACCOUNT_FILE, "foo")

    @override_settings(ANVIL_API_SERVICE_ACCOUNT_FILE=None)
    def test_api_service_account_file_none(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured, "ANVIL_API_SERVICE_ACCOUNT_FILE is required in settings.py"
        ):
            app_settings.API_SERVICE_ACCOUNT_FILE

    def test_workspace_adapters(self):
        # Using test settings.
        self.assertEqual(
            app_settings.WORKSPACE_ADAPTERS, ["anvil_consortium_manager.adapters.default.DefaultWorkspaceAdapter"]
        )

    @override_settings(ANVIL_WORKSPACE_ADAPTERS=None)
    def test_workspace_adapters_none(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "must specify at least one adapter"):
            app_settings.WORKSPACE_ADAPTERS

    @override_settings(ANVIL_WORKSPACE_ADAPTERS=[])
    def test_workspace_adapters_empty_array(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "must specify at least one adapter"):
            app_settings.WORKSPACE_ADAPTERS

    @override_settings(
        ANVIL_WORKSPACE_ADAPTERS=[
            "anvil_consortium_manager.adapters.default.DefaultWorkspaceAdapter",
            "anvil_consortium_manager.tests.test_app.adapters.TestWorkspaceAdapter",
        ]
    )
    def test_workspace_adapters_multiple(self):
        adapters = app_settings.WORKSPACE_ADAPTERS
        self.assertEqual(len(adapters), 2)
        self.assertIn("anvil_consortium_manager.adapters.default.DefaultWorkspaceAdapter", adapters)
        self.assertIn("anvil_consortium_manager.tests.test_app.adapters.TestWorkspaceAdapter", adapters)

    def test_account_verify_notification_email(self):
        self.assertEqual(app_settings.ACCOUNT_VERIFY_NOTIFICATION_EMAIL, None)

    @override_settings(ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL="foo@example.com")
    def test_account_verify_notification_email_custom(self):
        self.assertEqual(app_settings.ACCOUNT_VERIFY_NOTIFICATION_EMAIL, "foo@example.com")

    def test_account_adapter(self):
        self.assertEqual(
            app_settings.ACCOUNT_ADAPTER, "anvil_consortium_manager.adapters.default.DefaultAccountAdapter"
        )

    @override_settings(ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.test_app.adapters.TestAccountAdapter")
    def test_account_adapter_custom(self):
        self.assertEqual(app_settings.ACCOUNT_ADAPTER, "anvil_consortium_manager.test_app.adapters.TestAccountAdapter")
