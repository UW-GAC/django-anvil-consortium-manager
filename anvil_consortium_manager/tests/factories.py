from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from anvil_consortium_manager import models


class BillingProjectFactory(DjangoModelFactory):
    """A factory for the BillingProject model."""

    name = Faker("slug")
    has_app_as_user = True

    class Meta:
        model = models.BillingProject
        django_get_or_create = ["name"]


class AccountFactory(DjangoModelFactory):
    """A factory for the Account model."""

    email = Faker("email")
    is_service_account = False

    class Meta:
        model = models.Account
        django_get_or_create = ["email"]


class ManagedGroupFactory(DjangoModelFactory):
    """A factory for the ManagedGroup model."""

    name = Faker("slug")

    class Meta:
        model = models.ManagedGroup
        django_get_or_create = ["name"]


class WorkspaceFactory(DjangoModelFactory):
    """A factory for the Workspace model."""

    billing_project = SubFactory(BillingProjectFactory)
    name = Faker("slug")

    class Meta:
        model = models.Workspace
        django_get_or_create = ["billing_project", "name"]


class GroupGroupMembershipFactory(DjangoModelFactory):
    """A factory for the GroupGroupMembership model."""

    parent_group = SubFactory(ManagedGroupFactory)
    child_group = SubFactory(ManagedGroupFactory)
    role = models.GroupAccountMembership.MEMBER

    class Meta:
        model = models.GroupGroupMembership
        django_get_or_create = ["parent_group", "child_group"]


class GroupAccountMembershipFactory(DjangoModelFactory):
    """A factory for the Group model."""

    account = SubFactory(AccountFactory)
    group = SubFactory(ManagedGroupFactory)
    role = models.GroupAccountMembership.MEMBER

    class Meta:
        model = models.GroupAccountMembership
        django_get_or_create = ["account", "group"]


class WorkspaceGroupAccessFactory(DjangoModelFactory):
    """A factory for the WorkspaceGroup model."""

    workspace = SubFactory(WorkspaceFactory)
    group = SubFactory(ManagedGroupFactory)
    access = models.WorkspaceGroupAccess.READER
    can_compute = False

    class Meta:
        model = models.WorkspaceGroupAccess
        django_get_or_create = ["workspace", "group"]
