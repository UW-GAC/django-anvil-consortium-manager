from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import CookieStorage
from django.test import Client, RequestFactory, TestCase, override_settings

from anvil_consortium_manager.tests.factories import AccountFactory

from ..audit.accounts import AccountAudit
from ..audit.base import ModelInstanceResult
from ..utils import AuditCheckConfig
from .utils import AuditCacheClearTestMixin

User = get_user_model()

TEST_AUDITS = [AuditCheckConfig(AccountAudit, "anvil_consortium_manager:auditor:accounts:review")]
INVALID_AUDITS = [AuditCheckConfig(AccountAudit, "BAD_URL_NAME")]


# We enable the checking of the audit cache for just these tests
# otherwise they happen on all test logins and
@override_settings(ANVIL_CHECK_AUDIT_CACHE_ON_LOGIN=True)
class CheckAnvilAuditStatusTest(AuditCacheClearTestMixin, TestCase):
    """Tests for the check_cached_anvil_audit utility."""

    def setUp(self):
        self.client = Client()
        # Create a test user in the database
        self.user = User.objects.create_user(username="testuser", password="securepassword123")
        # Create a staff user
        self.staff_user = User.objects.create_user(
            username="teststaffuser",
            password="securepassword345",
            is_staff=True,
        )

    @patch("anvil_consortium_manager.auditor.signals.check_cached_anvil_audits")
    def test_check_run_for_staff(self, mock_handler):
        """Verify the check_cached_anvil_audits function is called for staff users"""
        self.client.force_login(self.staff_user)
        mock_handler.assert_called_once()

    @patch("anvil_consortium_manager.auditor.signals.check_cached_anvil_audits")
    @override_settings(ANVIL_CHECK_AUDIT_CACHE_ON_LOGIN=False)
    def test_check_on_login_setting(self, mock_handler):
        """Verify the check_cached_anvil_audits function is not called when anvil setting is false"""
        self.client.force_login(self.staff_user)
        mock_handler.assert_not_called()

    @patch("anvil_consortium_manager.auditor.signals.check_cached_anvil_audits")
    def test_check_not_run_for_non_staff(self, mock_handler):
        """Verify the check_cached_anvil_audits function is not called for NON staff users"""
        self.client.force_login(self.user)
        mock_handler.assert_not_called()

    def test_no_cache_reported(self):
        """Verify the check_cached_anvil_audits function reports all instances of missing cached audit results"""
        factory = RequestFactory()
        request = factory.get("/")

        # Due to the bare request the RequestFactory creates
        # we use a self-contained messages storage system
        request._messages = CookieStorage(request)

        # Directly fire Django's user_logged_in signal
        user_logged_in.send(sender=self.staff_user.__class__, request=request, user=self.staff_user)

        messages = [m.message for m in get_messages(request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]).count("No cached audit results found for"), 4)
        # self.assertEqual("No cached audit results found for", str(messages[0]))

    def test_bad_messages_framework_logs(self):
        """Verify the check_cached_anvil_audits function reports all instances of missing cached audit results"""
        factory = RequestFactory()
        request = factory.get("/")

        # Due to the bare request the RequestFactory creates
        # we use a self-contained messages storage system
        # request._messages = CookieStorage(request)

        # Directly fire Django's user_logged_in signal
        with self.assertLogs("anvil_consortium_manager.auditor.utils", level="ERROR") as log_context:
            user_logged_in.send(sender=self.staff_user.__class__, request=request, user=self.staff_user)

        self.assertEqual(len(log_context.output), 1)
        self.assertIn("[check_cached_anvil_audits] Could not notify", log_context.output[0])

    @patch("anvil_consortium_manager.auditor.utils.AUDITS_TO_CHECK", TEST_AUDITS)
    def test_cached_audit_not_okay(self):
        """Verify the check_cached_anvil_audits function reports when an audit is not ok"""
        factory = RequestFactory()
        request = factory.get("/")

        # Due to the bare request the RequestFactory creates
        # we use a self-contained messages storage system
        request._messages = CookieStorage(request)

        # Create a non-okay audit result and cache it.
        audit_results = AccountAudit()
        model_instance_result = ModelInstanceResult(AccountFactory())
        model_instance_result.add_error("foo")
        audit_results.add_result(model_instance_result)
        audit_results.cache()

        # Directly fire Django's user_logged_in signal
        user_logged_in.send(sender=self.staff_user.__class__, request=request, user=self.staff_user)

        messages = [m.message for m in get_messages(request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("Audit AccountAudit contains errors", str(messages[0]))

    @patch("anvil_consortium_manager.auditor.utils.AUDITS_TO_CHECK", TEST_AUDITS)
    def test_all_audits_okay_no_messages(self):
        """Verify the check_cached_anvil_audits function does not alert when audit is okay and in cache"""
        factory = RequestFactory()
        request = factory.get("/")

        # Due to the bare request the RequestFactory creates
        # we use a self-contained messages storage system
        request._messages = CookieStorage(request)

        # Create a non-okay audit result and cache it.
        audit_results = AccountAudit()
        model_instance_result = ModelInstanceResult(AccountFactory())
        audit_results.add_result(model_instance_result)
        audit_results.cache()

        # Directly fire Django's user_logged_in signal
        user_logged_in.send(sender=self.staff_user.__class__, request=request, user=self.staff_user)
        # cached audit is okay, no messages expected
        messages = [m.message for m in get_messages(request)]
        self.assertEqual(len(messages), 0)

    @patch("anvil_consortium_manager.auditor.utils.AUDITS_TO_CHECK", INVALID_AUDITS)
    def test_cache_check_exception(self):
        """Test that audit cache check logs error on exception but does not block user"""
        factory = RequestFactory()
        request = factory.get("/")

        # Due to the bare request the RequestFactory creates
        # we use a self-contained messages storage system
        request._messages = CookieStorage(request)

        # Directly fire Django's user_logged_in signal
        with self.assertLogs("anvil_consortium_manager.auditor.utils", level="ERROR") as log_context:
            user_logged_in.send(sender=self.staff_user.__class__, request=request, user=self.staff_user)
        self.assertEqual(len(log_context.output), 1)
        self.assertIn("[check_anvil_audits] Encountered exception", log_context.output[0])
