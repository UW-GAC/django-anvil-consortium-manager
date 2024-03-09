import responses
from django.test import TestCase
from faker import Faker

from .. import exceptions, models
from ..audit import audit
from . import api_factories, factories
from .utils import AnVILAPIMockTestMixin

fake = Faker()


class ModelInstanceResultTest(TestCase):
    def test_init(self):
        """Constructor works as expected."""
        obj = factories.AccountFactory.create()
        result = audit.ModelInstanceResult(obj)
        self.assertEqual(result.model_instance, obj)
        self.assertEqual(result.errors, set())

    def test_str(self):
        """__str__ method works as expected."""
        obj = factories.AccountFactory.create()
        result = audit.ModelInstanceResult(obj)
        self.assertEqual(str(result), (str(obj)))

    def test_eq_no_errors(self):
        """__eq__ method works as expected when there are no errors."""
        obj = factories.AccountFactory.create()
        result_1 = audit.ModelInstanceResult(obj)
        result_2 = audit.ModelInstanceResult(obj)
        self.assertEqual(result_1, result_2)

    def test_eq_errors(self):
        """__eq__ method works as expected when there are errors."""
        obj = factories.AccountFactory.create()
        result_1 = audit.ModelInstanceResult(obj)
        result_1.add_error("foo")
        result_2 = audit.ModelInstanceResult(obj)
        self.assertNotEqual(result_1, result_2)
        result_2.add_error("foo")
        self.assertEqual(result_1, result_2)

    def test_add_error(self):
        """add_error method works as expected."""
        obj = factories.AccountFactory.create()
        result = audit.ModelInstanceResult(obj)
        result.add_error("foo")
        self.assertEqual(result.errors, set(["foo"]))
        result.add_error("bar")
        self.assertEqual(result.errors, set(["foo", "bar"]))

    def test_add_error_duplicate(self):
        """can add a second, duplicate error without error."""
        obj = factories.AccountFactory.create()
        result = audit.ModelInstanceResult(obj)
        result.add_error("foo")
        self.assertEqual(result.errors, set(["foo"]))
        result.add_error("foo")
        self.assertEqual(result.errors, set(["foo"]))

    def test_ok_no_errors(self):
        """ok method returns True when there are no errors."""
        obj = factories.AccountFactory.create()
        result = audit.ModelInstanceResult(obj)
        self.assertTrue(result.ok())

    def test_ok_errors(self):
        """ok method returns False when there are errors."""
        obj = factories.AccountFactory.create()
        result = audit.ModelInstanceResult(obj)
        result.add_error("foo")
        self.assertFalse(result.ok())


class NotInAppResultTest(TestCase):
    def test_init(self):
        """Constructor works as expected."""
        result = audit.NotInAppResult("foo bar")
        self.assertEqual(result.record, "foo bar")

    def test_str(self):
        """__str__ method works as expected."""
        result = audit.NotInAppResult("foo bar")
        self.assertEqual(str(result), "foo bar")

    def test_eq(self):
        """__eq__ method works as expected."""
        result = audit.NotInAppResult("foo")
        self.assertEqual(audit.NotInAppResult("foo"), result)
        self.assertNotEqual(audit.NotInAppResult("bar"), result)


class VerifiedTableTest(TestCase):
    def test_zero_rows(self):
        results = []
        table = audit.VerifiedTable(results)
        self.assertEqual(len(table.rows), 0)

    def test_one_row(self):
        results = [audit.ModelInstanceResult(factories.AccountFactory())]
        table = audit.VerifiedTable(results)
        self.assertEqual(len(table.rows), 1)

    def test_two_rows(self):
        results = [
            audit.ModelInstanceResult(factories.AccountFactory()),
            audit.ModelInstanceResult(factories.AccountFactory()),
        ]
        table = audit.VerifiedTable(results)
        self.assertEqual(len(table.rows), 2)


class ErrorTableTest(TestCase):
    def test_zero_rows(self):
        results = []
        table = audit.ErrorTable(results)
        self.assertEqual(len(table.rows), 0)

    def test_one_row(self):
        results = [audit.ModelInstanceResult(factories.AccountFactory())]
        table = audit.ErrorTable(results)
        self.assertEqual(len(table.rows), 1)

    def test_two_rows(self):
        result_1 = audit.ModelInstanceResult(factories.AccountFactory())
        result_1.add_error("foo")
        result_2 = audit.ModelInstanceResult(factories.AccountFactory())
        result_2.add_error("bar")
        results = [result_1, result_2]
        table = audit.ErrorTable(results)
        self.assertEqual(len(table.rows), 2)


class AnVILAuditTest(TestCase):
    """Tests for the AnVILAudit abstract base class."""

    def setUp(self):
        super().setUp()

        class GenericAudit(audit.AnVILAudit):
            TEST_ERROR_1 = "Test error 1"
            TEST_ERROR_2 = "Test error 2"

        self.audit_results = GenericAudit()
        # It doesn't matter what model we use at this point, so just pick Account.
        self.model_factory = factories.AccountFactory

    def test_init(self):
        """Init method works as expected."""
        self.assertEqual(len(self.audit_results._model_instance_results), 0)
        self.assertEqual(len(self.audit_results._not_in_app_results), 0)

    def test_ok_no_results(self):
        """ok() returns True when there are no results."""
        self.assertTrue(self.audit_results.ok())

    def test_ok_one_result_ok(self):
        """ok() returns True when there is one ok result."""
        model_instance_result = audit.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        self.assertTrue(self.audit_results.ok())

    def test_ok_two_results_ok(self):
        """ok() returns True when there is one ok result."""
        model_instance_result_1 = audit.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = audit.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result_2)
        self.assertTrue(self.audit_results.ok())

    def test_ok_one_result_with_errors(self):
        """ok() returns True when there is one ok result."""
        model_instance_result = audit.ModelInstanceResult(self.model_factory())
        model_instance_result.add_error("foo")
        self.audit_results.add_result(model_instance_result)
        self.assertFalse(self.audit_results.ok())

    def test_ok_one_not_in_app(self):
        """ok() returns True when there are no results."""
        self.audit_results.add_result(audit.NotInAppResult("foo"))
        self.assertFalse(self.audit_results.ok())

    def test_run_audit_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.audit_results.run_audit()

    def test_add_result_not_in_app(self):
        """Can add a NotInAppResult."""
        not_in_app_result = audit.NotInAppResult("foo")
        self.audit_results.add_result(not_in_app_result)
        self.assertEqual(len(self.audit_results._not_in_app_results), 1)

    def test_add_result_wrong_class(self):
        """Can add a NotInAppResult."""
        with self.assertRaises(ValueError):
            self.audit_results.add_result("foo")

    def test_add_result_duplicate_not_in_app(self):
        """Cannot add a duplicate NotInAppResult."""
        not_in_app_result = audit.NotInAppResult("foo")
        self.audit_results.add_result(not_in_app_result)
        # import ipdb; ipdb.set_trace()
        with self.assertRaises(ValueError):
            self.audit_results.add_result(not_in_app_result)
        self.assertEqual(len(self.audit_results._not_in_app_results), 1)

    def test_add_result_not_in_app_same_record(self):
        """Cannot add a duplicate NotInAppResult."""
        not_in_app_result = audit.NotInAppResult("foo")
        self.audit_results.add_result(not_in_app_result)
        # import ipdb; ipdb.set_trace()
        with self.assertRaises(ValueError):
            self.audit_results.add_result(audit.NotInAppResult("foo"))
        self.assertEqual(len(self.audit_results._not_in_app_results), 1)

    def test_add_result_model_instance(self):
        """Can add a model instance result."""
        model_instance_result = audit.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results._model_instance_results), 1)

    def test_add_result_duplicate_model_instance_result(self):
        """Cannot add a duplicate model instance result."""
        model_instance_result = audit.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        # import ipdb; ipdb.set_trace()
        with self.assertRaises(ValueError):
            self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results._model_instance_results), 1)

    def test_add_result_second_result_for_same_model_instance(self):
        obj = self.model_factory()
        model_instance_result_1 = audit.ModelInstanceResult(obj)
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = audit.ModelInstanceResult(obj)
        # import ipdb; ipdb.set_trace()
        with self.assertRaises(ValueError):
            self.audit_results.add_result(model_instance_result_2)
        self.assertEqual(len(self.audit_results._model_instance_results), 1)
        self.assertEqual(self.audit_results._model_instance_results, [model_instance_result_1])

    def test_add_result_second_result_for_same_model_instance_with_error(self):
        obj = self.model_factory()
        model_instance_result_1 = audit.ModelInstanceResult(obj)
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = audit.ModelInstanceResult(obj)
        model_instance_result_2.add_error("Foo")
        with self.assertRaises(ValueError):
            self.audit_results.add_result(model_instance_result_2)
        self.assertEqual(len(self.audit_results._model_instance_results), 1)
        self.assertEqual(self.audit_results._model_instance_results, [model_instance_result_1])

    def test_get_result_for_model_instance_no_matches(self):
        obj = self.model_factory()
        audit.ModelInstanceResult(obj)
        with self.assertRaises(ValueError):
            self.audit_results.get_result_for_model_instance(obj)

    def test_get_result_for_model_instance_one_match(self):
        obj = self.model_factory()
        model_instance_result = audit.ModelInstanceResult(obj)
        self.audit_results.add_result(model_instance_result)
        result = self.audit_results.get_result_for_model_instance(obj)
        self.assertIs(result, model_instance_result)

    def test_get_verified_results_no_results(self):
        """get_verified_results returns an empty list when there are no results."""
        self.assertEqual(len(self.audit_results.get_verified_results()), 0)

    def test_get_verified_results_one_verified_result(self):
        """get_verified_results returns a list when there is one result."""
        model_instance_result = audit.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_verified_results()), 1)
        self.assertIn(model_instance_result, self.audit_results.get_verified_results())

    def test_get_error_results_two_verified_result(self):
        """get_verified_results returns a list of lenght two when there are two verified results."""
        model_instance_result_1 = audit.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = audit.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result_2)
        self.assertEqual(len(self.audit_results.get_verified_results()), 2)
        self.assertIn(model_instance_result_1, self.audit_results.get_verified_results())
        self.assertIn(model_instance_result_2, self.audit_results.get_verified_results())

    def test_get_verified_results_one_error_result(self):
        """get_verified_results returns a list of lenght zero when there is one error result."""
        model_instance_result = audit.ModelInstanceResult(self.model_factory())
        model_instance_result.add_error("foo")
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_verified_results()), 0)

    def test_get_verified_results_one_not_in_app_result(self):
        """get_verified_results returns a list of lenght zero when there is one not_in_app result."""
        self.audit_results.add_result(audit.NotInAppResult("foo"))
        self.assertEqual(len(self.audit_results.get_verified_results()), 0)

    def test_get_error_results_no_results(self):
        """get_error_results returns an empty list when there are no results."""
        self.assertEqual(len(self.audit_results.get_error_results()), 0)

    def test_get_error_results_one_verified_result(self):
        """get_error_results returns a list of length zero when there is one verified result."""
        model_instance_result = audit.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_error_results()), 0)

    def test_get_error_results_one_error_result(self):
        """get_error_results returns a list of lenght one when there is one error result."""
        model_instance_result = audit.ModelInstanceResult(self.model_factory())
        model_instance_result.add_error("foo")
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_error_results()), 1)
        self.assertIn(model_instance_result, self.audit_results.get_error_results())

    def test_get_error_results_two_error_result(self):
        """get_error_results returns a list of lenght two when there is one result."""
        model_instance_result_1 = audit.ModelInstanceResult(self.model_factory())
        model_instance_result_1.add_error("foo")
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = audit.ModelInstanceResult(self.model_factory())
        model_instance_result_2.add_error("foo")
        self.audit_results.add_result(model_instance_result_2)
        self.assertEqual(len(self.audit_results.get_error_results()), 2)
        self.assertIn(model_instance_result_1, self.audit_results.get_error_results())
        self.assertIn(model_instance_result_2, self.audit_results.get_error_results())

    def test_get_error_results_one_not_in_app_result(self):
        """get_error_results returns a list of length zero when there is one not_in_app result."""
        self.audit_results.add_result(audit.NotInAppResult("foo"))
        self.assertEqual(len(self.audit_results.get_error_results()), 0)

    def test_get_not_in_app_results_no_results(self):
        """get_not_in_app_results returns an empty list when there are no results."""
        self.assertEqual(len(self.audit_results.get_not_in_app_results()), 0)

    def test_get_not_in_app_results_one_verified_result(self):
        """get_not_in_app_results returns a list of length zero when there is one verified result."""
        model_instance_result = audit.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_not_in_app_results()), 0)

    def test_get_not_in_app_results_one_error_result(self):
        """get_not_in_app_results returns a list of lenght one when there is one error result."""
        model_instance_result = audit.ModelInstanceResult(self.model_factory())
        model_instance_result.add_error("foo")
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_not_in_app_results()), 0)

    def test_get_not_in_app_results_one_not_in_app_result(self):
        """get_not_in_app_results returns a list of length zero when there is one not_in_app result."""
        result = audit.NotInAppResult("foo")
        self.audit_results.add_result(result)
        self.assertEqual(len(self.audit_results.get_not_in_app_results()), 1)
        self.assertIn(result, self.audit_results.get_not_in_app_results())

    def test_get_not_in_app_results_two_not_in_app_results(self):
        """get_not_in_app_results returns a list of lenght two when there is one result."""
        result_1 = audit.NotInAppResult("foo")
        self.audit_results.add_result(result_1)
        result_2 = audit.NotInAppResult("bar")
        self.audit_results.add_result(result_2)
        self.assertEqual(len(self.audit_results.get_not_in_app_results()), 2)
        self.assertIn(result_1, self.audit_results.get_not_in_app_results())
        self.assertIn(result_2, self.audit_results.get_not_in_app_results())

    def test_export(self):
        # One Verified result.
        verified_result = audit.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(verified_result)
        # One error result.
        error_result = audit.ModelInstanceResult(self.model_factory())
        error_result.add_error("foo")
        self.audit_results.add_result(error_result)
        # Not in app result.
        not_in_app_result = audit.NotInAppResult("bar")
        self.audit_results.add_result(not_in_app_result)
        # Check export.
        exported_data = self.audit_results.export()
        self.assertIn("verified", exported_data)
        self.assertEqual(
            exported_data["verified"],
            [
                {
                    "id": verified_result.model_instance.pk,
                    "instance": verified_result.model_instance,
                }
            ],
        )
        self.assertIn("errors", exported_data)
        self.assertEqual(
            exported_data["errors"],
            [
                {
                    "id": error_result.model_instance.pk,
                    "instance": error_result.model_instance,
                    "errors": ["foo"],
                }
            ],
        )
        self.assertIn("not_in_app", exported_data)
        self.assertEqual(exported_data["not_in_app"], ["bar"])

    def test_export_include_verified_false(self):
        exported_data = self.audit_results.export(include_verified=False)
        self.assertNotIn("verified", exported_data)
        self.assertIn("errors", exported_data)
        self.assertIn("not_in_app", exported_data)

    def test_export_include_errors_false(self):
        exported_data = self.audit_results.export(include_errors=False)
        self.assertIn("verified", exported_data)
        self.assertNotIn("errors", exported_data)
        self.assertIn("not_in_app", exported_data)

    def test_export_include_not_in_app_false(self):
        exported_data = self.audit_results.export(include_not_in_app=False)
        self.assertIn("verified", exported_data)
        self.assertIn("errors", exported_data)
        self.assertNotIn("not_in_app", exported_data)

    def test_export_not_in_app_sorted(self):
        """export sorts the not_in_app results."""
        self.audit_results.add_result(audit.NotInAppResult("foo"))
        self.audit_results.add_result(audit.NotInAppResult("bar"))
        exported_data = self.audit_results.export()
        self.assertEqual(exported_data["not_in_app"], ["bar", "foo"])


class BillingProjectAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the BillingProject.anvil_audit method."""

    def get_api_url(self, billing_project_name):
        return self.api_client.rawls_entry_point + "/api/billing/v2/" + billing_project_name

    def get_api_json_response(self):
        return {
            "roles": ["User"],
        }

    def test_anvil_audit_no_billing_projects(self):
        """anvil_audit works correct if there are no billing projects in the app."""
        audit_results = audit.BillingProjectAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_billing_project_no_errors(self):
        """anvil_audit works correct if one billing project exists in the app and in AnVIL."""
        billing_project = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url = self.get_api_url(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = audit.BillingProjectAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(billing_project)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_billing_project_not_on_anvil(self):
        """anvil_audit raises exception with one billing project exists in the app but not on AnVIL."""
        billing_project = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url = self.get_api_url(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        audit_results = audit.BillingProjectAudit()
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
        billing_project_1 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=200,
            json=self.get_api_json_response(),
        )
        billing_project_2 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = audit.BillingProjectAudit()
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
        billing_project_1 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        billing_project_2 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = audit.BillingProjectAudit()
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
        billing_project_1 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        billing_project_2 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=404,
            json={"message": "other error"},
        )
        audit_results = audit.BillingProjectAudit()
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
        factories.BillingProjectFactory.create(has_app_as_user=False)
        # No API calls made.
        audit_results = audit.BillingProjectAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)


class AccountAuditTest(AnVILAPIMockTestMixin, TestCase):
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
        audit_results = audit.AccountAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_account_no_errors(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(account.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=self.get_api_json_response(account.email),
        )
        audit_results = audit.AccountAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(account)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_account_not_on_anvil(self):
        """anvil_audit raises exception if one billing project exists in the app but not on AnVIL."""
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(account.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        audit_results = audit.AccountAudit()
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
        account_1 = factories.AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=200,
            json=self.get_api_json_response(account_1.email),
        )
        account_2 = factories.AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(account_2.email),
        )
        audit_results = audit.AccountAudit()
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
        account_1 = factories.AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        account_2 = factories.AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(account_2.email),
        )
        audit_results = audit.AccountAudit()
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
        account_1 = factories.AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        account_2 = factories.AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=404,
            json={"message": "other error"},
        )
        audit_results = audit.AccountAudit()
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
        account = factories.AccountFactory.create()
        account.deactivate()
        # No API calls made.
        audit_results = audit.AccountAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)


class ManagedGroupAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests forthe ManagedGroup.anvil_audit method."""

    def get_api_groups_url(self):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1"

    def get_api_url_members(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member"

    def get_api_url_admins(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/admin"

    def test_anvil_audit_no_groups(self):
        """anvil_audit works correct if there are no ManagedGroups in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_group_managed_by_app_no_errors(self):
        """anvil_audit works correct if there is one group in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsAdminFactory(groupName=group.name)]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_managed_by_app_lowercase_role(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsAdminFactory(groupName=group.name)]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_not_managed_by_app_no_errors(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsMemberFactory(groupName=group.name)]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_not_managed_by_app_no_errors_uppercase_role(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsFactory(groupName=group.name, role="Member")]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_not_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app but not on AnVIL."""
        group = factories.ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(n_groups=0).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group.name,
            status=404,
            json=api_factories.ErrorResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_one_group_on_anvil_but_app_not_in_group_not_managed_by_app(
        self,
    ):
        """anvil_audit is correct if the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(n_groups=0).response,
        )
        # Add the response.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group.name,
            status=200,
            json="FOO@BAR.COM",
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_managed_by_app_on_anvil_but_app_not_in_group(self):
        """anvil_audit raises exception if one group exists in the app but not on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(n_groups=0).response,
        )
        # Add the response.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group.name,
            status=200,
            json="FOO@BAR.COM",
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE]))

    def test_anvil_audit_one_group_admin_in_app_member_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app as an admin but the role on AnVIL is member."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsMemberFactory(groupName=group.name)]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE]))

    def test_anvil_audit_one_group_member_in_app_admin_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app as an member but the role on AnVIL is admin."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsAdminFactory(groupName=group.name)]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE]))

    def test_anvil_audit_two_groups_no_errors(self):
        """anvil_audit works correctly if if two groups exist in both the app and AnVIL."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(groupName=group_1.name),
                    api_factories.GroupDetailsMemberFactory(groupName=group_2.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(group_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_groups_json_response_order_does_not_matter(self):
        """Order of groups in the json response does not matter."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsMemberFactory(groupName=group_2.name),
                    api_factories.GroupDetailsAdminFactory(groupName=group_1.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(group_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_groups_first_not_on_anvil(self):
        """anvil_audit raises exception if two groups exist in the app but the first is not not on AnVIL."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(groupName=group_2.name),
                ]
            ).response,
        )
        # Add response for the group that is not in the app.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group_1.name,
            status=404,
            json=api_factories.ErrorResponseFactory().response,
        )
        # Add responses for the group that is in the app.
        api_url_members = self.get_api_url_members(group_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(group_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_groups_both_missing(self):
        """anvil_audit raises exception if there are two groups that exist in the app but not in AnVIL."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory().response,
        )
        # Add response for the group that is not in the app.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group_1.name,
            status=404,
            json=api_factories.ErrorResponseFactory().response,
        )
        # Add response for the group that is not in the app.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group_2.name,
            status=404,
            json=api_factories.ErrorResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(group_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_one_group_member_missing_in_app(self):
        """Groups that the app is a member of are not reported in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsMemberFactory(groupName="test-group")]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_group_admin_missing_in_app(self):
        """anvil_audit works correctly if the service account is an admin of a group not in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsAdminFactory(groupName="test-group")]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-group")

    def test_anvil_audit_two_groups_admin_missing_in_app(self):
        """anvil_audit works correctly if there are two groups in AnVIL that aren't in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(groupName="test-group-1"),
                    api_factories.GroupDetailsAdminFactory(groupName="test-group-2"),
                ]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-group-1")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "test-group-2")

    def test_fails_membership_audit(self):
        """Error is reported when a group fails the membership audit."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsAdminFactory(groupName=group.name)]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_MEMBERSHIP]))

    def test_admin_in_app_both_member_and_admin_on_anvil(self):
        """anvil_audit works correctly when the app is an admin and AnVIL returns both a member and admin record."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(groupName=group.name),
                    api_factories.GroupDetailsMemberFactory(groupName=group.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_admin_in_app_both_member_and_admin_different_order_on_anvil(self):
        """anvil_audit works correctly when the app is an admin and AnVIL returns both a member and admin record."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsMemberFactory(groupName=group.name),
                    api_factories.GroupDetailsAdminFactory(groupName=group.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_member_in_app_both_member_and_admin_on_anvil(self):
        """anvil_audit works correctly when the app is a member and AnVIL returns both a member and admin record."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsMemberFactory(groupName=group.name),
                    api_factories.GroupDetailsAdminFactory(groupName=group.name),
                ]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE]))

    def test_member_in_app_both_member_and_admin_different_order_on_anvil(self):
        """anvil_audit works correctly when the app is a member and AnVIL returns both a member and admin record."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(groupName=group.name),
                    api_factories.GroupDetailsMemberFactory(groupName=group.name),
                ]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE]))


class ManagedGroupMembershipAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests forthe ManagedGroupMembershipAudit class."""

    def get_api_url_members(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member"

    def get_api_url_admins(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/admin"

    def test_group_not_managed_by_app(self):
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        with self.assertRaises(exceptions.AnVILNotGroupAdminError):
            audit.ManagedGroupMembershipAudit(group)

    def test_no_members(self):
        """audit works correctly if this group has no members."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_one_account_members(self):
        """audit works correctly if this group has one account member."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[membership.account.email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        model_result = audit_results.get_result_for_model_instance(membership)
        self.assertIsInstance(model_result, audit.ModelInstanceResult)
        self.assertTrue(model_result.ok())
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_two_account_members(self):
        """audit works correctly if this group has two account members."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupAccountMembershipFactory.create(group=group)
        membership_2 = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=[membership_1.account.email, membership_2.account.email]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        model_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertIsInstance(model_result, audit.ModelInstanceResult)
        self.assertTrue(model_result.ok())
        model_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertIsInstance(model_result, audit.ModelInstanceResult)
        self.assertTrue(model_result.ok())
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_one_account_members_not_in_anvil(self):
        """audit works correctly if this group has one account member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL]))

    def test_two_account_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has two account member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupAccountMembershipFactory.create(group=group)
        membership_2 = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        model_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertIsInstance(model_result, audit.ModelInstanceResult)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL]))
        model_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertIsInstance(model_result, audit.ModelInstanceResult)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL]))
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_one_account_members_not_in_app(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=["test-member@example.com"]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        # Check individual records.
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(record_result, audit.NotInAppResult)
        self.assertEqual(record_result.record, "MEMBER: test-member@example.com")

    def test_two_account_members_not_in_app(self):
        """anvil_audit works correctly if this group has two account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=["test-member-1@example.com", "test-member-2@example.com"]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        # Check individual records.
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(record_result, audit.NotInAppResult)
        self.assertEqual(record_result.record, "MEMBER: test-member-1@example.com")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertIsInstance(record_result, audit.NotInAppResult)
        self.assertEqual(record_result.record, "MEMBER: test-member-2@example.com")

    def test_one_account_members_case_insensitive(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, account__email="tEsT-mEmBeR@example.com"
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=["Test-Member@example.com"]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_one_account_admin(self):
        """anvil_audit works correctly if this group has one account admin."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[membership.account.email]).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_two_account_admin(self):
        """anvil_audit works correctly if this group has two account members."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        membership_2 = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=[membership_1.account.email, membership_2.account.email]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertTrue(record_result.ok())

    def test_one_account_admin_not_in_anvil(self):
        """anvil_audit works correctly if this group has one account member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL]))

    def test_two_account_admins_not_in_anvil(self):
        """anvil_audit works correctly if this group has two account member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        membership_2 = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL]))

    def test_one_account_admin_not_in_app(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=["test-admin@example.com"]).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: test-admin@example.com")

    def test_two_account_admin_not_in_app(self):
        """anvil_audit works correctly if this group has two account admin not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=["test-admin-1@example.com", "test-admin-2@example.com"]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: test-admin-1@example.com")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "ADMIN: test-admin-2@example.com")

    def test_one_account_admin_case_insensitive(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group,
            account__email="tEsT-aDmIn@example.com",
            role=models.GroupAccountMembership.ADMIN,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=["Test-Admin@example.com"]).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_account_different_role_member_in_app_admin_in_anvil(self):
        """anvil_audit works correctly if an account has a different role in AnVIL."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.MEMBER
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[membership.account.email]).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL]))
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: " + membership.account.email)

    def test_one_group_members(self):
        """anvil_audit works correctly if this group has one group member."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[membership.child_group.email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_two_group_members(self):
        """anvil_audit works correctly if this group has two account members."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        membership_2 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=[
                    membership_1.child_group.email,
                    membership_2.child_group.email,
                ]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertTrue(record_result.ok())

    def test_one_group_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has one group member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL]))

    def test_two_group_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has two group member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        membership_2 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL]))

    def test_one_group_members_not_in_app(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=["test-member@firecloud.org"]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "MEMBER: test-member@firecloud.org")

    def test_two_group_members_not_in_app(self):
        """anvil_audit works correctly if this group has two group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=["test-member-1@firecloud.org", "test-member-2@firecloud.org"]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "MEMBER: test-member-1@firecloud.org")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "MEMBER: test-member-2@firecloud.org")

    def test_one_group_members_case_insensitive(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(parent_group=group, child_group__name="tEsT-mEmBeR")
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=["Test-Member@firecloud.org"]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_one_group_admin(self):
        """anvil_audit works correctly if this group has one group admin."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[membership.child_group.email]).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_two_group_admin(self):
        """anvil_audit works correctly if this group has two group admin."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        membership_2 = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=[
                    membership_1.child_group.email,
                    membership_2.child_group.email,
                ]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertTrue(record_result.ok())

    def test_one_group_admin_not_in_anvil(self):
        """anvil_audit works correctly if this group has one group member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL]))

    def test_two_group_admins_not_in_anvil(self):
        """anvil_audit works correctly if this group has two group member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        membership_2 = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL]))

    def test_one_group_admin_not_in_app(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=["test-admin@firecloud.org"]).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: test-admin@firecloud.org")

    def test_two_group_admin_not_in_app(self):
        """anvil_audit works correctly if this group has two group admin not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=["test-admin-1@firecloud.org", "test-admin-2@firecloud.org"]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: test-admin-1@firecloud.org")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "ADMIN: test-admin-2@firecloud.org")

    def test_one_group_admin_case_insensitive(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group,
            child_group__name="tEsT-aDmIn",
            role=models.GroupGroupMembership.ADMIN,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=["Test-Admin@firecloud.org"]).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_group_different_role_member_in_app_admin_in_anvil(self):
        """anvil_audit works correctly if an group has a different role in AnVIL."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.MEMBER
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[membership.child_group.email]).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL]))
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: " + membership.child_group.email)

    def test_service_account_is_both_admin_and_member(self):
        """No errors are reported when the service account is both a member and an admin of a group."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[self.service_account_email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_different_group_member_email(self):
        """anvil_audit works correctly if this group has one group member with a different email."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(parent_group=group, child_group__email="foo@bar.com")
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[membership.child_group.email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_different_group_member_email_case_insensitive(self):
        """anvil_audit works correctly if this group has one group member with a different email, case insensitive."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(parent_group=group, child_group__email="foo@bar.com")
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=["Foo@Bar.com"]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_service_account_is_not_directly_admin(self):
        """Audit works when the service account is not directly an admin of a group (but is via a group admin)."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group,
            child_group__email="foo@bar.com",
            role=models.GroupGroupMembership.ADMIN,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            # Use the Membership factory because it doesn't add the service account as a direct admin.
            json=api_factories.GetGroupMembershipResponseFactory(response=["foo@bar.com"]).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_group_is_both_admin_and_member(self):
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[membership.child_group.email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[membership.child_group.email]).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_deactivated_account_not_member_in_anvil(self):
        """Audit is ok if a deactivated account is not in the group on AnVIL."""
        group = factories.ManagedGroupFactory.create()
        # Create an inactive account that is a member of this group.
        factories.GroupAccountMembershipFactory.create(group=group, account__status=models.Account.INACTIVE_STATUS)
        # The Account is not a member in AnVIL
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_deactivated_account_member_in_anvil(self):
        """Audit is not ok if a deactivated account is in the group on AnVIL."""
        group = factories.ManagedGroupFactory.create()
        # Create an inactive account that is a member of this group.
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, account__status=models.Account.INACTIVE_STATUS
        )
        # The Account is not a member in AnVIL
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[membership.account.email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertEqual(
            record_result.errors,
            set([audit_results.ERROR_DEACTIVATED_ACCOUNT_IS_MEMBER_IN_ANVIL]),
        )

    def test_deactivated_account_not_admin_in_anvil(self):
        """Audit is ok if a deactivated account is not in the group on AnVIL."""
        group = factories.ManagedGroupFactory.create()
        # Create an inactive account that is a member of this group.
        factories.GroupAccountMembershipFactory.create(
            group=group,
            account__status=models.Account.INACTIVE_STATUS,
            role=models.GroupAccountMembership.ADMIN,
        )
        # The Account is not a member in AnVIL
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_deactivated_account_admin_in_anvil(self):
        """Audit is not ok if a deactivated account is in the group on AnVIL."""
        group = factories.ManagedGroupFactory.create()
        # Create an inactive account that is a member of this group.
        membership = factories.GroupAccountMembershipFactory.create(
            group=group,
            account__status=models.Account.INACTIVE_STATUS,
            role=models.GroupAccountMembership.ADMIN,
        )
        # The Account is not a member in AnVIL
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[membership.account.email]).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertEqual(
            record_result.errors,
            set([audit_results.ERROR_DEACTIVATED_ACCOUNT_IS_ADMIN_IN_ANVIL]),
        )


class WorkspaceAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the Workspace.anvil_audit method."""

    def get_api_url(self):
        return self.api_client.rawls_entry_point + "/api/workspaces"

    def get_api_workspace_json(
        self,
        billing_project_name,
        workspace_name,
        access,
        auth_domains=[],
        is_locked=False,
    ):
        """Return the json dictionary for a single workspace on AnVIL."""
        return {
            "accessLevel": access,
            "workspace": {
                "name": workspace_name,
                "namespace": billing_project_name,
                "authorizationDomain": [{"membersGroupName": x} for x in auth_domains],
                "isLocked": is_locked,
            },
        }

    def get_api_workspace_acl_url(self, billing_project_name, workspace_name):
        return (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
            + "/acl"
        )

    def get_api_workspace_acl_response(self):
        """Return a json for the workspace/acl method where no one else can access."""
        return {
            "acl": {
                self.service_account_email: {
                    "accessLevel": "OWNER",
                    "canCompute": True,
                    "canShare": True,
                    "pending": False,
                }
            }
        }

    def get_api_bucket_options_url(self, billing_project_name, workspace_name):
        return self.api_client.rawls_entry_point + "/api/workspaces/" + billing_project_name + "/" + workspace_name

    def get_api_bucket_options_response(self):
        """Return a json for the workspace/acl method that is not requester pays."""
        return {"bucketOptions": {"requesterPays": False}}

    def test_anvil_audit_no_workspaces(self):
        """anvil_audit works correct if there are no Workspaces in the app."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_workspace_no_errors(self):
        """anvil_audit works correct if there is one workspace in the app and it exists on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json(workspace.billing_project.name, workspace.name, "OWNER")],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_workspace_not_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app but not on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_one_workspace_owner_in_app_reader_on_anvil(self):
        """anvil_audit raises exception if one workspace exists in the app but the access on AnVIL is READER."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json(workspace.billing_project.name, workspace.name, "READER")],
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_OWNER_ON_ANVIL]))

    def test_anvil_audit_one_workspace_owner_in_app_writer_on_anvil(self):
        """anvil_audit raises exception if one workspace exists in the app but the access on AnVIL is WRITER."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json(workspace.billing_project.name, workspace.name, "WRITER")],
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_OWNER_ON_ANVIL]))

    def test_anvil_audit_one_workspace_is_locked_in_app_not_on_anvil(self):
        """anvil_audit raises exception if workspace is locked in the app but not on AnVIL."""
        workspace = factories.WorkspaceFactory.create(is_locked=True)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    is_locked=False,
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_LOCK]))

    def test_anvil_audit_one_workspace_is_not_locked_in_app_but_is_on_anvil(self):
        """anvil_audit raises exception if workspace is locked in the app but not on AnVIL."""
        workspace = factories.WorkspaceFactory.create(is_locked=False)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    is_locked=True,
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_LOCK]))

    def test_anvil_audit_one_workspace_is_requester_pays_in_app_not_on_anvil(self):
        """anvil_audit raises exception if workspace is requester_pays in the app but not on AnVIL."""
        workspace = factories.WorkspaceFactory.create(is_requester_pays=True)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    is_locked=False,
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_REQUESTER_PAYS]))

    def test_anvil_audit_one_workspace_is_not_requester_pays_in_app_but_is_on_anvil(self):
        """anvil_audit raises exception if workspace is requester_pays in the app but not on AnVIL."""
        workspace = factories.WorkspaceFactory.create(is_requester_pays=False)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    is_locked=False,
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        response = self.get_api_bucket_options_response()
        response["bucketOptions"]["requesterPays"] = True
        self.anvil_response_mock.add(responses.GET, workspace_acl_url, status=200, json=response)
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_REQUESTER_PAYS]))

    def test_anvil_audit_two_workspaces_no_errors(self):
        """anvil_audit returns None if if two workspaces exist in both the app and AnVIL."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(workspace_1.billing_project.name, workspace_1.name, "OWNER"),
                self.get_api_workspace_json(workspace_2.billing_project.name, workspace_2.name, "OWNER"),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_groups_json_response_order_does_not_matter(self):
        """Order of groups in the json response does not matter."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(workspace_2.billing_project.name, workspace_2.name, "OWNER"),
                self.get_api_workspace_json(workspace_1.billing_project.name, workspace_1.name, "OWNER"),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_workspaces_first_not_on_anvil(self):
        """anvil_audit raises exception if two workspaces exist in the app but the first is not not on AnVIL."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(workspace_2.billing_project.name, workspace_2.name, "OWNER"),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_workspaces_first_different_access(self):
        """anvil_audit when if two workspaces exist in the app but access to the first is different on AnVIL."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(workspace_1.billing_project.name, workspace_1.name, "READER"),
                self.get_api_workspace_json(workspace_2.billing_project.name, workspace_2.name, "OWNER"),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_OWNER_ON_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_workspaces_both_missing_in_anvil(self):
        """anvil_audit when there are two workspaces that exist in the app but not in AnVIL."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_one_workspace_missing_in_app(self):
        """anvil_audit returns not_in_app info if a workspace exists on AnVIL but not in the app."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp", "test-ws", "OWNER")],
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-bp/test-ws")

    def test_anvil_audit_two_workspaces_missing_in_app(self):
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json("test-bp-1", "test-ws-1", "OWNER"),
                self.get_api_workspace_json("test-bp-2", "test-ws-2", "OWNER"),
            ],
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-bp-1/test-ws-1")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "test-bp-2/test-ws-2")

    def test_different_billing_project(self):
        """A workspace is reported as missing if it has the same name but a different billing project in app."""
        workspace = factories.WorkspaceFactory.create(billing_project__name="test-bp-app", name="test-ws")
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp-anvil", "test-ws", "OWNER")],
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-bp-anvil/test-ws")

    def test_ignores_workspaces_where_app_is_reader_on_anvil(self):
        """Audit ignores workspaces on AnVIL where app is a READER on AnVIL."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp", "test-ws", "READER")],
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_ignores_workspaces_where_app_is_writer_on_anvil(self):
        """Audit ignores workspaces on AnVIL where app is a WRITER on AnVIL."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp", "test-ws", "WRITER")],
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_one_workspace_one_auth_domain(self):
        """anvil_audit works properly when there is one workspace with one auth domain."""
        auth_domain = factories.WorkspaceAuthorizationDomainFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    auth_domain.workspace.billing_project.name,
                    auth_domain.workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(auth_domain.workspace)
        self.assertTrue(record_result.ok())

    def test_one_workspace_two_auth_domains(self):
        """anvil_audit works properly when there is one workspace with two auth domains."""
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        auth_domain_2 = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain_1.group.name, auth_domain_2.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertTrue(record_result.ok())

    def test_one_workspace_two_auth_domains_order_does_not_matter(self):
        """anvil_audit works properly when there is one workspace with two auth domains."""
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="aa")
        auth_domain_2 = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="zz")
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain_2.group.name, auth_domain_1.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertTrue(record_result.ok())

    def test_one_workspace_no_auth_domain_in_app_one_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with no auth domain in the app but one on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=["auth-anvil"],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_one_auth_domain_in_app_no_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with one auth domain in the app but none on AnVIL."""
        auth_domain = factories.WorkspaceAuthorizationDomainFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    auth_domain.workspace.billing_project.name,
                    auth_domain.workspace.name,
                    "OWNER",
                    auth_domains=[],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(auth_domain.workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_no_auth_domain_in_app_two_auth_domains_on_anvil(self):
        """anvil_audit works properly when there is one workspace with no auth domain in the app but two on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=["auth-domain"],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_two_auth_domains_in_app_no_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with two auth domains in the app but none on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_two_auth_domains_in_app_one_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with two auth domains in the app but one on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain_1.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_different_auth_domains(self):
        """anvil_audit works properly when the app and AnVIL have different auth domains for the same workspace."""
        auth_domain = factories.WorkspaceAuthorizationDomainFactory.create(group__name="app")
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    auth_domain.workspace.billing_project.name,
                    auth_domain.workspace.name,
                    "OWNER",
                    auth_domains=["anvil"],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(auth_domain.workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_two_workspaces_first_auth_domains_do_not_match(self):
        """anvil_audit works properly when there are two workspaces in the app and the first has auth domain issues."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace_1.billing_project.name,
                    workspace_1.name,
                    "OWNER",
                    auth_domains=["anvil"],
                ),
                self.get_api_workspace_json(
                    workspace_2.billing_project.name,
                    workspace_2.name,
                    "OWNER",
                    auth_domains=[],
                ),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertTrue(record_result.ok())

    def test_two_workspaces_auth_domains_do_not_match_for_both(self):
        """anvil_audit works properly when there are two workspaces in the app and both have auth domain issues."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace_1.billing_project.name,
                    workspace_1.name,
                    "OWNER",
                    auth_domains=["anvil-1"],
                ),
                self.get_api_workspace_json(
                    workspace_2.billing_project.name,
                    workspace_2.name,
                    "OWNER",
                    auth_domains=["anvil-2"],
                ),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_1.billing_project.name, workspace_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))
        record_result = audit_results.get_result_for_model_instance(workspace_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]))

    def test_one_workspace_with_two_errors(self):
        """One workspace has two errors: different auth domains and not owner."""
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json(workspace.billing_project.name, workspace.name, "READER")],
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors,
            set(
                [
                    audit_results.ERROR_NOT_OWNER_ON_ANVIL,
                    audit_results.ERROR_DIFFERENT_AUTH_DOMAINS,
                ]
            ),
        )

    def test_fails_sharing_audit(self):
        """anvil_audit works properly when one workspace fails its sharing audit."""
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace)
        # Response for the main call about workspaces.
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        audit_results = audit.WorkspaceAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(workspace)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_WORKSPACE_SHARING]))


class WorkspaceSharingAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the WorkspaceSharingAudit class."""

    def setUp(self):
        super().setUp()
        # Set this variable here because it will include the service account.
        # Tests can update it with the update_api_response method.
        self.api_response = {"acl": {}}
        # Create a workspace for use in tests.
        self.workspace = factories.WorkspaceFactory.create()
        self.api_url = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + self.workspace.billing_project.name
            + "/"
            + self.workspace.name
            + "/acl"
        )

    def update_api_response(self, email, access, can_compute=False, can_share=False):
        """Return a paired down json for a single ACL, including the service account."""
        self.api_response["acl"].update(
            {
                email: {
                    "accessLevel": access,
                    "canCompute": can_compute,
                    "canShare": can_share,
                    "pending": False,
                }
            }
        )

    def test_no_access(self):
        """anvil_audit works correctly if this workspace is not shared with any groups."""
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_one_group_reader(self):
        """anvil_audit works correctly if this group has one group member."""
        access = factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        self.update_api_response(access.group.email, access.access)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_two_group_readers(self):
        """anvil_audit works correctly if this workspace has two group readers."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        access_2 = factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        self.update_api_response(access_1.group.email, "READER")
        self.update_api_response(access_2.group.email, "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertTrue(model_result.ok())
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertTrue(model_result.ok())

    def test_one_group_reader_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has one group reader not in anvil."""
        access = factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_two_group_readers_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has two group readers not in anvil."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        access_2 = factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_one_group_readers_not_in_app(self):
        """anvil_audit works correctly if this workspace has one group reader not in the app."""
        self.update_api_response("test-member@firecloud.org", "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(model_result.record, "READER: test-member@firecloud.org")

    def test_two_group_readers_not_in_app(self):
        """anvil_audit works correctly if this workspace has two group readers not in the app."""
        self.update_api_response("test-member-1@firecloud.org", "READER")
        self.update_api_response("test-member-2@firecloud.org", "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(model_result.record, "READER: test-member-1@firecloud.org")
        model_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(model_result.record, "READER: test-member-2@firecloud.org")

    def test_one_group_members_case_insensitive(self):
        """anvil_audit ignores case."""
        access = factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace, group__name="tEsT-mEmBeR")
        self.update_api_response("Test-Member@firecloud.org", "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_one_group_writer(self):
        """anvil_audit works correctly if this workspace has one group writer."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        self.update_api_response(access.group.email, "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_two_group_writers(self):
        """anvil_audit works correctly if this workspace has two group writers."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        access_2 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        self.update_api_response(access_1.group.email, "WRITER")
        self.update_api_response(access_2.group.email, "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertTrue(model_result.ok())
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertTrue(model_result.ok())

    def test_one_group_writer_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has one group writer not in anvil."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_two_group_writers_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has two group writers not in anvil."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        access_2 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_one_group_writer_not_in_app(self):
        """anvil_audit works correctly if this workspace has one group writer not in the app."""
        self.update_api_response("test-writer@firecloud.org", "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(model_result.record, "WRITER: test-writer@firecloud.org")

    def test_two_group_writers_not_in_app(self):
        """anvil_audit works correctly if this workspace has two group writers not in the app."""
        self.update_api_response("test-writer-1@firecloud.org", "WRITER")
        self.update_api_response("test-writer-2@firecloud.org", "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(model_result.record, "WRITER: test-writer-1@firecloud.org")
        model_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(model_result.record, "WRITER: test-writer-2@firecloud.org")

    def test_one_group_admin_case_insensitive(self):
        """anvil_audit works correctly if this workspace has one group member not in the app."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            group__name="tEsT-wRiTeR",
            access=models.WorkspaceGroupSharing.WRITER,
        )
        self.update_api_response("Test-Writer@firecloud.org", "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_one_group_owner(self):
        """anvil_audit works correctly if this workspace has one group owner."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        self.update_api_response(access.group.email, "OWNER", can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_two_group_owners(self):
        """anvil_audit works correctly if this workspace has two group owners."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        access_2 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        self.update_api_response(access_1.group.email, "OWNER", can_share=True)
        self.update_api_response(access_2.group.email, "OWNER", can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertTrue(model_result.ok())
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertTrue(model_result.ok())

    def test_one_group_owner_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has one group owners not in anvil."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_two_group_owners_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has two group owners not in anvil."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        access_2 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access_1)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))
        model_result = audit_results.get_result_for_model_instance(access_2)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_NOT_SHARED_IN_ANVIL]))

    def test_one_group_owner_not_in_app(self):
        """anvil_audit works correctly if this workspace has one group owner not in the app."""
        self.update_api_response("test-writer@firecloud.org", "OWNER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(model_result.record, "OWNER: test-writer@firecloud.org")

    def test_two_group_owners_not_in_app(self):
        """anvil_audit works correctly if this workspace has two group owners not in the app."""
        self.update_api_response("test-writer-1@firecloud.org", "OWNER")
        self.update_api_response("test-writer-2@firecloud.org", "OWNER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        model_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(model_result.record, "OWNER: test-writer-1@firecloud.org")
        model_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(model_result.record, "OWNER: test-writer-2@firecloud.org")

    def test_one_group_owner_case_insensitive(self):
        """anvil_audit works correctly with different cases for owner emails."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            group__name="tEsT-oWnEr",
            access=models.WorkspaceGroupSharing.OWNER,
        )
        self.update_api_response("Test-Owner@firecloud.org", "OWNER", can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertTrue(model_result.ok())

    def test_group_different_access_reader_in_app_writer_in_anvil(self):
        """anvil_audit works correctly if a group has different access to a workspace in AnVIL."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.READER
        )
        self.update_api_response(access.group.email, "WRITER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_DIFFERENT_ACCESS]))

    def test_group_different_access_reader_in_app_owner_in_anvil(self):
        """anvil_audit works correctly if a group has different access to a workspace in AnVIL."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.READER
        )
        self.update_api_response(access.group.email, "OWNER", can_compute=True, can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(
            model_result.errors,
            set(
                [
                    audit_results.ERROR_DIFFERENT_ACCESS,
                    audit_results.ERROR_DIFFERENT_CAN_COMPUTE,
                    audit_results.ERROR_DIFFERENT_CAN_SHARE,
                ]
            ),
        )

    def test_group_different_can_compute(self):
        """anvil_audit works correctly if can_compute is different between the app and AnVIL."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        self.update_api_response(access.group.email, "WRITER", can_compute=False)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_DIFFERENT_CAN_COMPUTE]))

    def test_group_different_can_share(self):
        """anvil_audit works correctly if can_share is True in AnVIL."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        self.update_api_response(access.group.email, "WRITER", can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_DIFFERENT_CAN_SHARE]))

    def test_removes_service_account(self):
        """Removes the service account from acl if it exists."""
        self.update_api_response(self.service_account_email, "OWNER", can_compute=True, can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_group_owner_can_share_true(self):
        """Owners must have can_share=True."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=models.WorkspaceGroupSharing.OWNER,
            can_compute=True,
        )
        self.update_api_response(access.group.email, "OWNER", can_compute=True, can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_group_writer_can_share_false(self):
        """Writers must have can_share=False."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        self.update_api_response(access.group.email, "WRITER", can_compute=True, can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_DIFFERENT_CAN_SHARE]))

    def test_group_reader_can_share_false(self):
        """Readers must have can_share=False."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=models.WorkspaceGroupSharing.READER,
            can_compute=False,
        )
        self.update_api_response(access.group.email, "READER", can_compute=False, can_share=True)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = audit.WorkspaceSharingAudit(self.workspace)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        model_result = audit_results.get_result_for_model_instance(access)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_DIFFERENT_CAN_SHARE]))
