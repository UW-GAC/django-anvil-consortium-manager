import responses
from django.core.cache import caches
from django.test import TestCase
from django.utils import timezone
from faker import Faker
from freezegun import freeze_time

from anvil_consortium_manager.tests.factories import BillingProjectFactory
from anvil_consortium_manager.tests.utils import AnVILAPIMockTestMixin

from ... import app_settings
from ..audit import billing_projects
from .utils import AuditCacheClearTestMixin

fake = Faker()


class BillingProjectAuditTest(AnVILAPIMockTestMixin, AuditCacheClearTestMixin, TestCase):
    """Tests for the BillingProject.anvil_audit method."""

    def get_api_url(self, billing_project_name):
        return self.api_client.rawls_entry_point + "/api/billing/v2/" + billing_project_name

    def get_api_json_response(self):
        return {
            "roles": ["User"],
        }

    def test_anvil_audit_no_billing_projects(self):
        """anvil_audit works correct if there are no billing projects in the app."""
        audit_results = billing_projects.BillingProjectAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_billing_project_no_errors(self):
        """anvil_audit works correct if one billing project exists in the app and in AnVIL."""
        billing_project = BillingProjectFactory.create(has_app_as_user=True)
        api_url = self.get_api_url(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = billing_projects.BillingProjectAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(billing_project)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_billing_project_not_on_anvil(self):
        """anvil_audit raises exception with one billing project exists in the app but not on AnVIL."""
        billing_project = BillingProjectFactory.create(has_app_as_user=True)
        api_url = self.get_api_url(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        audit_results = billing_projects.BillingProjectAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(billing_project)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_two_billing_projects_no_errors(self):
        """anvil_audit returns None if there are two billing projects and both exist on AnVIL."""
        billing_project_1 = BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=200,
            json=self.get_api_json_response(),
        )
        billing_project_2 = BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = billing_projects.BillingProjectAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(billing_project_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(billing_project_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_billing_projects_first_not_on_anvil(self):
        """anvil_audit raises exception if two billing projects exist in the app but the first is not on AnVIL."""
        billing_project_1 = BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        billing_project_2 = BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = billing_projects.BillingProjectAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(billing_project_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(billing_project_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_billing_projects_both_missing(self):
        """anvil_audit raises exception if there are two billing projects that exist in the app but not in AnVIL."""
        billing_project_1 = BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        billing_project_2 = BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=404,
            json={"message": "other error"},
        )
        audit_results = billing_projects.BillingProjectAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(billing_project_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(billing_project_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_ignore_not_has_app_has_user(self):
        """anvil_audit does not check AnVIL about billing projects that do not have the app as a user."""
        BillingProjectFactory.create(has_app_as_user=False)
        # No API calls made.
        audit_results = billing_projects.BillingProjectAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_result_is_cached_if_requested(self):
        """Audit result is cached if specified."""
        cache_timestamp = timezone.now() - timezone.timedelta(days=1)
        with freeze_time(cache_timestamp):
            audit_results = billing_projects.BillingProjectAudit()
            audit_results.run_audit(cache=True)
        cached_audit_result = caches[app_settings.AUDIT_CACHE].get("billing_project_audit_results")
        self.assertIsNotNone(cached_audit_result)
        self.assertIsInstance(cached_audit_result, billing_projects.BillingProjectAudit)
        self.assertEqual(cached_audit_result.timestamp, cache_timestamp)

    def test_result_is_not_cached_if_not_requested(self):
        """Audit result is not cached if not specified."""
        cache_timestamp = timezone.now() - timezone.timedelta(days=1)
        with freeze_time(cache_timestamp):
            audit_results = billing_projects.BillingProjectAudit()
            audit_results.run_audit(cache=False)
        cached_audit_result = caches[app_settings.AUDIT_CACHE].get("billing_project_audit_results")
        self.assertIsNone(cached_audit_result)
