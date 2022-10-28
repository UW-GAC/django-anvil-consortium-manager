from django.contrib.auth.models import User
from django.utils import timezone
from factory import Faker, SelfAttribute, Sequence, SubFactory, Trait
from factory.django import DjangoModelFactory

from .. import models
from ..adapters.default import DefaultWorkspaceAdapter


class BillingProjectFactory(DjangoModelFactory):
    """A factory for the BillingProject model."""

    name = Faker("slug")
    has_app_as_user = True

    class Meta:
        model = models.BillingProject
        django_get_or_create = ["name"]


class UserFactory(DjangoModelFactory):
    """A factory to create a user."""

    username = Sequence(lambda n: "testuser%d" % n)
    password = "password"

    class Meta:
        model = User
        django_get_or_create = ["username"]


class UserEmailEntryFactory(DjangoModelFactory):
    """A factory for the UserEmailEntry model."""

    email = Faker("email")
    user = SubFactory(UserFactory)
    date_verification_email_sent = Faker(
        "date_time", tzinfo=timezone.get_current_timezone()
    )

    class Meta:
        model = models.UserEmailEntry

    # class Params:
    #     verified = Trait(
    #         date_verified=Faker("date_time", tzinfo=timezone.get_current_timezone()),
    #         # Create an Account with the same user.
    #         verified_account=SubFactory(
    #             AccountFactory,
    #             user=SelfAttribute("..user"),
    #             email=SelfAttribute("..email"),
    #         ),
    #     )


class AccountFactory(DjangoModelFactory):
    """A factory for the Account model."""

    email = Faker("email")
    is_service_account = False

    class Meta:
        model = models.Account
        django_get_or_create = ["email"]

    class Params:
        verified = Trait(
            user=SubFactory(UserFactory),
            verified_email_entry=SubFactory(
                UserEmailEntryFactory,
                email=SelfAttribute("..email"),
                user=SelfAttribute("..user"),
                date_verified=Faker(
                    "date_time", tzinfo=timezone.get_current_timezone()
                ),
            ),
        )


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
    workspace_type = DefaultWorkspaceAdapter().get_type()

    class Meta:
        model = models.Workspace
        django_get_or_create = ["billing_project", "name"]


class WorkspaceAuthorizationDomainFactory(DjangoModelFactory):
    """A factory for the WorkspaceAuthorizationDomain model."""

    workspace = SubFactory(WorkspaceFactory)
    group = SubFactory(ManagedGroupFactory)

    class Meta:
        model = models.WorkspaceAuthorizationDomain


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
