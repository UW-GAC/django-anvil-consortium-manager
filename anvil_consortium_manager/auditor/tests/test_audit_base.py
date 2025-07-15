from django.test import TestCase, override_settings
from django.utils import timezone
from django_tables2 import Table
from faker import Faker

from anvil_consortium_manager.tests.factories import (
    AccountFactory,
    BillingProjectFactory,
    ManagedGroupFactory,
    WorkspaceFactory,
)

from ..audit import base
from . import factories

fake = Faker()


class TestAudit(base.AnVILAudit):
    TEST_ERROR_1 = "Test error 1"
    TEST_ERROR_2 = "Test error 2"

    cache_key = "test_audit_cache"

    def audit(self, cache=False):
        pass


class ModelInstanceResultTest(TestCase):
    def test_init(self):
        """Constructor works as expected."""
        obj = AccountFactory.create()
        result = base.ModelInstanceResult(obj)
        self.assertEqual(result.model_instance, obj)
        self.assertEqual(result.errors, set())

    def test_str(self):
        """__str__ method works as expected."""
        obj = AccountFactory.create()
        result = base.ModelInstanceResult(obj)
        self.assertEqual(str(result), (str(obj)))

    def test_eq_no_errors(self):
        """__eq__ method works as expected when there are no errors."""
        obj = AccountFactory.create()
        result_1 = base.ModelInstanceResult(obj)
        result_2 = base.ModelInstanceResult(obj)
        self.assertEqual(result_1, result_2)

    def test_eq_errors(self):
        """__eq__ method works as expected when there are errors."""
        obj = AccountFactory.create()
        result_1 = base.ModelInstanceResult(obj)
        result_1.add_error("foo")
        result_2 = base.ModelInstanceResult(obj)
        self.assertNotEqual(result_1, result_2)
        result_2.add_error("foo")
        self.assertEqual(result_1, result_2)

    def test_add_error(self):
        """add_error method works as expected."""
        obj = AccountFactory.create()
        result = base.ModelInstanceResult(obj)
        result.add_error("foo")
        self.assertEqual(result.errors, set(["foo"]))
        result.add_error("bar")
        self.assertEqual(result.errors, set(["foo", "bar"]))

    def test_add_error_duplicate(self):
        """can add a second, duplicate error without error."""
        obj = AccountFactory.create()
        result = base.ModelInstanceResult(obj)
        result.add_error("foo")
        self.assertEqual(result.errors, set(["foo"]))
        result.add_error("foo")
        self.assertEqual(result.errors, set(["foo"]))

    def test_ok_no_errors(self):
        """ok method returns True when there are no errors."""
        obj = AccountFactory.create()
        result = base.ModelInstanceResult(obj)
        self.assertTrue(result.ok())

    def test_ok_errors(self):
        """ok method returns False when there are errors."""
        obj = AccountFactory.create()
        result = base.ModelInstanceResult(obj)
        result.add_error("foo")
        self.assertFalse(result.ok())


class NotInAppResultTest(TestCase):
    def test_init(self):
        """Constructor works as expected."""
        result = base.NotInAppResult("foo bar")
        self.assertEqual(result.record, "foo bar")

    def test_str(self):
        """__str__ method works as expected."""
        result = base.NotInAppResult("foo bar")
        self.assertEqual(str(result), "foo bar")

    def test_eq(self):
        """__eq__ method works as expected."""
        result = base.NotInAppResult("foo")
        self.assertEqual(base.NotInAppResult("foo"), result)
        self.assertNotEqual(base.NotInAppResult("bar"), result)


class IgnoredResultTest(TestCase):
    def test_init(self):
        """Constructor works as expected."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        result = base.IgnoredResult(obj, record="foo")
        self.assertEqual(result.model_instance, obj)
        self.assertEqual(result.record, "foo")

    def test_str(self):
        """__str__ method works as expected."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        result = base.IgnoredResult(obj, record="foo")
        self.assertEqual(str(result), "foo")

    def test_eq(self):
        """__eq__ method works as expected when there are no errors."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        result_1 = base.IgnoredResult(obj, record="foo")
        result_2 = base.IgnoredResult(obj, record="foo")
        self.assertEqual(result_1, result_2)

    def test_eq_not_equal_obj(self):
        """__eq__ method works as expected when there are no errors."""
        obj_1 = factories.IgnoredManagedGroupMembershipFactory.create()
        result_1 = base.IgnoredResult(obj_1, record="foo")
        obj_2 = factories.IgnoredManagedGroupMembershipFactory.create()
        result_2 = base.IgnoredResult(obj_2, record="foo")
        self.assertNotEqual(result_1, result_2)

    def test_eq_not_equal_record(self):
        """__eq__ method works as expected when there are no errors."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        result_1 = base.IgnoredResult(obj, record="foo")
        result_2 = base.IgnoredResult(obj, record="bar")
        self.assertNotEqual(result_1, result_2)


class VerifiedTableTest(TestCase):
    def test_zero_rows(self):
        results = []
        table = base.VerifiedTable(results)
        self.assertEqual(len(table.rows), 0)

    def test_one_row(self):
        results = [base.ModelInstanceResult(AccountFactory())]
        table = base.VerifiedTable(results)
        self.assertEqual(len(table.rows), 1)

    def test_two_rows(self):
        results = [
            base.ModelInstanceResult(AccountFactory()),
            base.ModelInstanceResult(AccountFactory()),
        ]
        table = base.VerifiedTable(results)
        self.assertEqual(len(table.rows), 2)


class ErrorTableTest(TestCase):
    def test_zero_rows(self):
        results = []
        table = base.ErrorTable(results)
        self.assertEqual(len(table.rows), 0)

    def test_one_row(self):
        results = [base.ModelInstanceResult(AccountFactory())]
        table = base.ErrorTable(results)
        self.assertEqual(len(table.rows), 1)

    def test_two_rows(self):
        result_1 = base.ModelInstanceResult(AccountFactory())
        result_1.add_error("foo")
        result_2 = base.ModelInstanceResult(AccountFactory())
        result_2.add_error("bar")
        results = [result_1, result_2]
        table = base.ErrorTable(results)
        self.assertEqual(len(table.rows), 2)


class AnVILAuditTest(TestCase):
    """Tests for the AnVILAudit abstract base class."""

    def setUp(self):
        super().setUp()

        self.audit_results = TestAudit()
        # It doesn't matter what model we use at this point, so just pick Account.
        self.model_factory = AccountFactory

    def test_init(self):
        """Init method works as expected."""
        self.assertEqual(len(self.audit_results._model_instance_results), 0)
        self.assertEqual(len(self.audit_results._not_in_app_results), 0)

    def test_timestamp(self):
        """Timestamp is set by default."""
        self.assertIsNotNone(self.audit_results.timestamp)
        self.assertTrue(isinstance(self.audit_results.timestamp, timezone.datetime))

    def test_ok_no_results(self):
        """ok() returns True when there are no results."""
        self.assertTrue(self.audit_results.ok())

    def test_ok_one_result_ok(self):
        """ok() returns True when there is one ok result."""
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        self.assertTrue(self.audit_results.ok())

    def test_ok_two_results_ok(self):
        """ok() returns True when there is one ok result."""
        model_instance_result_1 = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result_2)
        self.assertTrue(self.audit_results.ok())

    def test_ok_one_result_with_errors(self):
        """ok() returns True when there is one ok result."""
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        model_instance_result.add_error("foo")
        self.audit_results.add_result(model_instance_result)
        self.assertFalse(self.audit_results.ok())

    def test_ok_one_not_in_app(self):
        """ok() returns True when there are no results."""
        self.audit_results.add_result(base.NotInAppResult("foo"))
        self.assertFalse(self.audit_results.ok())

    def test_ok_one_ignored(self):
        """ok() returns True when there is one ignored result."""
        self.audit_results.add_result(
            base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create(), "foo"),
        )
        self.assertTrue(self.audit_results.ok())

    def test_run_audit_not_implemented(self):
        class CustomAudit(base.AnVILAudit):
            pass

        audit_results = CustomAudit()
        with self.assertRaises(NotImplementedError):
            audit_results.run_audit()

    def test_add_result_not_in_app(self):
        """Can add a NotInAppResult."""
        not_in_app_result = base.NotInAppResult("foo")
        self.audit_results.add_result(not_in_app_result)
        self.assertEqual(len(self.audit_results._not_in_app_results), 1)

    def test_add_result_ignored(self):
        """Can add an IgnoredResult."""
        ignored_result = base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create(), record="foo")
        self.audit_results.add_result(ignored_result)
        self.assertEqual(len(self.audit_results._ignored_results), 1)

    def test_add_result_wrong_class(self):
        """Can add a NotInAppResult."""
        with self.assertRaises(ValueError):
            self.audit_results.add_result("foo")

    def test_add_result_duplicate_not_in_app(self):
        """Cannot add a duplicate NotInAppResult."""
        not_in_app_result = base.NotInAppResult("foo")
        self.audit_results.add_result(not_in_app_result)
        # import ipdb; ipdb.set_trace()
        with self.assertRaises(ValueError):
            self.audit_results.add_result(not_in_app_result)
        self.assertEqual(len(self.audit_results._not_in_app_results), 1)

    def test_add_result_not_in_app_same_record(self):
        """Cannot add a duplicate NotInAppResult."""
        not_in_app_result = base.NotInAppResult("foo")
        self.audit_results.add_result(not_in_app_result)
        # import ipdb; ipdb.set_trace()
        with self.assertRaises(ValueError):
            self.audit_results.add_result(base.NotInAppResult("foo"))
        self.assertEqual(len(self.audit_results._not_in_app_results), 1)

    def test_add_result_ignored_duplicate(self):
        """Can add an IgnoredResult."""
        ignored_result = base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create(), record="foo")
        self.audit_results.add_result(ignored_result)
        with self.assertRaises(ValueError):
            self.audit_results.add_result(ignored_result)

    def test_add_result_ignored_equal(self):
        """Can add an IgnoredResult."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        ignored_result_1 = base.IgnoredResult(obj, record="foo")
        ignored_result_2 = base.IgnoredResult(obj, record="foo")
        self.audit_results.add_result(ignored_result_1)
        with self.assertRaises(ValueError):
            self.audit_results.add_result(ignored_result_2)

    def test_add_result_model_instance(self):
        """Can add a model instance result."""
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results._model_instance_results), 1)

    def test_add_result_duplicate_model_instance_result(self):
        """Cannot add a duplicate model instance result."""
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        # import ipdb; ipdb.set_trace()
        with self.assertRaises(ValueError):
            self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results._model_instance_results), 1)

    def test_add_result_second_result_for_same_model_instance(self):
        obj = self.model_factory()
        model_instance_result_1 = base.ModelInstanceResult(obj)
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = base.ModelInstanceResult(obj)
        # import ipdb; ipdb.set_trace()
        with self.assertRaises(ValueError):
            self.audit_results.add_result(model_instance_result_2)
        self.assertEqual(len(self.audit_results._model_instance_results), 1)
        self.assertEqual(self.audit_results._model_instance_results, [model_instance_result_1])

    def test_add_result_second_result_for_same_model_instance_with_error(self):
        obj = self.model_factory()
        model_instance_result_1 = base.ModelInstanceResult(obj)
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = base.ModelInstanceResult(obj)
        model_instance_result_2.add_error("Foo")
        with self.assertRaises(ValueError):
            self.audit_results.add_result(model_instance_result_2)
        self.assertEqual(len(self.audit_results._model_instance_results), 1)
        self.assertEqual(self.audit_results._model_instance_results, [model_instance_result_1])

    def test_get_result_for_model_instance_no_matches(self):
        obj = self.model_factory()
        base.ModelInstanceResult(obj)
        with self.assertRaises(ValueError):
            self.audit_results.get_result_for_model_instance(obj)

    def test_get_result_for_model_instance_one_match(self):
        obj = self.model_factory()
        model_instance_result = base.ModelInstanceResult(obj)
        self.audit_results.add_result(model_instance_result)
        result = self.audit_results.get_result_for_model_instance(obj)
        self.assertIs(result, model_instance_result)

    def test_get_verified_results_no_results(self):
        """get_verified_results returns an empty list when there are no results."""
        self.assertEqual(len(self.audit_results.get_verified_results()), 0)

    def test_get_verified_results_one_verified_result(self):
        """get_verified_results returns a list when there is one result."""
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_verified_results()), 1)
        self.assertIn(model_instance_result, self.audit_results.get_verified_results())

    def test_get_error_results_two_verified_result(self):
        """get_verified_results returns a list of lenght two when there are two verified results."""
        model_instance_result_1 = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result_2)
        self.assertEqual(len(self.audit_results.get_verified_results()), 2)
        self.assertIn(model_instance_result_1, self.audit_results.get_verified_results())
        self.assertIn(model_instance_result_2, self.audit_results.get_verified_results())

    def test_get_verified_results_one_error_result(self):
        """get_verified_results returns a list of lenght zero when there is one error result."""
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        model_instance_result.add_error("foo")
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_verified_results()), 0)

    def test_get_verified_results_one_not_in_app_result(self):
        """get_verified_results returns a list of lenght zero when there is one not_in_app result."""
        self.audit_results.add_result(base.NotInAppResult("foo"))
        self.assertEqual(len(self.audit_results.get_verified_results()), 0)

    def test_get_verified_results_one_ignored_result(self):
        """get_verified_results returns a list of lenght zero when there is one ignored result."""
        self.audit_results.add_result(
            base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create(), record="foo")
        )
        self.assertEqual(len(self.audit_results.get_verified_results()), 0)

    def test_get_error_results_no_results(self):
        """get_error_results returns an empty list when there are no results."""
        self.assertEqual(len(self.audit_results.get_error_results()), 0)

    def test_get_error_results_one_verified_result(self):
        """get_error_results returns a list of length zero when there is one verified result."""
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_error_results()), 0)

    def test_get_error_results_one_error_result(self):
        """get_error_results returns a list of lenght one when there is one error result."""
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        model_instance_result.add_error("foo")
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_error_results()), 1)
        self.assertIn(model_instance_result, self.audit_results.get_error_results())

    def test_get_error_results_two_error_result(self):
        """get_error_results returns a list of lenght two when there is one result."""
        model_instance_result_1 = base.ModelInstanceResult(self.model_factory())
        model_instance_result_1.add_error("foo")
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = base.ModelInstanceResult(self.model_factory())
        model_instance_result_2.add_error("foo")
        self.audit_results.add_result(model_instance_result_2)
        self.assertEqual(len(self.audit_results.get_error_results()), 2)
        self.assertIn(model_instance_result_1, self.audit_results.get_error_results())
        self.assertIn(model_instance_result_2, self.audit_results.get_error_results())

    def test_get_error_results_one_not_in_app_result(self):
        """get_error_results returns a list of length zero when there is one not_in_app result."""
        self.audit_results.add_result(base.NotInAppResult("foo"))
        self.assertEqual(len(self.audit_results.get_error_results()), 0)

    def test_get_error_results_one_ignored_result(self):
        """get_verified_results returns a list of lenght zero when there is one ignored result."""
        self.audit_results.add_result(
            base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create(), record="foo")
        )
        self.assertEqual(len(self.audit_results.get_error_results()), 0)

    def test_get_not_in_app_results_no_results(self):
        """get_not_in_app_results returns an empty list when there are no results."""
        self.assertEqual(len(self.audit_results.get_not_in_app_results()), 0)

    def test_get_not_in_app_results_one_verified_result(self):
        """get_not_in_app_results returns a list of length zero when there is one verified result."""
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_not_in_app_results()), 0)

    def test_get_not_in_app_results_one_error_result(self):
        """get_not_in_app_results returns a list of lenght one when there is one error result."""
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        model_instance_result.add_error("foo")
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_not_in_app_results()), 0)

    def test_get_not_in_app_results_one_not_in_app_result(self):
        """get_not_in_app_results returns a list of length zero when there is one not_in_app result."""
        result = base.NotInAppResult("foo")
        self.audit_results.add_result(result)
        self.assertEqual(len(self.audit_results.get_not_in_app_results()), 1)
        self.assertIn(result, self.audit_results.get_not_in_app_results())

    def test_get_not_in_app_results_two_not_in_app_results(self):
        """get_not_in_app_results returns a list of lenght two when there is one result."""
        result_1 = base.NotInAppResult("foo")
        self.audit_results.add_result(result_1)
        result_2 = base.NotInAppResult("bar")
        self.audit_results.add_result(result_2)
        self.assertEqual(len(self.audit_results.get_not_in_app_results()), 2)
        self.assertIn(result_1, self.audit_results.get_not_in_app_results())
        self.assertIn(result_2, self.audit_results.get_not_in_app_results())

    def test_get_not_in_app_results_one_ignored_result(self):
        """get_verified_results returns a list of lenght zero when there is one ignored result."""
        self.audit_results.add_result(
            base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create(), record="foo")
        )
        self.assertEqual(len(self.audit_results.get_not_in_app_results()), 0)

    def test_get_ignored_results_no_results(self):
        """get_ignored_results returns an empty list when there are no results."""
        self.assertEqual(len(self.audit_results.get_ignored_results()), 0)

    def test_get_ignored_results_one_result(self):
        """get_ignored_results returns a list when there is one result."""
        result = base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create(), record="foo")
        self.audit_results.add_result(result)
        self.assertEqual(len(self.audit_results.get_ignored_results()), 1)
        self.assertIn(result, self.audit_results.get_ignored_results())

    def test_get_ignored_results_two_results(self):
        """get_ignored_results returns a list of lenght two when there are two verified results."""
        result_1 = base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create(), record="foo")
        self.audit_results.add_result(result_1)
        result_2 = base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create(), record="bar")
        self.audit_results.add_result(result_2)
        self.assertEqual(len(self.audit_results.get_ignored_results()), 2)
        self.assertIn(result_1, self.audit_results.get_ignored_results())
        self.assertIn(result_2, self.audit_results.get_ignored_results())

    def test_get_ignored_results_one_verified_result(self):
        """get_ignored_results returns a list of lenght zero when there is one verified result."""
        self.audit_results.add_result(base.ModelInstanceResult(self.model_factory()))
        self.assertEqual(len(self.audit_results.get_ignored_results()), 0)

    def test_get_ignored_results_one_error_result(self):
        """get_ignored_results returns a list of lenght zero when there is one error result."""
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        model_instance_result.add_error("foo")
        self.audit_results.add_result(model_instance_result)
        self.assertEqual(len(self.audit_results.get_ignored_results()), 0)

    def test_get_ignored_results_one_not_in_app_result(self):
        """get_ignored_results returns a list of length zero when there is one not_in_app result."""
        self.audit_results.add_result(base.NotInAppResult("foo"))
        self.assertEqual(len(self.audit_results.get_ignored_results()), 0)

    def test_get_verified_table_no_results(self):
        table = self.audit_results.get_verified_table()
        self.assertIsInstance(table, base.VerifiedTable)
        self.assertEqual(len(table.rows), 0)

    def test_get_verified_table_one_result(self):
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result)
        table = self.audit_results.get_verified_table()
        self.assertEqual(len(table.rows), 1)
        self.assertIn(model_instance_result, table.data)

    def test_get_verified_table_two_results(self):
        model_instance_result_1 = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(model_instance_result_2)
        table = self.audit_results.get_verified_table()
        self.assertEqual(len(table.rows), 2)
        self.assertIn(model_instance_result_1, table.data)
        self.assertIn(model_instance_result_2, table.data)

    def test_get_verified_table_custom_class(self):
        class CustomTable(Table):
            pass

        class CustomAudit(base.AnVILAudit):
            verified_table_class = CustomTable

        audit_results = CustomAudit()
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        audit_results.add_result(model_instance_result)
        table = audit_results.get_verified_table()
        self.assertIsInstance(table, CustomTable)
        self.assertEqual(len(table.rows), 1)
        self.assertIn(model_instance_result, table.data)

    def test_get_error_table_no_results(self):
        table = self.audit_results.get_error_table()
        self.assertIsInstance(table, base.ErrorTable)
        self.assertEqual(len(table.rows), 0)

    def test_get_error_table_one_result(self):
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        model_instance_result.add_error("foo")
        self.audit_results.add_result(model_instance_result)
        table = self.audit_results.get_error_table()
        self.assertEqual(len(table.rows), 1)
        self.assertIn(model_instance_result, table.data)

    def test_get_error_table_two_results(self):
        model_instance_result_1 = base.ModelInstanceResult(self.model_factory())
        model_instance_result_1.add_error("foo")
        self.audit_results.add_result(model_instance_result_1)
        model_instance_result_2 = base.ModelInstanceResult(self.model_factory())
        model_instance_result_2.add_error("bar")
        self.audit_results.add_result(model_instance_result_2)
        table = self.audit_results.get_error_table()
        self.assertEqual(len(table.rows), 2)
        self.assertIn(model_instance_result_1, table.data)
        self.assertIn(model_instance_result_2, table.data)

    def test_get_error_table_custom_class(self):
        class CustomTable(Table):
            pass

        class CustomAudit(base.AnVILAudit):
            error_table_class = CustomTable

        audit_results = CustomAudit()
        model_instance_result = base.ModelInstanceResult(self.model_factory())
        model_instance_result.add_error("foo")
        audit_results.add_result(model_instance_result)
        table = audit_results.get_error_table()
        self.assertIsInstance(table, CustomTable)
        self.assertEqual(len(table.rows), 1)
        self.assertIn(model_instance_result, table.data)

    def test_get_not_in_app_table_no_results(self):
        table = self.audit_results.get_not_in_app_table()
        self.assertIsInstance(table, base.NotInAppTable)
        self.assertEqual(len(table.rows), 0)

    def test_get_not_in_app_table_one_result(self):
        result = base.NotInAppResult("foo")
        self.audit_results.add_result(result)
        table = self.audit_results.get_not_in_app_table()
        self.assertEqual(len(table.rows), 1)
        self.assertIn(result, table.data)

    def test_get_not_in_app_table_two_results(self):
        result_1 = base.NotInAppResult("foo")
        self.audit_results.add_result(result_1)
        result_2 = base.NotInAppResult("bar")
        self.audit_results.add_result(result_2)
        table = self.audit_results.get_not_in_app_table()
        self.assertEqual(len(table.rows), 2)
        self.assertIn(result_1, table.data)
        self.assertIn(result_2, table.data)

    def test_get_not_in_app_table_custom_class(self):
        class CustomTable(Table):
            pass

        class CustomAudit(base.AnVILAudit):
            not_in_app_table_class = CustomTable

        audit_results = CustomAudit()
        result = base.NotInAppResult("foo")
        audit_results.add_result(result)
        table = audit_results.get_not_in_app_table()
        self.assertIsInstance(table, CustomTable)
        self.assertEqual(len(table.rows), 1)
        self.assertIn(result, table.data)

    def test_get_ignored_table_no_results(self):
        table = self.audit_results.get_ignored_table()
        self.assertIsInstance(table, base.IgnoredTable)
        self.assertEqual(len(table.rows), 0)

    def test_get_ignored_table_one_result(self):
        result = base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create())
        self.audit_results.add_result(result)
        table = self.audit_results.get_ignored_table()
        self.assertEqual(len(table.rows), 1)
        self.assertIn(result, table.data)

    def test_get_ignored_table_two_results(self):
        result_1 = base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create())
        self.audit_results.add_result(result_1)
        result_2 = base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create())
        self.audit_results.add_result(result_2)
        table = self.audit_results.get_ignored_table()
        self.assertEqual(len(table.rows), 2)
        self.assertIn(result_1, table.data)
        self.assertIn(result_2, table.data)

    def test_get_ignored_table_custom_class(self):
        class CustomTable(Table):
            pass

        class CustomAudit(base.AnVILAudit):
            ignored_table_class = CustomTable

        audit_results = CustomAudit()
        result = base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create())
        audit_results.add_result(result)
        table = audit_results.get_ignored_table()
        self.assertIsInstance(table, CustomTable)
        self.assertEqual(len(table.rows), 1)
        self.assertIn(result, table.data)

    def test_export(self):
        # One Verified result.
        verified_result = base.ModelInstanceResult(self.model_factory())
        self.audit_results.add_result(verified_result)
        # One error result.
        error_result = base.ModelInstanceResult(self.model_factory())
        error_result.add_error("foo")
        self.audit_results.add_result(error_result)
        # Not in app result.
        not_in_app_result = base.NotInAppResult("bar")
        self.audit_results.add_result(not_in_app_result)
        # Ignored result
        ignored_result = base.IgnoredResult(factories.IgnoredManagedGroupMembershipFactory.create(), record="foobar")
        self.audit_results.add_result(ignored_result)
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
        self.assertIn("ignored", exported_data)
        self.assertEqual(
            exported_data["ignored"],
            [
                {
                    "id": ignored_result.model_instance.pk,
                    "instance": ignored_result.model_instance,
                    "record": "foobar",
                }
            ],
        )

    def test_export_include_verified_false(self):
        exported_data = self.audit_results.export(include_verified=False)
        self.assertNotIn("verified", exported_data)
        self.assertIn("errors", exported_data)
        self.assertIn("not_in_app", exported_data)
        self.assertIn("ignored", exported_data)

    def test_export_include_errors_false(self):
        exported_data = self.audit_results.export(include_errors=False)
        self.assertIn("verified", exported_data)
        self.assertNotIn("errors", exported_data)
        self.assertIn("not_in_app", exported_data)
        self.assertIn("ignored", exported_data)

    def test_export_include_not_in_app_false(self):
        exported_data = self.audit_results.export(include_not_in_app=False)
        self.assertIn("verified", exported_data)
        self.assertIn("errors", exported_data)
        self.assertNotIn("not_in_app", exported_data)
        self.assertIn("ignored", exported_data)

    def test_export_include_ignored_false(self):
        exported_data = self.audit_results.export(include_ignored=False)
        self.assertIn("verified", exported_data)
        self.assertIn("errors", exported_data)
        self.assertIn("not_in_app", exported_data)
        self.assertNotIn("ignored", exported_data)

    def test_export_not_in_app_sorted(self):
        """export sorts the not_in_app results."""
        self.audit_results.add_result(base.NotInAppResult("foo"))
        self.audit_results.add_result(base.NotInAppResult("bar"))
        exported_data = self.audit_results.export()
        self.assertEqual(exported_data["not_in_app"], ["bar", "foo"])

    def test_get_cache_key_not_set(self):
        """get_cache_key raises NotImplementedError if not set."""

        class CustomAudit(base.AnVILAudit):
            pass

        audit_results = CustomAudit()
        with self.assertRaises(NotImplementedError):
            audit_results.get_cache_key()

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.db.DatabaseCache",
                "OPTIONS": {"MAX_ENTRIES": 6},
            },
        }
    )
    def test_cache_size_warning_equal_size(self):
        """Cache size warning is logged when required cache size exceeds limit."""
        audit_results = TestAudit()
        # Create one billing project, one account, one group, and one workspace.
        # This requires a cache size of 4 (each model overall) + 2 (sharing and membership).
        BillingProjectFactory.create()
        AccountFactory.create()
        ManagedGroupFactory.create()
        WorkspaceFactory.create()
        # Cache setting that is equal to the required number of entries.
        with self.assertNoLogs(base.logger.name, level="WARNING"):
            audit_results.run_audit(cache=True)

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.db.DatabaseCache",
                "OPTIONS": {"MAX_ENTRIES": 5},
            },
        }
    )
    def test_cache_size_warning_too_small(self):
        """Cache size warning is logged when required cache size exceeds limit."""
        audit_results = TestAudit()
        # Create one billing project, one account, one group, and one workspace.
        # This requires a cache size of 4 (each model overall) + 2 (sharing and membership).
        BillingProjectFactory.create()
        AccountFactory.create()
        ManagedGroupFactory.create()
        WorkspaceFactory.create()
        # Cache setting that is equal to the required number of entries.
        with self.assertLogs(base.logger.name, "WARNING") as cm:
            audit_results.run_audit(cache=True)
            self.assertIn("maximum size of at least 6 entries", cm.output[0])

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.db.DatabaseCache",
                "OPTIONS": {"MAX_ENTRIES": 5},
            },
        }
    )
    def test_cache_size_no_warning_in_log_if_cache_is_false(self):
        """No cache size warning is logged if cache is False."""
        audit_results = TestAudit()
        # Create one billing project, one account, one group, and one workspace.
        # This requires a cache size of 4 (each model overall) + 2 (sharing and membership).
        BillingProjectFactory.create()
        AccountFactory.create()
        ManagedGroupFactory.create()
        WorkspaceFactory.create()
        # No warning when we are not caching.
        with self.assertNoLogs(base.logger.name, level="WARNING"):
            audit_results.run_audit(cache=False)
