import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from factory.django import DjangoModelFactory
from faker import Faker

from .. import models
from ..adapters.default import DefaultWorkspaceAdapter

User = get_user_model()

fake = Faker()


class BillingProjectFactory(DjangoModelFactory):
    """A factory for the BillingProject model."""

    name = factory.Faker("slug")
    has_app_as_user = True

    class Meta:
        model = models.BillingProject
        django_get_or_create = ["name"]


class UserFactory(DjangoModelFactory):
    """A factory to create a user."""

    username = factory.Sequence(lambda n: "testuser%d" % n)
    password = "password"

    class Meta:
        model = User
        django_get_or_create = ["username"]


class UserEmailEntryFactory(DjangoModelFactory):
    """A factory for the UserEmailEntry model."""

    email = factory.Faker("email")
    user = factory.SubFactory(UserFactory)
    date_verification_email_sent = factory.Faker("date_time", tzinfo=timezone.get_current_timezone())

    class Meta:
        model = models.UserEmailEntry


class AccountFactory(DjangoModelFactory):
    """A factory for the Account model."""

    email = factory.Faker("email")
    is_service_account = False

    class Meta:
        model = models.Account
        django_get_or_create = ["email"]

    class Params:
        verified = factory.Trait(
            user=factory.SubFactory(UserFactory),
            verified_email_entry=factory.SubFactory(
                UserEmailEntryFactory,
                email=factory.SelfAttribute("..email"),
                user=factory.SelfAttribute("..user"),
                date_verified=factory.Faker("date_time", tzinfo=timezone.get_current_timezone()),
            ),
        )


class ManagedGroupFactory(DjangoModelFactory):
    """A factory for the ManagedGroup model."""

    name = factory.Faker("slug")
    email = factory.LazyAttribute(lambda o: o.name + "@firecloud.org")

    class Meta:
        model = models.ManagedGroup
        django_get_or_create = ["name"]


class WorkspaceFactory(DjangoModelFactory):
    """A factory for the Workspace model."""

    billing_project = factory.SubFactory(BillingProjectFactory)
    name = factory.Faker("slug")
    workspace_type = DefaultWorkspaceAdapter().get_type()
    app_access = models.Workspace.AppAccessChoices.OWNER

    @factory.lazy_attribute
    def app_access_reason(self):
        if self.app_access == models.Workspace.AppAccessChoices.OWNER:
            return ""
        else:
            return fake.sentence()

    class Meta:
        model = models.Workspace
        django_get_or_create = ["billing_project", "name"]


class DefaultWorkspaceDataFactory(DjangoModelFactory):
    """A factory for the DefaultWorkspaceData model."""

    workspace = factory.SubFactory(WorkspaceFactory)

    class Meta:
        model = models.DefaultWorkspaceData
        django_get_or_create = [
            "workspace",
        ]


class WorkspaceAuthorizationDomainFactory(DjangoModelFactory):
    """A factory for the WorkspaceAuthorizationDomain model."""

    workspace = factory.SubFactory(WorkspaceFactory)
    group = factory.SubFactory(ManagedGroupFactory)

    class Meta:
        model = models.WorkspaceAuthorizationDomain


class GroupGroupMembershipFactory(DjangoModelFactory):
    """A factory for the GroupGroupMembership model."""

    parent_group = factory.SubFactory(ManagedGroupFactory)
    child_group = factory.SubFactory(ManagedGroupFactory)
    role = models.GroupAccountMembership.RoleChoices.MEMBER

    class Meta:
        model = models.GroupGroupMembership
        django_get_or_create = ["parent_group", "child_group"]


class GroupAccountMembershipFactory(DjangoModelFactory):
    """A factory for the Group model."""

    account = factory.SubFactory(AccountFactory)
    group = factory.SubFactory(ManagedGroupFactory)
    role = models.GroupAccountMembership.RoleChoices.MEMBER

    class Meta:
        model = models.GroupAccountMembership
        django_get_or_create = ["account", "group"]


class WorkspaceGroupSharingFactory(DjangoModelFactory):
    """A factory for the WorkspaceGroup model."""

    workspace = factory.SubFactory(WorkspaceFactory)
    group = factory.SubFactory(ManagedGroupFactory)
    access = models.WorkspaceGroupSharing.READER
    can_compute = False

    class Meta:
        model = models.WorkspaceGroupSharing
        django_get_or_create = ["workspace", "group"]
