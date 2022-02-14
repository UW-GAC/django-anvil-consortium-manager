from django.db.utils import IntegrityError
from django.test import TestCase

from ..models import Group, Investigator


class InvestigatorTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = Investigator(email="email@example.com")
        instance.save()
        self.assertIsInstance(instance, Investigator)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = Investigator(email="email@example.com")
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "email@example.com")

    def test_unique_email(self):
        """Saving a model with a duplicate email fails."""
        email = "email@example.com"
        instance = Investigator(email=email)
        instance.save()
        instance2 = Investigator(email=email)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_unique_email_case_insensitive(self):
        """Email uniqueness does not depend on case."""
        instance = Investigator(email="email@example.com")
        instance.save()
        instance2 = Investigator(email="EMAIL@example.com")
        with self.assertRaises(IntegrityError):
            instance2.save()


class GroupTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = Group(name="my_group")
        instance.save()
        self.assertIsInstance(instance, Group)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = Group(name="my_group")
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "my_group")

    def test_unique_name(self):
        """Saving a model with a duplicate name fails."""
        name = "my_group"
        instance = Group(name=name)
        instance.save()
        instance2 = Group(name=name)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_unique_name_case_insensitive(self):
        """Email uniqueness does not depend on case."""
        instance = Group(name="my_group")
        instance.save()
        instance2 = Group(name="My_GrOuP")
        with self.assertRaises(IntegrityError):
            instance2.save()
