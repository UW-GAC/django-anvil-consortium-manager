from django.test import TestCase

from ..anvil_audit import AnVILAuditResults
from .factories import AccountFactory


class AnVILAuditTest(TestCase):
    """General tests of the AnVILAuditResults base class"""

    def setUp(self):
        class GenericAuditResults(AnVILAuditResults):
            TEST_ERROR_1 = "Test error 1"
            TEST_ERROR_2 = "Test error 2"
            allowed_errors = (
                TEST_ERROR_1,
                TEST_ERROR_2,
            )

        self.audit_results = GenericAuditResults()
        # It doesn't matter what model we use at this point, so just pick Account.
        self.model_factory = AccountFactory

    def test_add_verified(self):
        """Can add a verified record."""
        obj = self.model_factory.create()
        self.audit_results.add_verified(obj)
        self.assertEqual(self.audit_results.get_verified(), set([obj]))

    def test_add_verified_when_instance_has_an_error(self):
        """add_verified raises a ValueError if the mdoel instance already has an error."""
        obj = self.model_factory.create()
        self.audit_results.add_error(obj, self.audit_results.TEST_ERROR_1)
        with self.assertRaises(ValueError) as e:
            self.audit_results.add_verified(obj)
        self.assertIn("has reported errors", str(e.exception))
        self.assertEqual(self.audit_results.get_verified(), set())
        self.assertEqual(
            self.audit_results.get_errors(), {obj: [self.audit_results.TEST_ERROR_1]}
        )

    def test_add_error(self):
        """Can add an error for a model instance."""
        obj = self.model_factory.create()
        self.audit_results.add_error(obj, self.audit_results.TEST_ERROR_1)
        self.assertEqual(
            self.audit_results.get_errors(), {obj: [self.audit_results.TEST_ERROR_1]}
        )

    def test_add_error_two_errors(self):
        """Can add two errors for a model instance."""
        obj = self.model_factory.create()
        self.audit_results.add_error(obj, self.audit_results.TEST_ERROR_1)
        self.audit_results.add_error(obj, self.audit_results.TEST_ERROR_2)
        self.assertEqual(
            self.audit_results.get_errors(),
            {obj: [self.audit_results.TEST_ERROR_1, self.audit_results.TEST_ERROR_2]},
        )

    def test_add_error_error_not_allowed(self):
        """Cannot call add_error with an error that is not in the allowed_errors dictionary."""
        obj = self.model_factory.create()
        with self.assertRaises(ValueError) as e:
            self.audit_results.add_error(obj, "foo")
        self.assertIn("not an allowed error", str(e.exception))
        self.assertEqual(self.audit_results.get_errors(), {})

    def test_add_error_when_instance_is_verified(self):
        """add_error raises a ValueError if the mdoel instance is already verified."""
        obj = self.model_factory.create()
        self.audit_results.add_verified(obj)
        with self.assertRaises(ValueError) as e:
            self.audit_results.add_error(obj, self.audit_results.TEST_ERROR_1)
        self.assertIn("already verified", str(e.exception))
        self.assertEqual(self.audit_results.get_verified(), set([obj]))
        self.assertEqual(self.audit_results.get_errors(), {})

    def test_add_not_in_app(self):
        """Can add a record with add_not_in_app"""
        self.audit_results.add_not_in_app("foo")
        self.assertEqual(self.audit_results.get_not_in_app(), set(["foo"]))

    def test_add_not_in_app_two_records(self):
        """Can add two records with add_not_in_app"""
        self.audit_results.add_not_in_app("foo")
        self.audit_results.add_not_in_app("bar")
        self.assertEqual(self.audit_results.get_not_in_app(), set(["foo", "bar"]))

    def test_ok_no_verified(self):
        """ok() returns True when there are no verified and no errors."""
        self.assertEqual(self.audit_results.ok(), True)

    def test_ok_no_errors(self):
        """ok() returns True when there ais one verified and no errors."""
        obj = self.model_factory.create()
        self.audit_results.add_verified(obj)
        self.assertEqual(self.audit_results.ok(), True)

    def test_ok_one_error(self):
        """ok() returns False when there is no verified and one error."""
        obj = self.model_factory.create()
        self.audit_results.add_error(obj, self.audit_results.TEST_ERROR_1)
        self.assertEqual(self.audit_results.ok(), False)

    def test_ok_one_verified_one_error(self):
        """ok() returns False when there is no verified and one error."""
        obj_verified = self.model_factory.create()
        obj_error = self.model_factory.create()
        self.audit_results.add_verified(obj_verified)
        self.audit_results.add_error(obj_error, self.audit_results.TEST_ERROR_1)
        self.assertEqual(self.audit_results.ok(), False)

    def test_ok_one_not_in_app(self):
        """ok() returns False when there is no verified and one not_in_app."""
        self.audit_results.add_not_in_app("foo")
        self.assertEqual(self.audit_results.ok(), False)

    def test_ok_one_verified_one_not_in_app(self):
        """ok() returns False when there is no verified and one notin_app."""
        obj = self.model_factory.create()
        self.audit_results.add_verified(obj)
        self.audit_results.add_not_in_app("foo")
        self.assertEqual(self.audit_results.ok(), False)

    def test_export(self):
        """export method works as expected."""
        obj_verified = self.model_factory.create()
        self.audit_results.add_verified(obj_verified)
        obj_error = self.model_factory.create()
        self.audit_results.add_error(obj_error, self.audit_results.TEST_ERROR_1)
        self.audit_results.add_not_in_app("foo")
        expected_json = {
            "verified": [{"instance": obj_verified, "id": obj_verified.pk}],
            "errors": [
                {
                    "id": obj_error.pk,
                    "instance": obj_error,
                    "errors": [self.audit_results.TEST_ERROR_1],
                }
            ],
            "not_in_app": ["foo"],
        }
        self.assertEqual(self.audit_results.export(), expected_json)

    def test_export_include_verified_false(self):
        """export method works as expected."""
        obj_verified = self.model_factory.create()
        self.audit_results.add_verified(obj_verified)
        obj_error = self.model_factory.create()
        self.audit_results.add_error(obj_error, self.audit_results.TEST_ERROR_1)
        self.audit_results.add_not_in_app("foo")
        expected_json = {
            "errors": [
                {
                    "id": obj_error.pk,
                    "instance": obj_error,
                    "errors": [self.audit_results.TEST_ERROR_1],
                }
            ],
            "not_in_app": ["foo"],
        }
        self.assertEqual(
            self.audit_results.export(include_verified=False), expected_json
        )

    def test_export_include_errors_false(self):
        """export method works as expected."""
        obj_verified = self.model_factory.create()
        self.audit_results.add_verified(obj_verified)
        obj_error = self.model_factory.create()
        self.audit_results.add_error(obj_error, self.audit_results.TEST_ERROR_1)
        self.audit_results.add_not_in_app("foo")
        expected_json = {
            "verified": [{"instance": obj_verified, "id": obj_verified.pk}],
            "not_in_app": ["foo"],
        }
        self.assertEqual(self.audit_results.export(include_errors=False), expected_json)

    def test_export_include_not_in_app_false(self):
        """export method works as expected."""
        obj_verified = self.model_factory.create()
        self.audit_results.add_verified(obj_verified)
        obj_error = self.model_factory.create()
        self.audit_results.add_error(obj_error, self.audit_results.TEST_ERROR_1)
        self.audit_results.add_not_in_app("foo")
        expected_json = {
            "verified": [{"instance": obj_verified, "id": obj_verified.pk}],
            "errors": [
                {
                    "id": obj_error.pk,
                    "instance": obj_error,
                    "errors": [self.audit_results.TEST_ERROR_1],
                }
            ],
        }
        self.assertEqual(
            self.audit_results.export(include_not_in_app=False), expected_json
        )
