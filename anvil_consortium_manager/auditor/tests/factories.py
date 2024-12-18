from django.contrib.auth import get_user_model
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from anvil_consortium_manager.tests.factories import ManagedGroupFactory, UserFactory

from .. import models

User = get_user_model()


class IgnoredManagedGroupMembershipFactory(DjangoModelFactory):
    """A factory for the Account model."""

    group = SubFactory(ManagedGroupFactory)
    ignored_email = Faker("email")
    added_by = SubFactory(UserFactory)
    note = Faker("sentence")

    class Meta:
        model = models.IgnoredManagedGroupMembership
