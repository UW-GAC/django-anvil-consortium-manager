from django.db.utils import IntegrityError
from django.test import TestCase

from ..models import Investigator


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

    def test_unique(self):
        """Saving a model with a duplicate email fails."""
        email = "email@example.com"
        instance = Investigator(email=email)
        instance.save()
        instance2 = Investigator(email=email)
        with self.assertRaises(IntegrityError):
            instance2.save()
