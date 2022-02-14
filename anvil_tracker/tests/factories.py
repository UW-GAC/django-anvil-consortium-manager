from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from anvil_tracker import models


class InvestigatorFactory(DjangoModelFactory):
    """A factory for the Investigator model."""

    email = Faker("email")

    class Meta:
        model = models.Investigator
        django_get_or_create = ["email"]


class GroupFactory(DjangoModelFactory):
    """A factory for the Group model."""

    name = Faker("slug")

    class Meta:
        model = models.Group
        django_get_or_create = ["name"]


class WorkspaceFactory(DjangoModelFactory):
    """A factory for the Workspace model."""

    namespace = Faker("slug")
    name = Faker("slug")
    authorization_domain = SubFactory(GroupFactory)

    class Meta:
        model = models.Workspace
        django_get_or_create = ["namespace", "name"]


class GroupMembershipFactory(DjangoModelFactory):
    """A factory for the Group model."""

    investigator = SubFactory(InvestigatorFactory)
    group = SubFactory(GroupFactory)
    role = models.GroupMembership.MEMBER

    class Meta:
        model = models.GroupMembership
        django_get_or_create = ["investigator", "group"]


class WorkspaceGroupAccessFactory(DjangoModelFactory):
    """A factory for the WorkspaceGroup model."""

    workspace = SubFactory(WorkspaceFactory)
    group = SubFactory(GroupFactory)
    access_level = models.WorkspaceGroupAccess.READER

    class Meta:
        model = models.WorkspaceGroupAccess
        django_get_or_create = ["workspace", "group"]
