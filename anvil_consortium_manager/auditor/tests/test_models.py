from django.db.utils import IntegrityError

from anvil_consortium_manager.tests.utils import TestCase  # Redefined to work with Django < 4.2 and Django=4.2.

from .. import models
from . import factories


class IgnoredManagedGroupMembershipTest(TestCase):
    """Tests for the models.IgnoredManagedGroupMembership model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        group = factories.ManagedGroupFactory.create()
        user = factories.UserFactory.create()
        instance = models.IgnoredManagedGroupMembership(
            group=group,
            ignored_email="email@example.com",
            added_by=user,
            note="foo",
        )
        instance.save()
        self.assertIsInstance(instance, models.IgnoredManagedGroupMembership)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.IgnoredManagedGroupMembershipFactory.create(
            group__name="foo", ignored_email="email@example.com"
        )
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "foo membership: ignoring email@example.com")

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.IgnoredManagedGroupMembershipFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_history(self):
        """A simple history record is created when model is updated."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        # History was created.
        self.assertEqual(obj.history.count(), 1)
        # A new entry is created on update.
        obj.note = "foo bar"
        obj.save()
        self.assertEqual(obj.history.count(), 2)
        # An entry is created upon deletion.
        obj.delete()
        self.assertEqual(models.IgnoredManagedGroupMembership.history.count(), 3)

    def test_unique(self):
        # Cannot save the same record for the same group and email.
        group = factories.ManagedGroupFactory.create()
        email = "email@example.com"
        instance_1 = factories.IgnoredManagedGroupMembershipFactory.build(
            group=group,
            ignored_email=email,
            added_by=factories.UserFactory.create(),
        )
        instance_1.save()
        instance_2 = factories.IgnoredManagedGroupMembershipFactory.build(
            group=group,
            ignored_email=email,
            added_by=factories.UserFactory.create(),
        )
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_unique_case_insensitive(self):
        # Cannot save the same record for the same group and email.
        group = factories.ManagedGroupFactory.create()
        email = "email@example.com"
        instance_1 = factories.IgnoredManagedGroupMembershipFactory.build(
            group=group,
            ignored_email=email,
            added_by=factories.UserFactory.create(),
        )
        instance_1.save()
        instance_2 = factories.IgnoredManagedGroupMembershipFactory.build(
            group=group,
            ignored_email=email.upper(),
            added_by=factories.UserFactory.create(),
        )
        with self.assertRaises(IntegrityError):
            instance_2.save()
