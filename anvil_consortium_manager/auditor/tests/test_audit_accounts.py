import responses
from django.core.cache import caches
from django.test import TestCase
from django.utils import timezone
from faker import Faker
from freezegun import freeze_time

from anvil_consortium_manager.tests.factories import AccountFactory
from anvil_consortium_manager.tests.utils import AnVILAPIMockTestMixin

from ... import app_settings
from ..audit import accounts
from .utils import AuditCacheClearTestMixin

fake = Faker()


class AccountAuditTest(AnVILAPIMockTestMixin, AuditCacheClearTestMixin, TestCase):
    """Tests for the Account.anvil_audit method."""

    def get_api_url(self, email):
        return self.api_client.sam_entry_point + "/api/users/v1/" + email

    def get_api_json_response(self, email):
        id = fake.bothify(text="#" * 21)
        return {
            "googleSubjectId": id,
            "userEmail": email,
            "userSubjectId": id,
        }

    def test_anvil_audit_no_accounts(self):
        """anvil_audit works correct if there are no Accounts in the app."""
        audit_results = accounts.AccountAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_account_no_errors(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        account = AccountFactory.create()
        api_url = self.get_api_url(account.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=self.get_api_json_response(account.email),
        )
        audit_results = accounts.AccountAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(account)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_account_not_on_anvil(self):
        """anvil_audit raises exception if one billing project exists in the app but not on AnVIL."""
        account = AccountFactory.create()
        api_url = self.get_api_url(account.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        audit_results = accounts.AccountAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(account)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_two_accounts_no_errors(self):
        """anvil_audit returns None if if two accounts exist in both the app and AnVIL."""
        account_1 = AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=200,
            json=self.get_api_json_response(account_1.email),
        )
        account_2 = AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(account_2.email),
        )
        audit_results = accounts.AccountAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(account_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(account_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_accounts_first_not_on_anvil(self):
        """anvil_audit raises exception if two accounts exist in the app but the first is not not on AnVIL."""
        account_1 = AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        account_2 = AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(account_2.email),
        )
        audit_results = accounts.AccountAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(account_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(account_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_accounts_both_missing(self):
        """anvil_audit raises exception if there are two accounts that exist in the app but not in AnVIL."""
        account_1 = AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        account_2 = AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=404,
            json={"message": "other error"},
        )
        audit_results = accounts.AccountAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(account_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(account_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_deactivated_account(self):
        """anvil_audit does not check AnVIL about accounts that are deactivated."""
        account = AccountFactory.create()
        account.deactivate()
        # No API calls made.
        audit_results = accounts.AccountAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_result_is_cached_if_requested(self):
        """Audit result is cached if specified."""
        cache_timestamp = timezone.now() - timezone.timedelta(days=1)
        with freeze_time(cache_timestamp):
            audit_results = accounts.AccountAudit()
            audit_results.run_audit(cache=True)
        cached_audit_result = caches[app_settings.AUDIT_CACHE].get("account_audit_results")
        self.assertIsNotNone(cached_audit_result)
        self.assertIsInstance(cached_audit_result, accounts.AccountAudit)
        self.assertEqual(cached_audit_result.timestamp, cache_timestamp)
