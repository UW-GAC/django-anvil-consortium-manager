from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from anvil_project_manager import models


class BillingProjectFactory(DjangoModelFactory):
    """A factory for the BillingProject model."""

    name = Faker("slug")

    class Meta:
        model = models.BillingProject
        django_get_or_create = ["name"]


class ResearcherFactory(DjangoModelFactory):
    """A factory for the Researcher model."""

    email = Faker("email")

    class Meta:
        model = models.Researcher
        django_get_or_create = ["email"]


class GroupFactory(DjangoModelFactory):
    """A factory for the Group model."""

    name = Faker("slug")

    class Meta:
        model = models.Group
        django_get_or_create = ["name"]


class WorkspaceFactory(DjangoModelFactory):
    """A factory for the Workspace model."""

    billing_project = SubFactory(BillingProjectFactory)
    name = Faker("slug")

    class Meta:
        model = models.Workspace
        django_get_or_create = ["billing_project", "name"]


class GroupMembershipFactory(DjangoModelFactory):
    """A factory for the Group model."""

    researcher = SubFactory(ResearcherFactory)
    group = SubFactory(GroupFactory)
    role = models.GroupMembership.MEMBER

    class Meta:
        model = models.GroupMembership
        django_get_or_create = ["researcher", "group"]


class WorkspaceGroupAccessFactory(DjangoModelFactory):
    """A factory for the WorkspaceGroup model."""

    workspace = SubFactory(WorkspaceFactory)
    group = SubFactory(GroupFactory)
    access = models.WorkspaceGroupAccess.READER

    class Meta:
        model = models.WorkspaceGroupAccess
        django_get_or_create = ["workspace", "group"]
