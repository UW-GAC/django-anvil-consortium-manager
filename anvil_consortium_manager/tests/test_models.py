import datetime
import time
from unittest import skip

import networkx as nx
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models.deletion import ProtectedError
from django.db.utils import IntegrityError
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from ..adapters.default import DefaultWorkspaceAdapter
from ..models import (
    Account,
    AccountUserArchive,
    BillingProject,
    DefaultWorkspaceData,
    GroupAccountMembership,
    GroupGroupMembership,
    ManagedGroup,
    UserEmailEntry,
    Workspace,
    WorkspaceAuthorizationDomain,
    WorkspaceGroupSharing,
)
from ..tokens import account_verification_token
from . import factories
from .utils import TestCase  # Redefined to work with Django < 4.2 and Django=4.2.


class BillingProjectTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = BillingProject(name="my_project", has_app_as_user=True)
        instance.save()
        self.assertIsInstance(instance, BillingProject)

    def test_note_field(self):
        instance = BillingProject(name="my_project", has_app_as_user=True, note="foo")
        instance.save()
        self.assertIsInstance(instance, BillingProject)
        self.assertEqual(instance.note, "foo")

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = BillingProject(name="my_project", has_app_as_user=True)
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "my_project")

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.BillingProjectFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_history(self):
        """A history record is created when model is updated."""
        obj = factories.BillingProjectFactory.create(name="original-name")
        # History was created.
        self.assertEqual(obj.history.count(), 1)
        # A new entry was created after update.
        obj.name = "updated-name"
        obj.save()
        self.assertEqual(obj.history.count(), 2)
        # An entry is created upon deletion.
        obj.delete()
        self.assertEqual(BillingProject.history.count(), 3)

    def test_unique_name(self):
        """Saving a model with a duplicate name fails."""
        name = "my_project"
        instance = BillingProject(name=name, has_app_as_user=True)
        instance.save()
        instance2 = BillingProject(name=name, has_app_as_user=False)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_workspace_on_delete(self):
        """Billing project cannot be deleted if a workspace in that BillingProject exists."""
        workspace = factories.WorkspaceFactory.create()
        with self.assertRaises(ProtectedError):
            workspace.billing_project.delete()
        self.assertEqual(BillingProject.objects.count(), 1)

    @skip("Add this constraint.")
    def test_name_save_case_insensitivity(self):
        """Cannot save two models with the same case-insensitive name."""
        name = "AbAbA"
        factories.BillingProjectFactory.create(name=name)
        instance = BillingProject(name=name.lower())
        with self.assertRaises(IntegrityError):
            instance.save()


class UserEmailEntryTest(TestCase):
    """Tests for the UserEmailEntry model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        user = get_user_model().objects.create_user(username="testuser")
        instance = UserEmailEntry(
            email="email@example.com",
            user=user,
            date_verification_email_sent=timezone.now(),
        )
        instance.save()
        self.assertIsInstance(instance, UserEmailEntry)

    def test_save_unique_email_case_insensitive(self):
        """Email uniqueness does not depend on case."""
        user = get_user_model().objects.create_user(username="testuser")
        instance = UserEmailEntry(
            email="email@example.com",
            user=user,
            date_verification_email_sent=timezone.now(),
        )
        instance.save()
        instance2 = UserEmailEntry(
            email="EMAIL@example.com",
            user=user,
            date_verification_email_sent=timezone.now(),
        )
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_verified(self):
        user = get_user_model().objects.create_user(username="testuser")
        instance = UserEmailEntry(
            email="email@example.com",
            user=user,
            date_verification_email_sent=timezone.now() - datetime.timedelta(days=30),
            date_verified=timezone.now(),
        )
        instance.save()
        self.assertIsInstance(instance, UserEmailEntry)

    def test_verified_account_deleted(self):
        """A verified account linked to the entry is deleted."""
        account = factories.AccountFactory.create(verified=True)
        obj = account.verified_email_entry
        account.delete()
        # Make sure it still exists.
        obj.refresh_from_db()
        with self.assertRaises(ObjectDoesNotExist):
            obj.verified_account

    def test_user_deleted(self):
        """The user linked to the entry is deleted."""
        user = factories.UserFactory.create()
        obj = factories.UserEmailEntryFactory.create(user=user)
        user.delete()
        with self.assertRaises(UserEmailEntry.DoesNotExist):
            obj.refresh_from_db()

    def test_cannot_delete_if_verified_account(self):
        """Cannot delete a UserEmailEntry object if it is linked to an Account."""
        account = factories.AccountFactory.create(verified=True)
        obj = account.verified_email_entry
        with self.assertRaises(ProtectedError):
            obj.delete()

    # This test occasionally fails if the time flips one second between sending the email and
    # regenerating the token. Use freezegun's freeze_time decorator to fix the time and avoid
    # this spurious failure.
    @freeze_time("2022-11-22 03:12:34")
    def test_send_verification_email(self):
        """Verification email is correct."""
        email_entry = factories.UserEmailEntryFactory.create()
        email_entry.send_verification_email("www.test.com")
        # One message has been sent.
        self.assertEqual(len(mail.outbox), 1)
        # The subject is correct.
        self.assertEqual(mail.outbox[0].subject, "Verify your AnVIL account email")
        # The contents are correct.
        email_body = mail.outbox[0].body
        self.assertIn("http://www.test.com", email_body)
        self.assertIn(email_entry.user.username, email_body)
        self.assertIn(account_verification_token.make_token(email_entry), email_body)
        self.assertIn(str(email_entry.uuid), email_body)

    # This test occasionally fails if the time flips one second between sending the email and
    # regenerating the token. Use freezegun's freeze_time decorator to fix the time and avoid
    # this spurious failure.
    @freeze_time("2022-11-22 03:12:34")
    @override_settings(ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountAdapter")
    def test_send_verification_email_custom_subject(self):
        """Verification email is correct."""
        email_entry = factories.UserEmailEntryFactory.create()
        email_entry.send_verification_email("www.test.com")
        # One message has been sent.
        self.assertEqual(len(mail.outbox), 1)
        # The subject is correct.
        self.assertEqual(mail.outbox[0].subject, "custom subject")
        # The contents are correct.
        email_body = mail.outbox[0].body
        self.assertIn("http://www.test.com", email_body)
        self.assertIn(email_entry.user.username, email_body)
        self.assertIn(account_verification_token.make_token(email_entry), email_body)
        self.assertIn(str(email_entry.uuid), email_body)


class AccountTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = Account(email="email@example.com", is_service_account=False)
        instance.save()
        self.assertIsInstance(instance, Account)

    def test_note_field(self):
        instance = Account(email="email@example.com", is_service_account=False, note="foo")
        instance.save()
        self.assertIsInstance(instance, Account)
        self.assertEqual(instance.note, "foo")

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = Account(email="email@example.com", is_service_account=False)
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "email@example.com")

    def test_history(self):
        """A simple history record is created when model is updated."""
        obj = factories.AccountFactory.create(email="original@example.com")
        # History was created.
        self.assertEqual(obj.history.count(), 1)
        # A new entry is created on update.
        obj.name = "updated@example.com"
        obj.save()
        self.assertEqual(obj.history.count(), 2)
        # An entry is created upon deletion.
        obj.delete()
        self.assertEqual(Account.history.count(), 3)

    def test_save_email_case_insensitive(self):
        instance = Account(email="email@example.com", is_service_account=False)
        instance.save()
        instance2 = Account(email="EMAIL@example.com", is_service_account=False)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.AccountFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_unique_email_non_service_account(self):
        """Saving a model with a duplicate email fails."""
        email = "email@example.com"
        instance = Account(email=email, is_service_account=False)
        instance.save()
        instance2 = Account(email=email, is_service_account=False)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_save_unique_email_case_insensitive(self):
        """Email uniqueness does not depend on case."""
        instance = Account(email="email@example.com", is_service_account=False)
        instance.save()
        instance2 = Account(email="EMAIL@example.com", is_service_account=False)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_service_account(self):
        """Can create a service account."""
        instance = Account(email="service@account.com", is_service_account=True)
        instance.save()
        self.assertIsInstance(instance, Account)
        self.assertTrue(instance.is_service_account)

    def test_unique_email_service_account(self):
        """Saving a service account model with a duplicate email fails."""
        email = "email@example.com"
        instance = Account(email=email, is_service_account=True)
        instance.save()
        instance2 = Account(email=email, is_service_account=True)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_unique_email(self):
        """Saving a model with a duplicate email fails regardless of service account status."""
        email = "email@example.com"
        instance = Account(email=email, is_service_account=True)
        instance.save()
        instance2 = Account(email=email, is_service_account=False)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_user_has_unique_account(self):
        """User links to more than one ANVIL account email fails"""
        user = get_user_model().objects.create_user(username="testuser")
        email = "email1@example.com"
        email2 = "email2@example.com"
        instance = Account(email=email, user=user, is_service_account=False)
        instance.save()
        instance2 = Account(email=email2, user=user, is_service_account=False)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_linked_user_deleted(self):
        """Cannot delete a user if they have a linked account."""
        user = factories.UserFactory.create()
        factories.AccountFactory.create(user=user)
        with self.assertRaises(ProtectedError):
            user.delete()

    def test_clean_no_verified_email_entry_no_user(self):
        """The clean method succeeds if there is no verified_email_entry and no user."""
        account = factories.AccountFactory.build()
        account.full_clean()

    def test_clean_user_no_verified_email_entry(self):
        """The clean method fails if there is a user but no verified_email_entry."""
        user = factories.UserFactory.create()
        account = factories.AccountFactory.build(user=user)
        with self.assertRaises(ValidationError) as e:
            account.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("verified_email_entry", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["verified_email_entry"]), 1)
        self.assertIn(
            Account.ERROR_USER_WITHOUT_VERIFIED_EMAIL_ENTRY,
            e.exception.error_dict["verified_email_entry"][0].message,
        )

    def test_clean_no_user_verified_email_entry(self):
        """The clean method fails if there is no user but a verified_email_entry."""
        email_entry = factories.UserEmailEntryFactory.create(date_verified=timezone.now())
        account = factories.AccountFactory.build(email=email_entry.email, verified_email_entry=email_entry)
        with self.assertRaises(ValidationError) as e:
            account.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("user", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["user"]), 1)
        self.assertIn(
            Account.ERROR_VERIFIED_EMAIL_ENTRY_WITHOUT_USER,
            e.exception.error_dict["user"][0].message,
        )

    def test_clean_unverified_verified_email_entry(self):
        """The clean method fails if the verified_email_entry is actually unverified."""
        email_entry = factories.UserEmailEntryFactory.create(date_verified=None)
        account = factories.AccountFactory.build(
            user=email_entry.user,
            email=email_entry.email,
            verified_email_entry=email_entry,
        )
        with self.assertRaises(ValidationError) as e:
            account.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("verified_email_entry", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["verified_email_entry"]), 1)
        self.assertIn(
            Account.ERROR_UNVERIFIED_VERIFIED_EMAIL_ENTRY,
            e.exception.error_dict["verified_email_entry"][0].message,
        )

    def test_clean_account_verified_email_entry_email_mismatch(self):
        """The clean method fails if the verified_email_entry and the account have different emails."""
        email_entry = factories.UserEmailEntryFactory.create(date_verified=timezone.now(), email="foo@bar.com")
        account = factories.AccountFactory.build(
            user=email_entry.user, email="bar@foo.com", verified_email_entry=email_entry
        )
        with self.assertRaises(ValidationError) as e:
            account.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("email", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["email"]), 1)
        self.assertIn(Account.ERROR_MISMATCHED_EMAIL, e.exception.error_dict["email"][0].message)

    def test_clean_account_verified_email_entry_user_mismatch(self):
        """The clean method fails if the verified_email_entry and the account have different users."""
        user_1 = factories.UserFactory.create()
        user_2 = factories.UserFactory.create()
        email_entry = factories.UserEmailEntryFactory.create(user=user_1, date_verified=timezone.now())
        account = factories.AccountFactory.build(user=user_2, email=email_entry.email, verified_email_entry=email_entry)
        with self.assertRaises(ValidationError) as e:
            account.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("user", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["user"]), 1)
        self.assertIn(Account.ERROR_MISMATCHED_USER, e.exception.error_dict["user"][0].message)

    def test_get_accessible_workspaces_shared(self):
        """One workspace when the account is a member of a group and the workspace is shared with that group."""
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        # Set up group membership.
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_accessible_workspaces_not_shared(self):
        """One workspace when the account is a member of a group and the workspace is not shared with that group."""
        account = factories.AccountFactory.create()
        # Set up workspace.
        factories.WorkspaceFactory.create()
        # Set up group membership.
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        # Set up workspace sharing.
        # Tests.
        self.assertEqual(len(account.get_accessible_workspaces()), 0)

    def test_get_accessible_workspaces_not_in_group_shared(self):
        """No workspaces when the account is not a member of the group and a workspace is shared with that group."""
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        # Set up group membership.
        group = factories.ManagedGroupFactory.create()
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Tests.
        self.assertEqual(len(account.get_accessible_workspaces()), 0)

    def test_get_accessible_workspaces_not_in_group_not_shared(self):
        """No workspaces when the account is not in the group and a workspace is not shared with that group."""
        account = factories.AccountFactory.create()
        # Set up workspace.
        factories.WorkspaceFactory.create()
        # Set up group membership.
        factories.ManagedGroupFactory.create()
        # Set up workspace sharing.
        # Tests.
        self.assertEqual(len(account.get_accessible_workspaces()), 0)

    def test_get_accessible_workspaces_shared_with_parent(self):
        """One workspace when the account is in a group and the workspace is shared with a parent of that group."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        # Set up group membership.
        child_group = factories.ManagedGroupFactory.create()
        parent_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(child_group=child_group, parent_group=parent_group)
        factories.GroupAccountMembershipFactory.create(group=child_group, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=parent_group)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_accessible_workspaces_shared_with_grandparent(self):
        """One workspace when the account is in a group and the workspace is shared with a grandparent of that group."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        # Set up group membership.
        child_group = factories.ManagedGroupFactory.create()
        parent_group = factories.ManagedGroupFactory.create()
        grandparent_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(child_group=parent_group, parent_group=grandparent_group)
        factories.GroupGroupMembershipFactory.create(child_group=child_group, parent_group=parent_group)
        factories.GroupAccountMembershipFactory.create(group=child_group, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=grandparent_group)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_accessible_workspaces_in_auth_domain_shared(self):
        """One workspace when the workspace has an auth domain, the account is part of the auth domain, and the workspace is shared with the auth domain."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        auth_domain = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(auth_domain)
        # Set up group membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=auth_domain)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_accessible_workspaces_in_auth_domain_shared_with_different_group(self):
        """One workspace when the workspace has an auth domain, the account is part of the auth domain, and the workspace is shared with a different group that the account is in."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        auth_domain = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(auth_domain)
        # Set up group membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain, account=account)
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_accessible_workspaces_in_auth_domain_not_shared(self):
        """No workspaces when account is part of the auth domain but the workspace is not shared."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        auth_domain = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(auth_domain)
        # Set up group membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain, account=account)
        # Set up workspace sharing.
        # Tests.
        self.assertEqual(len(account.get_accessible_workspaces()), 0)

    def test_get_accessible_workspaces_not_in_auth_domain_shared(self):
        """No workspaces when account is not part of the auth domain and the workspace is shared with the auth domain."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        auth_domain = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(auth_domain)
        # Set up group membership.
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=auth_domain)
        # Tests.
        self.assertEqual(len(account.get_accessible_workspaces()), 0)

    def test_get_accessible_workspaces_in_auth_domain_as_parent_shared(self):
        """One workspace when account is part of the auth domain via a child group and the workspace is shared with the auth domain."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        auth_domain = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(auth_domain)
        # Set up group membership.
        group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(child_group=group, parent_group=auth_domain)
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=auth_domain)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_accessible_workspaces_in_auth_domain_as_grandparent_shared(self):
        """One workspace when account is part of the auth domain via a grandchild group and the workspace is shared with the auth domain."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        auth_domain = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(auth_domain)
        # Set up group membership.
        child_group = factories.ManagedGroupFactory.create()
        parent_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(child_group=child_group, parent_group=parent_group)
        factories.GroupGroupMembershipFactory.create(child_group=parent_group, parent_group=auth_domain)
        factories.GroupAccountMembershipFactory.create(group=child_group, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=auth_domain)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_accessible_workspaces_in_auth_domain_shared_with_different_parent(
        self,
    ):
        """One workspace when account is part of the auth domain, the account is in a different group, and the workspace is shared a parent of that group."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        auth_domain = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(auth_domain)
        # Set up group membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain, account=account)
        child_group = factories.ManagedGroupFactory.create()
        parent_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(child_group=child_group, parent_group=parent_group)
        factories.GroupAccountMembershipFactory.create(group=child_group, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=parent_group)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_accessible_worspaces_in_auth_domain_shared_with_different_grandparent(
        self,
    ):
        """One workspace when account is part of the auth domain, the account is in a different group, and the workspace is shared a grandparent of that group."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        auth_domain = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(auth_domain)
        # Set up group membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain, account=account)
        child_group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=child_group, account=account)
        parent_group = factories.ManagedGroupFactory.create()
        grandparent_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(child_group=child_group, parent_group=parent_group)
        factories.GroupGroupMembershipFactory.create(child_group=parent_group, parent_group=grandparent_group)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=grandparent_group)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_accessible_workspaces_two_auth_domains_in_both_shared_with_one(self):
        """One workspace when a workspace has two auth domains, the account is part of both auth domains, and the group is shared with one of them."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.ManagedGroupFactory.create()
        auth_domain_2 = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(auth_domain_1, auth_domain_2)
        # Set up group membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain_1, account=account)
        factories.GroupAccountMembershipFactory.create(group=auth_domain_2, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=auth_domain_1)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_accessible_workspaces_two_auth_domains_in_one_shared(self):
        """No workspaces are returned when a workspace has two auth domains, the account is in only one of the auth domains, and the group is shared with that auth domain."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.ManagedGroupFactory.create()
        auth_domain_2 = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(auth_domain_1, auth_domain_2)
        # Set up group membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain_1, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=auth_domain_1)
        # Tests.
        self.assertEqual(len(account.get_accessible_workspaces()), 0)

    def test_get_accessible_workspaces_two_auth_domains_in_both_shared_different_group(
        self,
    ):
        """One workspace when a workspace has two auth domains, the account is part of both auth domains, the account is in a different group, and the group is shared with that group."""  # noqa: E501
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.ManagedGroupFactory.create()
        auth_domain_2 = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(auth_domain_1, auth_domain_2)
        # Set up group membership.
        factories.GroupAccountMembershipFactory.create(account=account, group=auth_domain_1)
        factories.GroupAccountMembershipFactory.create(account=account, group=auth_domain_2)
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_accessible_workspaces_workspace_only_appears_once(self):
        """A workspace only appears once in the returned list."""
        account = factories.AccountFactory.create()
        # Set up workspace.
        workspace = factories.WorkspaceFactory.create()
        # Set up group membership.
        group_1 = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group_1, account=account)
        group_2 = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group_2, account=account)
        # Set up workspace sharing.
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group_1)
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group_2)
        # Tests.
        accessible_workspaces = account.get_accessible_workspaces()
        self.assertEqual(len(accessible_workspaces), 1)
        self.assertIn(workspace, accessible_workspaces)

    def test_get_all_groups_no_parents(self):
        """One group returns in the set"""
        account = factories.AccountFactory.create()
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        groups = account.get_all_groups()
        self.assertEqual(len(groups), 1)
        self.assertIn(group, groups)

    def test_get_all_groups_one_parent(self):
        """Two groups returned in the set"""
        account = factories.AccountFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=child, account=account)
        parent = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        groups = account.get_all_groups()
        self.assertEqual(len(groups), 2)
        self.assertIn(parent, groups)
        self.assertIn(child, groups)

    def test_get_all_groups_one_parent_account_in_both(self):
        """Two groups returned in the set when the account is in both child and parent groups"""
        account = factories.AccountFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=child, account=account)
        parent = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        factories.GroupAccountMembershipFactory.create(group=parent, account=account)
        groups = account.get_all_groups()
        self.assertEqual(len(groups), 2)
        self.assertIn(parent, groups)
        self.assertIn(child, groups)

    def test_get_all_groups_one_grandparent(self):
        """Three groups returned in the set"""
        account = factories.AccountFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=child, account=account)
        parent = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        grandparent = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        groups = account.get_all_groups()
        self.assertEqual(len(groups), 3)
        self.assertIn(parent, groups)
        self.assertIn(child, groups)
        self.assertIn(grandparent, groups)

    def test_get_all_groups_one_parent_two_grandparents(self):
        """Four groups returned in the set"""
        account = factories.AccountFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=child, account=account)
        parent = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        grandparent_1 = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent_1, child_group=parent)
        grandparent_2 = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent_2, child_group=parent)
        groups = account.get_all_groups()
        self.assertEqual(len(groups), 4)
        self.assertIn(parent, groups)
        self.assertIn(child, groups)
        self.assertIn(grandparent_1, groups)
        self.assertIn(grandparent_2, groups)

    def test_get_all_groups_grandparent_is_also_parent(self):
        """Three groups returned when a child group has one parent and a grandparent.  The grandparent group is also a parent to the child's group"""  # noqa: E501
        account = factories.AccountFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=child, account=account)
        parent = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        grandparent = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=child)
        groups = account.get_all_groups()
        self.assertEqual(len(groups), 3)
        self.assertIn(parent, groups)
        self.assertIn(child, groups)
        self.assertIn(grandparent, groups)

    def test_get_all_groups_one_child(self):
        """Child groups are not returned."""
        account = factories.AccountFactory.create()
        child = factories.ManagedGroupFactory.create()
        parent = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        factories.GroupAccountMembershipFactory.create(group=parent, account=account)
        groups = account.get_all_groups()
        self.assertEqual(len(groups), 1)
        self.assertIn(parent, groups)

    def test_has_workspace_access_not_shared_no_auth_domains(self):
        # Workspace setup.
        workspace = factories.WorkspaceFactory.create()
        # Workspace sharing.
        # Account setup.
        account = factories.AccountFactory.create()
        # Auth domain membership.
        # Sharing membership.
        self.assertFalse(account.has_workspace_access(workspace))

    def test_has_workspace_access_is_shared_no_auth_domains(self):
        # Workspace setup.
        workspace = factories.WorkspaceFactory.create()
        # Workspace sharing.
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Account setup.
        account = factories.AccountFactory.create()
        # Auth domain membership.
        # Sharing membership.
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        self.assertTrue(account.has_workspace_access(workspace))

    def test_has_workspace_access_is_shared_with_parent_no_auth_domains(self):
        # Workspace setup.
        workspace = factories.WorkspaceFactory.create()
        # Workspace sharing.
        parent_group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent_group, child_group=child_group)
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=parent_group)
        # Account setup.
        account = factories.AccountFactory.create()
        # Auth domain membership.
        # Sharing membership.
        factories.GroupAccountMembershipFactory.create(group=child_group, account=account)
        self.assertTrue(account.has_workspace_access(workspace))

    def test_has_workspace_access_is_shared_one_auth_domain_not_in_auth_domain(self):
        # Workspace setup.
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        # Workspace sharing.
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Account setup.
        account = factories.AccountFactory.create()
        # Auth domain membership.
        # Sharing membership.
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        self.assertFalse(account.has_workspace_access(workspace))

    def test_has_workspace_access_is_shared_one_auth_domain_in_auth_domain(self):
        # Workspace setup.
        workspace = factories.WorkspaceFactory.create()
        auth_domain = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        # Workspace sharing.
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Account setup.
        account = factories.AccountFactory.create()
        # Auth domain membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain.group, account=account)
        # Sharing membership.
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        self.assertTrue(account.has_workspace_access(workspace))

    def test_has_workspace_access_is_shared_one_auth_domain_in_auth_domain_child(self):
        # Workspace setup.
        workspace = factories.WorkspaceFactory.create()
        auth_domain = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        # Workspace sharing.
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Account setup.
        account = factories.AccountFactory.create()
        # Auth domain membership.
        child_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=auth_domain.group, child_group=child_group)
        factories.GroupAccountMembershipFactory.create(group=child_group, account=account)
        # Sharing membership.
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        self.assertTrue(account.has_workspace_access(workspace))

    def test_has_workspace_access_is_not_shared_one_auth_domain_in_auth_domain(self):
        # Workspace setup.
        workspace = factories.WorkspaceFactory.create()
        auth_domain = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        # Workspace sharing.
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Account setup.
        account = factories.AccountFactory.create()
        # Auth domain membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain.group, account=account)
        # Sharing membership.
        self.assertFalse(account.has_workspace_access(workspace))

    def test_has_workspace_access_is_shared_two_auth_domain_not_in_either(self):
        # Workspace setup.
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        # Workspace sharing.
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Account setup.
        account = factories.AccountFactory.create()
        # Auth domain membership.
        # Sharing membership.
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        self.assertFalse(account.has_workspace_access(workspace))

    def test_has_workspace_access_is_shared_two_auth_domain_in_one(self):
        # Workspace setup.
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        # Workspace sharing.
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Account setup.
        account = factories.AccountFactory.create()
        # Auth domain membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain_1.group, account=account)
        # Sharing membership.
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        self.assertFalse(account.has_workspace_access(workspace))

    def test_has_workspace_access_is_shared_two_auth_domain_in_both(self):
        # Workspace setup.
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        auth_domain_2 = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        # Workspace sharing.
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Account setup.
        account = factories.AccountFactory.create()
        # Auth domain membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain_1.group, account=account)
        factories.GroupAccountMembershipFactory.create(group=auth_domain_2.group, account=account)
        # Sharing membership.
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        self.assertTrue(account.has_workspace_access(workspace))

    def test_has_workspace_access_is_not_shared_two_auth_domain_in_both(self):
        # Workspace setup.
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        auth_domain_2 = factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        # Workspace sharing.
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Account setup.
        account = factories.AccountFactory.create()
        # Auth domain membership.
        factories.GroupAccountMembershipFactory.create(group=auth_domain_1.group, account=account)
        factories.GroupAccountMembershipFactory.create(group=auth_domain_2.group, account=account)
        # Sharing membership.
        self.assertFalse(account.has_workspace_access(workspace))

    def test_unlink_user(self):
        """The unlink_user method removes the user and verified_email_entry."""
        account = factories.AccountFactory.create(verified=True)
        account.unlink_user()
        self.assertIsNone(account.user)
        self.assertIsNone(account.verified_email_entry)

    def test_unlink_user_adds_to_archive(self):
        """The unlink_user method adds the user to the AccountUserArchive."""
        account = factories.AccountFactory.create(verified=True)
        user = account.user
        verified_email_entry = account.verified_email_entry
        account.unlink_user()
        self.assertEqual(AccountUserArchive.objects.count(), 1)
        archive = AccountUserArchive.objects.first()
        self.assertEqual(archive.user, user)
        self.assertEqual(archive.account, account)
        self.assertEqual(archive.verified_email_entry, verified_email_entry)

    def test_unlink_user_no_verified_email(self):
        """The unlink_user method removes the user and verified_email_entry."""
        user = factories.UserFactory.create()
        account = factories.AccountFactory.create(user=user)
        account.unlink_user()
        self.assertIsNone(account.user)
        self.assertIsNone(account.verified_email_entry)
        self.assertEqual(AccountUserArchive.objects.count(), 1)
        archive = AccountUserArchive.objects.first()
        self.assertEqual(archive.user, user)
        self.assertEqual(archive.account, account)
        self.assertIsNone(archive.verified_email_entry)

    def test_can_archive_more_than_one_account_for_one_user(self):
        """The unlink_user method adds the user to the AccountUserArchive."""
        user = factories.UserFactory.create()
        account_1 = factories.AccountFactory.create(user=user)
        account_1.unlink_user()
        account_2 = factories.AccountFactory.create(user=user)
        account_2.unlink_user()
        self.assertEqual(AccountUserArchive.objects.count(), 2)
        AccountUserArchive.objects.get(account=account_1, user=user)
        AccountUserArchive.objects.get(account=account_2, user=user)

    def test_raises_value_error_no_user(self):
        """Raises a ValueError if the account has no user."""
        account = factories.AccountFactory.create()
        with self.assertRaises(ValueError):
            account.unlink_user()


class AccountUserArchiveTestCase(TestCase):
    """Tests for the AccountUserArchive model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        user = factories.UserFactory.create()
        account = factories.AccountFactory.create()
        instance = AccountUserArchive(user=user, account=account)
        instance.save()
        self.assertIsInstance(instance, AccountUserArchive)

    def test_created_timestamp(self):
        """created timestamp is set."""
        user = factories.UserFactory.create()
        account = factories.AccountFactory.create()
        instance = AccountUserArchive(user=user, account=account)
        instance.save()
        self.assertIsNotNone(instance.created)

    def test_verified_email_entry(self):
        """Creation using the model constructor and .save() works."""
        account = factories.AccountFactory.create(verified=True)
        instance = AccountUserArchive(
            user=account.user, account=account, verified_email_entry=account.verified_email_entry
        )
        instance.save()
        self.assertIsInstance(instance, AccountUserArchive)

    def test_one_account_two_users(self):
        """Multiple AccountUserArchive records for one user."""
        user = factories.UserFactory.create()
        account_1 = factories.AccountFactory.create()
        account_2 = factories.AccountFactory.create()
        instance = AccountUserArchive(user=user, account=account_1)
        instance.save()
        instance_2 = AccountUserArchive(user=user, account=account_2)
        instance_2.save()
        self.assertEqual(AccountUserArchive.objects.count(), 2)

    def test_str_method(self):
        """The custom __str__ method returns a string."""
        user = factories.UserFactory.create()
        account = factories.AccountFactory.create()
        instance = AccountUserArchive(user=user, account=account)
        instance.save()
        self.assertIsInstance(instance.__str__(), str)


class ManagedGroupTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = ManagedGroup(name="my_group", email="foo@bar.com")
        instance.save()
        self.assertIsInstance(instance, ManagedGroup)

    def test_note_field(self):
        """Creation using the model constructor and .save() works with a note field."""
        instance = ManagedGroup(name="my_group", note="test note", email="foo@bar.com")
        instance.save()
        self.assertIsInstance(instance, ManagedGroup)
        self.assertEqual(instance.note, "test note")

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = ManagedGroup(name="my_group", email="foo@bar.com")
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "my_group")

    @skip("Add this constraint.")
    def test_name_save_case_insensitivity(self):
        """Cannot save two models with the same case-insensitive name."""
        name = "AbAbA"
        factories.ManagedGroupFactory.create(name=name)
        instance = ManagedGroup(name=name.lower())
        with self.assertRaises(IntegrityError):
            instance.save()

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.ManagedGroupFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_history(self):
        """A simple history record is created when model is updated."""
        obj = factories.ManagedGroupFactory.create(name="original-name")
        # History was created.
        self.assertEqual(obj.history.count(), 1)
        # A new entry is created on update.
        obj.name = "updated-name"
        obj.save()
        self.assertEqual(obj.history.count(), 2)
        # An entry is created upon deletion.
        obj.delete()
        self.assertEqual(ManagedGroup.history.count(), 3)

    def test_unique_name(self):
        """Saving a model with a duplicate name fails."""
        instance = factories.ManagedGroupFactory.create()
        instance.save()
        instance2 = factories.ManagedGroupFactory.build(name=instance.name)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_name_max_length(self):
        """ValidationError is raised when the group name is too long."""
        instance = factories.ManagedGroupFactory.build(name="a" * 60)
        instance.full_clean()
        instance = factories.ManagedGroupFactory.build(name="a" * 61)
        with self.assertRaises(ValidationError):
            instance.full_clean()

    def test_unique_email(self):
        """Saving a model with a duplicate name fails."""
        instance = factories.ManagedGroupFactory.create()
        instance.save()
        instance2 = factories.ManagedGroupFactory.build(email=instance.email)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_is_managed_by_app(self):
        """Can set the is_managed_by_app field."""
        instance = ManagedGroup(name="my-group", is_managed_by_app=True, email="foo1@bar.com")
        instance.full_clean()
        instance.save()
        instance_2 = ManagedGroup(name="my-group-2", is_managed_by_app=False, email="foo2@bar.com")
        instance_2.full_clean()
        instance_2.save()

    def test_workspace_on_delete(self):
        """Group cannot be deleted if it is used as an auth domain for a workspace."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        workspace.authorization_domains.add(group)
        with self.assertRaises(ProtectedError):
            group.delete()
        self.assertEqual(ManagedGroup.objects.count(), 1)

    def test_cannot_delete_group_that_is_a_member_of_another_group(self):
        """Group cannot be deleted if it is a member of another group.

        This is a behavior enforced by AnVIL."""
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        with self.assertRaises(ProtectedError):
            child.delete()
        # Both groups still exist.
        self.assertEqual(ManagedGroup.objects.count(), 2)
        # The membership still exists.
        self.assertEqual(GroupGroupMembership.objects.count(), 1)

    def test_can_delete_group_if_it_has_child_groups(self):
        """A group can be deleted if it has other groups as members."""
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        parent.delete()
        # Only the child group still exists.
        self.assertEqual(ManagedGroup.objects.count(), 1)
        with self.assertRaises(ManagedGroup.DoesNotExist):
            ManagedGroup.objects.get(pk=parent.pk)
        ManagedGroup.objects.get(pk=child.pk)
        # The membership was deleted.
        self.assertEqual(GroupGroupMembership.objects.count(), 0)

    def test_can_delete_group_if_it_has_account_members(self):
        """A group can be deleted if it has an account as a member."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        group.delete()
        # No groups exist.
        self.assertEqual(ManagedGroup.objects.count(), 0)
        # The relationship was deleted.
        self.assertEqual(GroupAccountMembership.objects.count(), 0)
        # The account still exists.
        self.assertEqual(Account.objects.count(), 1)
        Account.objects.get(pk=account.pk)

    def test_cannot_delete_group_if_it_has_access_to_a_workspace(self):
        """Group cannot be deleted if it has access to a workspace.

        This is a behavior enforced by AnVIL."""
        access = factories.WorkspaceGroupSharingFactory.create()
        with self.assertRaises(ProtectedError):
            access.group.delete()
        # The group still exists.
        self.assertEqual(ManagedGroup.objects.count(), 1)
        ManagedGroup.objects.get(pk=access.group.pk)
        # The access still exists.
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        WorkspaceGroupSharing.objects.get(pk=access.pk)

    def test_get_direct_parents_no_parents(self):
        group = factories.ManagedGroupFactory(name="group")
        self.assertEqual(group.get_direct_parents().count(), 0)
        self.assertQuerySetEqual(group.get_direct_parents(), ManagedGroup.objects.none())

    def test_get_direct_parents_one_parent(self):
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(child.get_direct_parents().count(), 1)
        self.assertQuerySetEqual(child.get_direct_parents(), ManagedGroup.objects.filter(pk=parent.pk))

    def test_get_direct_parents_one_child_two_parents(self):
        parent_1 = factories.ManagedGroupFactory(name="parent-group-1")
        parent_2 = factories.ManagedGroupFactory(name="parent-group-2")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=parent_1, child_group=child)
        factories.GroupGroupMembershipFactory.create(parent_group=parent_2, child_group=child)
        self.assertEqual(child.get_direct_parents().count(), 2)
        self.assertQuerySetEqual(
            child.get_direct_parents(),
            ManagedGroup.objects.filter(pk__in=[parent_1.pk, parent_2.pk]),
            ordered=False,
        )

    def test_get_direct_parents_two_children_one_parent(self):
        parent = factories.ManagedGroupFactory(name="parent-group-1")
        child_1 = factories.ManagedGroupFactory(name="child-group-1")
        child_2 = factories.ManagedGroupFactory(name="child-group-2")
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child_1)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child_2)
        self.assertEqual(child_1.get_direct_parents().count(), 1)
        self.assertQuerySetEqual(child_1.get_direct_parents(), ManagedGroup.objects.filter(pk=parent.pk))
        self.assertEqual(child_2.get_direct_parents().count(), 1)
        self.assertQuerySetEqual(child_2.get_direct_parents(), ManagedGroup.objects.filter(pk=parent.pk))

    def test_get_direct_parents_with_other_group(self):
        # Create a relationship not involving the group in question.
        factories.GroupGroupMembershipFactory.create()
        # Create a group not related to any other group.
        group = factories.ManagedGroupFactory.create()
        self.assertEqual(group.get_direct_parents().count(), 0)

    def test_get_direct_parents_with_only_child(self):
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(parent.get_direct_parents().count(), 0)

    def test_get_direct_parents_with_grandparent(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(child.get_direct_parents().count(), 1)
        self.assertQuerySetEqual(child.get_direct_parents(), ManagedGroup.objects.filter(pk=parent.pk))

    def test_get_direct_children_no_children(self):
        group = factories.ManagedGroupFactory(name="group")
        self.assertEqual(group.get_direct_children().count(), 0)
        self.assertQuerySetEqual(group.get_direct_children(), ManagedGroup.objects.none())

    def test_get_direct_children_one_child(self):
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(parent.get_direct_children().count(), 1)
        self.assertQuerySetEqual(parent.get_direct_children(), ManagedGroup.objects.filter(pk=child.pk))

    def test_get_direct_children_one_parent_two_children(self):
        child_1 = factories.ManagedGroupFactory(name="child-group-1")
        child_2 = factories.ManagedGroupFactory(name="child-group-2")
        parent = factories.ManagedGroupFactory(name="parent-group")
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child_1)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child_2)
        self.assertEqual(parent.get_direct_children().count(), 2)
        self.assertQuerySetEqual(
            parent.get_direct_children(),
            ManagedGroup.objects.filter(pk__in=[child_1.pk, child_2.pk]),
            ordered=False,
        )

    def test_get_direct_parents_two_parents_one_child(self):
        child = factories.ManagedGroupFactory(name="child-group-1")
        parent_1 = factories.ManagedGroupFactory(name="parent-group-1")
        parent_2 = factories.ManagedGroupFactory(name="parent-group-2")
        factories.GroupGroupMembershipFactory.create(parent_group=parent_1, child_group=child)
        factories.GroupGroupMembershipFactory.create(parent_group=parent_2, child_group=child)
        self.assertEqual(parent_1.get_direct_children().count(), 1)
        self.assertQuerySetEqual(parent_1.get_direct_children(), ManagedGroup.objects.filter(pk=child.pk))
        self.assertEqual(parent_2.get_direct_children().count(), 1)
        self.assertQuerySetEqual(parent_2.get_direct_children(), ManagedGroup.objects.filter(pk=child.pk))

    def test_get_direct_children_with_other_group(self):
        # Create a relationship not involving the group in question.
        factories.GroupGroupMembershipFactory.create()
        # Create a group not related to any other group.
        group = factories.ManagedGroupFactory.create()
        self.assertEqual(group.get_direct_children().count(), 0)

    def test_get_direct_children_with_only_parent(self):
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(child.get_direct_children().count(), 0)

    def test_get_direct_children_with_grandchildren(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(grandparent.get_direct_children().count(), 1)
        self.assertQuerySetEqual(grandparent.get_direct_children(), ManagedGroup.objects.filter(pk=parent.pk))

    def test_get_all_parents_no_parents(self):
        group = factories.ManagedGroupFactory(name="group")
        self.assertEqual(group.get_all_parents().count(), 0)
        self.assertQuerySetEqual(group.get_all_parents(), ManagedGroup.objects.none())

    def test_get_all_parents_one_parent(self):
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(child.get_all_parents().count(), 1)
        self.assertQuerySetEqual(child.get_all_parents(), ManagedGroup.objects.filter(pk=parent.pk))

    def test_get_all_parents_one_grandparent(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(child.get_all_parents().count(), 2)
        self.assertQuerySetEqual(
            child.get_all_parents(),
            ManagedGroup.objects.filter(pk__in=[grandparent.pk, parent.pk]),
            ordered=False,
        )

    def test_get_all_parents_two_grandparents_same_parent(self):
        grandparent_1 = factories.ManagedGroupFactory(name="grandparent-group-1")
        grandparent_2 = factories.ManagedGroupFactory(name="grandparent-group-2")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent_1, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent_2, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(child.get_all_parents().count(), 3)
        self.assertQuerySetEqual(
            child.get_all_parents(),
            ManagedGroup.objects.filter(pk__in=[grandparent_1.pk, grandparent_2.pk, parent.pk]),
            ordered=False,
        )

    def test_get_all_parents_two_grandparents_two_parents(self):
        grandparent_1 = factories.ManagedGroupFactory(name="grandparent-group-1")
        grandparent_2 = factories.ManagedGroupFactory(name="grandparent-group-2")
        parent_1 = factories.ManagedGroupFactory(name="parent-group-1")
        parent_2 = factories.ManagedGroupFactory(name="parent-group-2")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent_1, child_group=parent_1)
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent_2, child_group=parent_2)
        factories.GroupGroupMembershipFactory.create(parent_group=parent_1, child_group=child)
        factories.GroupGroupMembershipFactory.create(parent_group=parent_2, child_group=child)
        self.assertEqual(child.get_all_parents().count(), 4)
        self.assertQuerySetEqual(
            child.get_all_parents(),
            ManagedGroup.objects.filter(pk__in=[grandparent_1.pk, grandparent_2.pk, parent_1.pk, parent_2.pk]),
            ordered=False,
        )

    def test_get_all_parents_multiple_paths_to_same_group(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        # Then create a grandparent-child direct relationship.
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=child)
        self.assertEqual(child.get_all_parents().count(), 2)
        self.assertQuerySetEqual(
            child.get_all_parents(),
            ManagedGroup.objects.filter(pk__in=[grandparent.pk, parent.pk]),
            ordered=False,
        )

    def test_all_parents_greatgrandparent(self):
        greatgrandparent = factories.ManagedGroupFactory(name="greatgrandparent-group")
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(parent_group=greatgrandparent, child_group=grandparent)
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(child.get_all_parents().count(), 3)
        self.assertQuerySetEqual(
            child.get_all_parents(),
            ManagedGroup.objects.filter(pk__in=[greatgrandparent.pk, grandparent.pk, parent.pk]),
            ordered=False,
        )

    def test_get_all_parents_with_other_group(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        # Create a group with no relationships
        group = factories.ManagedGroupFactory.create(name="other-group")
        self.assertEqual(group.get_all_parents().count(), 0)

    def test_get_all_children_no_children(self):
        group = factories.ManagedGroupFactory(name="group")
        self.assertEqual(group.get_all_children().count(), 0)
        self.assertQuerySetEqual(group.get_all_children(), ManagedGroup.objects.none())

    def test_get_all_children_one_child(self):
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(parent.get_all_children().count(), 1)
        self.assertQuerySetEqual(parent.get_all_children(), ManagedGroup.objects.filter(pk=child.pk))

    def test_get_all_children_one_grandchild(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(grandparent.get_all_children().count(), 2)
        self.assertQuerySetEqual(
            grandparent.get_all_children(),
            ManagedGroup.objects.filter(pk__in=[parent.pk, child.pk]),
            ordered=False,
        )

    def test_get_all_children_two_grandchildren_same_parent(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child_1 = factories.ManagedGroupFactory(name="child-group-1")
        child_2 = factories.ManagedGroupFactory(name="child-group-2")
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child_1)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child_2)
        self.assertEqual(grandparent.get_all_children().count(), 3)
        self.assertQuerySetEqual(
            grandparent.get_all_children(),
            ManagedGroup.objects.filter(pk__in=[parent.pk, child_1.pk, child_2.pk]),
            ordered=False,
        )

    def test_get_all_children_two_grandchildren_two_parents(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent_1 = factories.ManagedGroupFactory(name="parent-group-1")
        parent_2 = factories.ManagedGroupFactory(name="parent-group-2")
        child_1 = factories.ManagedGroupFactory(name="child-group-1")
        child_2 = factories.ManagedGroupFactory(name="child-group-2")
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent_1)
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent_2)
        factories.GroupGroupMembershipFactory.create(parent_group=parent_1, child_group=child_1)
        factories.GroupGroupMembershipFactory.create(parent_group=parent_2, child_group=child_2)
        self.assertEqual(grandparent.get_all_children().count(), 4)
        self.assertQuerySetEqual(
            grandparent.get_all_children(),
            ManagedGroup.objects.filter(pk__in=[parent_1.pk, parent_2.pk, child_1.pk, child_2.pk]),
            ordered=False,
        )

    def test_get_all_children_multiple_paths_to_same_group(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        # Then create a grandparent-child direct relationship.
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=child)
        self.assertEqual(grandparent.get_all_children().count(), 2)
        self.assertQuerySetEqual(
            grandparent.get_all_children(),
            ManagedGroup.objects.filter(pk__in=[parent.pk, child.pk]),
            ordered=False,
        )

    def test_all_children_greatgrandparent(self):
        greatgrandparent = factories.ManagedGroupFactory(name="greatgrandparent-group")
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(parent_group=greatgrandparent, child_group=grandparent)
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.assertEqual(greatgrandparent.get_all_children().count(), 3)
        self.assertQuerySetEqual(
            greatgrandparent.get_all_children(),
            ManagedGroup.objects.filter(pk__in=[grandparent.pk, parent.pk, child.pk]),
            ordered=False,
        )

    def test_get_all_children_with_other_group(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        # Create a group with no relationships
        group = factories.ManagedGroupFactory.create(name="other-group")
        self.assertEqual(group.get_all_children().count(), 0)

    def test_cannot_delete_group_used_as_is_in_authorization_domain(self):
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        workspace.authorization_domains.add(group)
        with self.assertRaises(ProtectedError):
            group.delete()
        self.assertEqual(len(ManagedGroup.objects.all()), 1)
        self.assertIn(group, ManagedGroup.objects.all())

    def test_get_anvil_url(self):
        """get_anvil_url returns a string."""
        group = factories.ManagedGroupFactory.create()
        self.assertIsInstance(group.get_anvil_url(), str)


class ManagedGroupGraphTest(TestCase):
    def test_get_full_graph(self):
        groups = factories.ManagedGroupFactory.create_batch(5)
        grandparent_group = groups[0]
        parent_group_1 = groups[1]
        parent_group_2 = groups[2]
        child_group_1 = groups[3]
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent_group, child_group=parent_group_1)
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent_group, child_group=parent_group_2)
        factories.GroupGroupMembershipFactory.create(parent_group=parent_group_1, child_group=child_group_1)
        G = ManagedGroup.get_full_graph()
        # Check nodes.
        self.assertIsInstance(G, nx.DiGraph)
        self.assertEqual(len(G.nodes), 5)
        self.assertIn(str(groups[0]), G.nodes)
        self.assertIn(str(groups[1]), G.nodes)
        self.assertIn(str(groups[2]), G.nodes)
        self.assertIn(str(groups[3]), G.nodes)
        self.assertIn(str(groups[4]), G.nodes)
        # Check edges.
        self.assertEqual(len(G.edges), 3)
        self.assertIn((grandparent_group.name, parent_group_1.name), G.edges)
        self.assertIn((grandparent_group.name, parent_group_2.name), G.edges)
        self.assertIn((parent_group_1.name, child_group_1.name), G.edges)

    def test_get_graph(self):
        groups = factories.ManagedGroupFactory.create_batch(5)
        grandparent_group = groups[0]
        parent_group_1 = groups[1]
        parent_group_2 = groups[2]
        child_group_1 = groups[3]
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent_group, child_group=parent_group_1)
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent_group, child_group=parent_group_2)
        factories.GroupGroupMembershipFactory.create(parent_group=parent_group_1, child_group=child_group_1)
        G = parent_group_1.get_graph()
        # Check nodes.
        self.assertIsInstance(G, nx.DiGraph)
        self.assertEqual(len(G.nodes), 3)
        self.assertIn(str(parent_group_1), G.nodes)
        self.assertIn(str(grandparent_group), G.nodes)
        self.assertIn(str(child_group_1), G.nodes)
        # Check edges.
        self.assertEqual(len(G.edges), 2)
        self.assertIn((grandparent_group.name, parent_group_1.name), G.edges)
        self.assertIn((parent_group_1.name, child_group_1.name), G.edges)


class WorkspaceTest(TestCase):
    """Tests for the Workspace model that do not make AnVIL API calls."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        billing_project = factories.BillingProjectFactory.create()
        instance = Workspace(
            billing_project=billing_project,
            name="my-name",
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        instance.save()
        self.assertIsInstance(instance, Workspace)

    def test_name_max_length(self):
        """ValidationError is raised when the group name is too long."""
        billing_project = factories.BillingProjectFactory.create()
        instance = factories.WorkspaceFactory.build(billing_project=billing_project, name="a" * 254)
        instance.full_clean()
        instance = factories.WorkspaceFactory.build(billing_project=billing_project, name="a" * 255)
        with self.assertRaises(ValidationError):
            instance.full_clean()

    def test_note_field(self):
        """Creation using the model constructor and .save() works when note is set."""
        billing_project = factories.BillingProjectFactory.create()
        instance = Workspace(
            billing_project=billing_project,
            name="my-name",
            workspace_type=DefaultWorkspaceAdapter().get_type(),
            note="test note",
        )
        instance.save()
        self.assertIsInstance(instance, Workspace)
        self.assertEqual(instance.note, "test note")

    def test_is_locked_default(self):
        """Default value for is_locked is set as expected."""
        billing_project = factories.BillingProjectFactory.create()
        instance = Workspace(
            billing_project=billing_project,
            name="my-name",
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        self.assertFalse(instance.is_locked)

    def test_is_locked_true(self):
        """is_locked can be set to True."""
        billing_project = factories.BillingProjectFactory.create()
        instance = Workspace(
            billing_project=billing_project,
            name="my-name",
            workspace_type=DefaultWorkspaceAdapter().get_type(),
            is_locked=True,
        )
        self.assertTrue(instance.is_locked)

    def test_is_requester_pays_default(self):
        """Default value for is_requester_pays is set as expected."""
        billing_project = factories.BillingProjectFactory.create()
        instance = Workspace(
            billing_project=billing_project,
            name="my-name",
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        self.assertFalse(instance.is_requester_pays)

    def test_is_requester_pays_true(self):
        """is_requester_pays can be set to True."""
        billing_project = factories.BillingProjectFactory.create()
        instance = Workspace(
            billing_project=billing_project,
            name="my-name",
            workspace_type=DefaultWorkspaceAdapter().get_type(),
            is_requester_pays=True,
        )
        self.assertTrue(instance.is_requester_pays)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.WorkspaceFactory.build(
            billing_project__name="my-project",
            name="my-name",
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "my-project/my-name")

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.WorkspaceFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_history(self):
        """A simple history record is created when model is updated."""
        obj = factories.WorkspaceFactory.create(name="original-name")
        # History was created.
        self.assertEqual(obj.history.count(), 1)
        # A new entry is created on update.
        obj.name = "updated-name"
        obj.save()
        self.assertEqual(obj.history.count(), 2)
        # An entry is created upon deletion.
        obj.delete()
        self.assertEqual(Workspace.history.count(), 3)

    def test_history_foreign_key_billing_project(self):
        """History is retained when a billing_project foreign key object is deleted."""
        obj = factories.WorkspaceFactory.create()
        obj.delete()  # Delete because of a on_delete=PROTECT foreign key.
        # History was created.
        self.assertEqual(Workspace.history.count(), 2)
        # Entries are retained when a foreign key is deleted.
        billing_project_pk = obj.billing_project.pk
        obj.billing_project.delete()
        self.assertEqual(Workspace.history.count(), 2)
        # Make sure you can access it.
        self.assertEqual(Workspace.history.all()[1].billing_project_id, billing_project_pk)

    def test_workspace_on_delete_is_in_authorization_domain(self):
        """Workspace can be deleted if it has an authorization domain."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        workspace.authorization_domains.add(group)
        workspace.delete()
        self.assertEqual(Workspace.objects.count(), 0)
        # Also deletes the relationship.
        self.assertEqual(WorkspaceAuthorizationDomain.objects.count(), 0)

    def test_workspace_on_delete_access(self):
        """Workspace can be deleted if a group has access to it."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceGroupSharingFactory(group=group, workspace=workspace)
        workspace.delete()
        self.assertEqual(Workspace.objects.count(), 0)
        # Also deletes the relationship.
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 0)

    @skip("Add this constraint.")
    def test_name_save_case_insensitivity(self):
        """Cannot save two models with the same case-insensitive name in the same billing project."""
        billing_project = factories.BillingProjectFactory.create()
        name = "AbAbA"
        factories.WorkspaceFactory.create(billing_project=billing_project, name=name)
        instance = Workspace(billing_project=billing_project, name=name.lower())
        with self.assertRaises(IntegrityError):
            instance.save()

    def test_cannot_have_duplicated_billing_project_and_name(self):
        """Cannot have two workspaces with the same billing_project and name."""
        billing_project = factories.BillingProjectFactory.create()
        name = "test-name"
        instance1 = Workspace(billing_project=billing_project, name=name)
        instance1.save()
        instance2 = Workspace(billing_project=billing_project, name=name)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_can_have_same_name_in_different_billing_project(self):
        """Can have two workspaces with the same name but in different billing_projects."""
        name = "test-name"
        billing_project_1 = factories.BillingProjectFactory.create(name="test-project-1")
        billing_project_2 = factories.BillingProjectFactory.create(name="test-project-2")
        instance1 = Workspace(billing_project=billing_project_1, name=name)
        instance1.save()
        instance2 = Workspace(billing_project=billing_project_2, name=name)
        instance2.save()
        self.assertEqual(Workspace.objects.count(), 2)

    def test_can_have_same_billing_project_with_different_names(self):
        """Can have two workspaces with different names in the same namespace."""
        billing_project = factories.BillingProjectFactory.create(name="test-project")
        instance1 = Workspace(billing_project=billing_project, name="name-1")
        instance1.save()
        instance2 = Workspace(billing_project=billing_project, name="name-2")
        instance2.save()
        self.assertEqual(Workspace.objects.count(), 2)

    def test_get_full_name(self):
        billing_project = factories.BillingProjectFactory.create(name="test-project")
        instance = Workspace(billing_project=billing_project, name="test-name")
        instance.save()
        self.assertEqual(instance.get_full_name(), "test-project/test-name")

    def test_cannot_create_with_invalid_billing_project(self):
        instance = Workspace(name="test-name")
        with self.assertRaises(IntegrityError):
            instance.save()

    def test_one_is_in_authorization_domain(self):
        """Can create a workspace with one authorization domain."""
        is_in_authorization_domain = factories.ManagedGroupFactory.create()
        billing_project = factories.BillingProjectFactory.create(name="test-project")
        instance = Workspace(billing_project=billing_project, name="test-name")
        instance.save()
        instance.authorization_domains.set(ManagedGroup.objects.all())
        self.assertEqual(len(instance.authorization_domains.all()), 1)
        self.assertIn(is_in_authorization_domain, instance.authorization_domains.all())

    def test_two_is_in_authorization_domains(self):
        """Can create a workspace with two authorization domains."""
        is_in_authorization_domain_1 = factories.ManagedGroupFactory.create()
        is_in_authorization_domain_2 = factories.ManagedGroupFactory.create()
        billing_project = factories.BillingProjectFactory.create(name="test-project")
        instance = Workspace(billing_project=billing_project, name="test-name")
        instance.save()
        instance.authorization_domains.set(ManagedGroup.objects.all())
        self.assertEqual(len(instance.authorization_domains.all()), 2)
        self.assertIn(is_in_authorization_domain_1, instance.authorization_domains.all())
        self.assertIn(is_in_authorization_domain_2, instance.authorization_domains.all())

    def test_is_in_authorization_domain_unique(self):
        """Adding the same auth domain twice does nothing."""
        is_in_authorization_domain = factories.ManagedGroupFactory.create()
        billing_project = factories.BillingProjectFactory.create(name="test-project")
        instance = Workspace(billing_project=billing_project, name="test-name")
        instance.save()
        instance.authorization_domains.add(is_in_authorization_domain)
        instance.authorization_domains.add(is_in_authorization_domain)
        self.assertEqual(len(instance.authorization_domains.all()), 1)
        self.assertIn(is_in_authorization_domain, instance.authorization_domains.all())

    def test_can_delete_workspace_with_is_in_authorization_domain(self):
        is_in_authorization_domain = factories.ManagedGroupFactory.create()
        billing_project = factories.BillingProjectFactory.create(name="test-project")
        instance = Workspace(billing_project=billing_project, name="test-name")
        instance.save()
        instance.authorization_domains.add(is_in_authorization_domain)
        instance.save()
        # Now try to delete it.
        instance.refresh_from_db()
        instance.delete()
        self.assertEqual(len(Workspace.objects.all()), 0)
        self.assertEqual(len(WorkspaceAuthorizationDomain.objects.all()), 0)
        # The group has not been deleted.
        self.assertIn(is_in_authorization_domain, ManagedGroup.objects.all())

    def test_get_anvil_url(self):
        """get_anvil_url returns a string."""
        instance = factories.WorkspaceFactory.create()
        self.assertIsInstance(instance.get_anvil_url(), str)

    def test_workspace_type_not_registered(self):
        """A ValidationError is raised if the workspace_type is not a registered adapter type."""
        billing_project = factories.BillingProjectFactory.create()
        instance = factories.WorkspaceFactory.build(billing_project=billing_project, workspace_type="foo")
        with self.assertRaises(ValidationError) as e:
            instance.clean_fields()
        self.assertIn("not a registered adapter type", str(e.exception))


class WorkspaceGroupSharingMethodsTest(TestCase):
    """Tests for the is_in_authorization_domain, is_shared, and has_access Workspace and ManagedGroup methods."""

    def setUp(self):
        super().setUp()
        self.workspace = factories.WorkspaceFactory.create()
        self.auth_domain = factories.ManagedGroupFactory.create()
        self.group = factories.ManagedGroupFactory.create()

    def test_is_in_authorization_domain_no_auth_domain(self):
        """is_in_authorization_domain returns False when group is not in the auth domain."""
        self.assertTrue(self.workspace.is_in_authorization_domain(self.group))
        self.assertTrue(self.group.is_in_authorization_domain(self.workspace))

    def test_is_in_authorization_domain_not_in_domain(self):
        """is_in_authorization_domain returns False when group is not in the auth domain."""
        self.workspace.authorization_domains.add(self.auth_domain)
        self.assertFalse(self.workspace.is_in_authorization_domain(self.group))
        self.assertFalse(self.group.is_in_authorization_domain(self.workspace))

    def test_is_in_authorization_domain_in_domain(self):
        """is_in_authorization_domain returns True when group is in the auth domain."""
        self.workspace.authorization_domains.add(self.auth_domain)
        factories.GroupGroupMembershipFactory.create(
            parent_group=self.auth_domain,
            child_group=self.group,
        )
        self.assertTrue(self.workspace.is_in_authorization_domain(self.group))
        self.assertTrue(self.group.is_in_authorization_domain(self.workspace))

    def test_is_in_authorization_domain_parent_group_in_domain(self):
        """is_in_authorization_domain returns True when the parent group is in the auth domain."""
        self.workspace.authorization_domains.add(self.auth_domain)
        parent_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(
            parent_group=self.auth_domain,
            child_group=parent_group,
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent_group,
            child_group=self.group,
        )
        self.assertTrue(self.workspace.is_in_authorization_domain(self.group))
        self.assertTrue(self.group.is_in_authorization_domain(self.workspace))

    def test_is_in_authorization_domain_grandparent_group_in_domain(self):
        """is_in_authorization_domain returns True when a grandparent group is in the auth domain."""
        self.workspace.authorization_domains.add(self.auth_domain)
        grandparent_group = factories.ManagedGroupFactory.create()
        parent_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(
            parent_group=self.auth_domain,
            child_group=grandparent_group,
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent_group,
            child_group=parent_group,
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent_group,
            child_group=self.group,
        )
        self.assertTrue(self.workspace.is_in_authorization_domain(self.group))
        self.assertTrue(self.group.is_in_authorization_domain(self.workspace))

    def test_is_in_auth_domain_two_auth_domains_in_both(self):
        """is_in_authorization_domain returns True when a workspace has two auth domains and the group is in both."""
        self.workspace.authorization_domains.add(self.auth_domain)
        auth_domain_2 = factories.ManagedGroupFactory.create()
        self.workspace.authorization_domains.add(auth_domain_2)
        # Add the group to both auth domains.
        factories.GroupGroupMembershipFactory.create(
            parent_group=self.auth_domain,
            child_group=self.group,
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=auth_domain_2,
            child_group=self.group,
        )
        self.assertTrue(self.workspace.is_in_authorization_domain(self.group))
        self.assertTrue(self.group.is_in_authorization_domain(self.workspace))

    def test_is_in_auth_domain_two_auth_domains_in_one(self):
        """is_in_authorization_domain returns True when a workspace has two auth domains and the group is in one."""
        self.workspace.authorization_domains.add(self.auth_domain)
        auth_domain_2 = factories.ManagedGroupFactory.create()
        self.workspace.authorization_domains.add(auth_domain_2)
        # Add the group to one auth domains.
        factories.GroupGroupMembershipFactory.create(
            parent_group=auth_domain_2,
            child_group=self.group,
        )
        self.assertFalse(self.workspace.is_in_authorization_domain(self.group))
        self.assertFalse(self.group.is_in_authorization_domain(self.workspace))

    def test_is_in_auth_domain_two_auth_domains_in_none(self):
        """is_in_authorization_domain returns True when a workspace has two auth domains and a group is in neither."""
        self.workspace.authorization_domains.add(self.auth_domain)
        auth_domain_2 = factories.ManagedGroupFactory.create()
        self.workspace.authorization_domains.add(auth_domain_2)
        # Do not add the group to either auth domain.
        self.assertFalse(self.workspace.is_in_authorization_domain(self.group))
        self.assertFalse(self.group.is_in_authorization_domain(self.workspace))

    def test_is_in_auth_domain_child(self):
        """is_in_auth_domain returns False when a child group is in the auth domain but not the group."""
        self.workspace.authorization_domains.add(self.auth_domain)
        child_group = factories.ManagedGroupFactory.create()
        # Add the child group to the auth domain.
        factories.GroupGroupMembershipFactory.create(parent_group=self.auth_domain, child_group=child_group)
        # Add the child group to the group.
        factories.GroupGroupMembershipFactory.create(parent_group=self.group, child_group=child_group)
        # Do not add the group itself to the auth domain.
        self.assertFalse(self.workspace.is_in_authorization_domain(self.group))
        self.assertFalse(self.group.is_in_authorization_domain(self.workspace))

    def test_is_shared_not_shared(self):
        """Returns False when the workspace is not shared with the group."""
        self.assertFalse(self.workspace.is_shared(self.group))
        self.assertFalse(self.group.is_shared(self.workspace))

    def test_is_shared_is_shared(self):
        """Returns True when the workspace is shared with the group."""
        factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace, group=self.group)
        self.assertTrue(self.workspace.is_shared(self.group))
        self.assertTrue(self.group.is_shared(self.workspace))

    def test_is_shared_shared_with_parent(self):
        """Returns False when the workspace is shared with a parent group."""
        # Create the parent group structure.
        parent_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent_group, child_group=self.group)
        # Share with the parent.
        factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace, group=parent_group)
        self.assertTrue(self.workspace.is_shared(self.group))
        self.assertTrue(self.group.is_shared(self.workspace))

    def test_is_shared_shared_with_grandparent(self):
        """Returns False when the workspace is shared with the grandparent group."""
        # Create the grandparent group structure.
        grandparent_group = factories.ManagedGroupFactory.create()
        parent_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent_group, child_group=parent_group)
        factories.GroupGroupMembershipFactory.create(parent_group=parent_group, child_group=self.group)
        # Share with the grandparent.
        factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace, group=grandparent_group)
        self.assertTrue(self.workspace.is_shared(self.group))
        self.assertTrue(self.group.is_shared(self.workspace))

    def test_is_shared_shared_with_child(self):
        """Returns False when the workspace is shared with a child group but not the group itself."""
        child_group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=self.group, child_group=child_group)
        # Share with the child.
        factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace, group=child_group)
        self.assertFalse(self.workspace.is_shared(self.group))
        self.assertFalse(self.group.is_shared(self.workspace))


class WorkspaceDataTest(TestCase):
    """Tests for the WorkspaceData models (default and base)."""

    def test_get_absolute_url(self):
        """get_absolute_url returns the url of the workspace."""
        workspace = factories.WorkspaceFactory.create()
        workspace_data = DefaultWorkspaceData(workspace=workspace)
        self.assertEqual(workspace_data.get_absolute_url(), workspace.get_absolute_url())

    def test_str(self):
        workspace = factories.WorkspaceFactory.create()
        workspace_data = DefaultWorkspaceData(workspace=workspace)
        self.assertEqual(str(workspace_data), str(workspace))


class WorkspaceAuthorizationDomainTestCase(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        instance = WorkspaceAuthorizationDomain(workspace=workspace, group=group)
        instance.save()
        self.assertIsInstance(instance, WorkspaceAuthorizationDomain)

    def test_str_method(self):
        """Creation using the model constructor and .save() works."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        instance = WorkspaceAuthorizationDomain(workspace=workspace, group=group)
        instance.save()
        self.assertIsInstance(instance.__str__(), str)

    def test_history(self):
        """A simple history record is created when model is updated."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        obj = WorkspaceAuthorizationDomain(workspace=workspace, group=group)
        obj.save()
        # History was created.
        self.assertEqual(obj.history.count(), 1)
        # No entries on update since this is a many-to-many through table with no extra information.
        # An entry is created upon deletion.
        obj.delete()
        self.assertEqual(WorkspaceAuthorizationDomain.history.count(), 2)

    def test_history_foreign_key_workspace(self):
        """History is retained when a group foreign key object is deleted."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = WorkspaceAuthorizationDomain(workspace=workspace, group=group)
        obj.save()
        obj.delete()  # Delete because of a on_delete=PROTECT foreign key.
        # Entries are retained when the foreign key is deleted.
        workspace_pk = workspace.pk
        workspace.delete()
        self.assertEqual(WorkspaceAuthorizationDomain.history.count(), 2)
        # Make sure you can access it.
        self.assertEqual(WorkspaceAuthorizationDomain.history.earliest().workspace_id, workspace_pk)

    def test_history_foreign_key_group(self):
        """History is retained when a workspace foreign key object is deleted."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = WorkspaceAuthorizationDomain(workspace=workspace, group=group)
        obj.save()
        # Entries are retained when the foreign key is deleted.
        obj.delete()  # Delete because of a on_delete=PROTECT foreign key.
        group_pk = group.pk
        group.delete()
        self.assertEqual(WorkspaceAuthorizationDomain.history.count(), 2)
        # Make sure you can still access the history.
        self.assertEqual(WorkspaceAuthorizationDomain.history.earliest().group_id, group_pk)


class GroupGroupMembershipTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        parent_group = factories.ManagedGroupFactory.create(name="parent")
        child_group = factories.ManagedGroupFactory.create(name="child")
        instance = GroupGroupMembership(parent_group=parent_group, child_group=child_group)
        self.assertIsInstance(instance, GroupGroupMembership)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        parent_group = factories.ManagedGroupFactory.create(name="parent")
        child_group = factories.ManagedGroupFactory.create(name="child")
        instance = GroupGroupMembership(parent_group=parent_group, child_group=child_group)
        self.assertIsInstance(instance.__str__(), str)
        expected_string = "child as MEMBER in parent"
        self.assertEqual(instance.__str__(), expected_string)

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.GroupGroupMembershipFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_history(self):
        """A simple history record is created when model is updated."""
        obj = factories.GroupGroupMembershipFactory.create(role=GroupGroupMembership.MEMBER)
        # History was created.
        self.assertEqual(obj.history.count(), 1)
        # A new entry was created after update.
        obj.role = GroupGroupMembership.ADMIN
        obj.save()
        self.assertEqual(obj.history.count(), 2)
        # An entry is created upon deletion.
        obj.delete()
        self.assertEqual(GroupGroupMembership.history.count(), 3)

    def test_history_foreign_key_parent_group(self):
        """History is retained when a parent group foreign key object is deleted."""
        obj = factories.GroupGroupMembershipFactory.create()
        # Entries are retained when the parent group foreign key is deleted.
        parent_group_pk = obj.parent_group.pk
        obj.parent_group.delete()
        self.assertEqual(GroupGroupMembership.history.count(), 2)
        # Make sure you can access it.
        self.assertEqual(GroupGroupMembership.history.earliest().parent_group_id, parent_group_pk)

    def test_history_foreign_key_child_group(self):
        """History is retained when a child group foreign key object is deleted."""
        obj = factories.GroupGroupMembershipFactory.create()
        # Entries are retained when the parent group foreign key is deleted.
        child_group_pk = obj.child_group.pk
        obj.delete()  # Delete because of a on_delete=PROTECT foreign key.
        obj.child_group.delete()
        self.assertEqual(GroupGroupMembership.history.count(), 2)
        # Make sure you can access it.
        self.assertEqual(GroupGroupMembership.history.earliest().child_group_id, child_group_pk)

    def test_same_group_with_two_parent_groups(self):
        """The same group can be a child in two groups."""
        child_group = factories.ManagedGroupFactory(name="child")
        group_1 = factories.ManagedGroupFactory(name="parent-1")
        group_2 = factories.ManagedGroupFactory(name="parent-2")
        instance = GroupGroupMembership(parent_group=group_1, child_group=child_group)
        instance.save()
        instance = GroupGroupMembership(parent_group=group_2, child_group=child_group)
        instance.save()
        self.assertEqual(GroupGroupMembership.objects.count(), 2)

    def test_two_groups_in_same_parent_group(self):
        """Two accounts can be in the same group."""
        child_1 = factories.ManagedGroupFactory(name="child-1")
        child_2 = factories.ManagedGroupFactory(name="child-2")
        parent = factories.ManagedGroupFactory(name="parent")
        instance = GroupGroupMembership(parent_group=parent, child_group=child_1)
        instance.save()
        instance = GroupGroupMembership(parent_group=parent, child_group=child_2)
        instance.save()
        self.assertEqual(GroupGroupMembership.objects.count(), 2)

    def test_cannot_have_duplicated_parent_and_child_with_same_role(self):
        """Cannot have the same child in the same group with the same role twice."""
        child_group = factories.ManagedGroupFactory()
        parent_group = factories.ManagedGroupFactory()
        instance_1 = GroupGroupMembership(
            parent_group=parent_group,
            child_group=child_group,
            role=GroupGroupMembership.MEMBER,
        )
        instance_1.save()
        instance_2 = GroupGroupMembership(
            parent_group=parent_group,
            child_group=child_group,
            role=GroupGroupMembership.MEMBER,
        )
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_cannot_have_duplicated_parent_and_child_with_different_role(self):
        """Cannot have the same child in the same group with a different role twice."""
        child_group = factories.ManagedGroupFactory()
        parent_group = factories.ManagedGroupFactory()
        instance_1 = GroupGroupMembership(
            parent_group=parent_group,
            child_group=child_group,
            role=GroupGroupMembership.MEMBER,
        )
        instance_1.save()
        instance_2 = GroupGroupMembership(
            parent_group=parent_group,
            child_group=child_group,
            role=GroupGroupMembership.ADMIN,
        )
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_cant_add_a_group_to_itself_member(self):
        group = factories.ManagedGroupFactory()
        instance = GroupGroupMembership(parent_group=group, child_group=group, role=GroupGroupMembership.MEMBER)
        with self.assertRaises(ValidationError):
            instance.clean()

    def test_cant_add_a_group_to_itself_admin(self):
        group = factories.ManagedGroupFactory()
        instance = GroupGroupMembership(parent_group=group, child_group=group, role=GroupGroupMembership.ADMIN)
        with self.assertRaisesRegex(ValidationError, "add a group to itself"):
            instance.clean()

    def test_circular_cant_add_parent_group_as_a_child(self):
        obj = factories.GroupGroupMembershipFactory.create(role=GroupGroupMembership.MEMBER)
        instance = GroupGroupMembership(
            parent_group=obj.child_group,
            child_group=obj.parent_group,
            role=GroupGroupMembership.MEMBER,
        )
        with self.assertRaisesRegex(ValidationError, "circular"):
            instance.clean()

    def test_circular_cant_add_grandparent_group_as_a_grandchild(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        instance = GroupGroupMembership(
            parent_group=child,
            child_group=grandparent,
            role=GroupGroupMembership.MEMBER,
        )
        with self.assertRaisesRegex(ValidationError, "circular"):
            instance.clean()

    def test_circular_multiple_paths(self):
        grandparent = factories.ManagedGroupFactory(name="grandparent-group")
        parent = factories.ManagedGroupFactory(name="parent-group")
        child = factories.ManagedGroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        # Also create a grandparent-child relationship.
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=child)
        instance = GroupGroupMembership(
            parent_group=child,
            child_group=grandparent,
            role=GroupGroupMembership.MEMBER,
        )
        with self.assertRaisesRegex(ValidationError, "circular"):
            instance.clean()


class GroupAccountMembershipTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        account = factories.AccountFactory.create()
        group = factories.ManagedGroupFactory.create()
        instance = GroupAccountMembership(account=account, group=group)
        self.assertIsInstance(instance, GroupAccountMembership)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        email = "email@example.com"
        group = "test-group"
        account = factories.AccountFactory(email=email)
        group = factories.ManagedGroupFactory(name=group)
        instance = GroupAccountMembership(account=account, group=group, role=GroupAccountMembership.MEMBER)
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        expected_string = "{email} as MEMBER in {group}".format(email=email, group=group)
        self.assertEqual(instance.__str__(), expected_string)

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.GroupAccountMembershipFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_history(self):
        """A simple history record is created when model is updated."""
        obj = factories.GroupAccountMembershipFactory.create(role=GroupAccountMembership.MEMBER)
        # History was created.
        self.assertEqual(obj.history.count(), 1)
        # A new entry was created after update.
        obj.role = GroupAccountMembership.ADMIN
        obj.save()
        self.assertEqual(obj.history.count(), 2)
        # An entry is created upon deletion.
        obj.delete()
        self.assertEqual(GroupAccountMembership.history.count(), 3)

    def test_history_foreign_key_group(self):
        """History is retained when a group foreign key object is deleted."""
        obj = factories.GroupAccountMembershipFactory.create()
        # History was created.
        self.assertEqual(GroupAccountMembership.history.count(), 1)
        # Entries are retained when the foreign key is deleted.
        group_pk = obj.group.pk
        obj.group.delete()
        self.assertEqual(GroupAccountMembership.history.count(), 2)
        # Make sure you can access it.
        self.assertEqual(GroupAccountMembership.history.earliest().group_id, group_pk)

    def test_history_foreign_key_account(self):
        """History is retained when an account foreign key object is deleted."""
        obj = factories.GroupAccountMembershipFactory.create()
        # History was created.
        self.assertEqual(GroupAccountMembership.history.count(), 1)
        # Entries are retained when the foreign key is deleted.
        account_pk = obj.account.pk
        obj.account.delete()
        self.assertEqual(GroupAccountMembership.history.count(), 2)
        # Make sure you can access it.
        self.assertEqual(GroupAccountMembership.history.earliest().account_id, account_pk)

    def test_history_inactive_user(self):
        """Account active/inactive status is correct at time of history check."""
        # Create an account.
        account = factories.AccountFactory.create()
        # Create a group.
        group = factories.ManagedGroupFactory.create()
        # Add the account to the group.
        obj = factories.GroupAccountMembershipFactory.create(
            account=account, group=group, role=GroupAccountMembership.MEMBER
        )
        # Timestamp
        current_time = timezone.now()
        # Sleep a tiny bit so are history records are sure to not have the same timestamp
        time.sleep(0.1)
        # Mark the account as inactive.
        account.status = account.INACTIVE_STATUS
        account.save()
        # Check the history at timestamp to make sure the account shows active.
        record = obj.history.as_of(current_time)

        self.assertEqual(account.history.as_of(current_time).status, record.account.ACTIVE_STATUS)
        self.assertEqual(record.account.status, record.account.ACTIVE_STATUS)

    def test_same_account_in_two_groups(self):
        """The same account can be in two groups."""
        account = factories.AccountFactory()
        group_1 = factories.ManagedGroupFactory(name="group-1")
        group_2 = factories.ManagedGroupFactory(name="group-2")
        instance = GroupAccountMembership(account=account, group=group_1)
        instance.save()
        instance = GroupAccountMembership(account=account, group=group_2)
        instance.save()

    def test_two_accounts_in_same_group(self):
        """Two accounts can be in the same group."""
        account_1 = factories.AccountFactory(email="email_1@example.com")
        account_2 = factories.AccountFactory(email="email_2@example.com")
        group = factories.ManagedGroupFactory()
        instance = GroupAccountMembership(account=account_1, group=group)
        instance.save()
        instance = GroupAccountMembership(account=account_2, group=group)
        instance.save()

    def test_cannot_have_duplicated_account_and_group_with_same_role(self):
        """Cannot have the same account in the same group with the same role twice."""
        account = factories.AccountFactory()
        group = factories.ManagedGroupFactory()
        instance_1 = GroupAccountMembership(account=account, group=group, role=GroupAccountMembership.MEMBER)
        instance_1.save()
        instance_2 = GroupAccountMembership(account=account, group=group, role=GroupAccountMembership.MEMBER)
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_cannot_have_duplicated_account_and_group_with_different_role(self):
        """Cannot have the same account in the same group with different roles twice."""
        account = factories.AccountFactory()
        group = factories.ManagedGroupFactory()
        instance_1 = GroupAccountMembership(account=account, group=group, role=GroupAccountMembership.MEMBER)
        instance_1.save()
        instance_2 = GroupAccountMembership(account=account, group=group, role=GroupAccountMembership.ADMIN)
        with self.assertRaises(IntegrityError):
            instance_2.save()


class WorkspaceGroupSharingTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        instance = WorkspaceGroupSharing(
            group=group,
            workspace=workspace,
            access=WorkspaceGroupSharing.READER,
            can_compute=False,
        )
        self.assertIsInstance(instance, WorkspaceGroupSharing)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        billing_project_name = "test-namespace"
        workspace_name = "test-workspace"
        group_name = "test-group"
        billing_project = factories.BillingProjectFactory(name=billing_project_name)
        group = factories.ManagedGroupFactory(name=group_name)
        workspace = factories.WorkspaceFactory(billing_project=billing_project, name=workspace_name)
        instance = WorkspaceGroupSharing(group=group, workspace=workspace, access=WorkspaceGroupSharing.READER)
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        expected_string = "test-group with READER to test-namespace/test-workspace"
        self.assertEqual(instance.__str__(), expected_string)

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.WorkspaceGroupSharingFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_clean_reader_can_compute(self):
        """Clean method raises a ValidationError if a READER has can_compute=True"""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        instance = WorkspaceGroupSharing(
            group=group,
            workspace=workspace,
            access=WorkspaceGroupSharing.READER,
            can_compute=True,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.messages), 1)
        self.assertIn("READER", e.exception.messages[0])
        self.assertIn("compute privileges", e.exception.messages[0])

    def test_clean_writer_can_compute(self):
        """Clean method succeeds if a WRITER has can_compute=True"""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        instance = WorkspaceGroupSharing(
            group=group,
            workspace=workspace,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        instance.full_clean()

    def test_clean_owner_can_compute(self):
        """Clean method succeeds if an OWNER has can_compute=True"""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        instance = WorkspaceGroupSharing(
            group=group,
            workspace=workspace,
            access=WorkspaceGroupSharing.OWNER,
            can_compute=True,
        )
        instance.full_clean()

    def test_clean_owner_can_compute_false(self):
        """Clean method raises ValidationError if an OWNER has can_compute=False"""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        instance = WorkspaceGroupSharing(
            group=group,
            workspace=workspace,
            access=WorkspaceGroupSharing.OWNER,
            can_compute=False,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.messages), 1)
        self.assertIn("OWNER", e.exception.messages[0])
        self.assertIn("compute privileges", e.exception.messages[0])

    def test_history(self):
        """A simple history record is created when model is updated."""
        obj = factories.WorkspaceGroupSharingFactory.create(access=WorkspaceGroupSharing.READER)
        # History was created.
        self.assertEqual(obj.history.count(), 1)
        # A new entry was created after update.
        obj.access = WorkspaceGroupSharing.WRITER
        obj.save()
        self.assertEqual(obj.history.count(), 2)
        # An entry is created upon deletion.
        obj.delete()
        self.assertEqual(WorkspaceGroupSharing.history.count(), 3)

    def test_history_foreign_key_workspace(self):
        """History is retained when a workspace foreign key object is deleted."""
        obj = factories.WorkspaceGroupSharingFactory.create()
        # History was created.
        self.assertEqual(WorkspaceGroupSharing.history.count(), 1)
        # Entries are retained when the foreign key is deleted.
        workspace_pk = obj.workspace.pk
        obj.workspace.delete()
        self.assertEqual(WorkspaceGroupSharing.history.count(), 2)
        # Make sure you can access it.
        self.assertEqual(WorkspaceGroupSharing.history.earliest().workspace_id, workspace_pk)

    def test_history_foreign_key_group(self):
        """History is retained when a group foreign key object is deleted."""
        obj = factories.WorkspaceGroupSharingFactory.create()
        # Entries are retained when the foreign key is deleted.
        group_pk = obj.group.pk
        obj.delete()  # Delete because of a on_delete=PROTECT foreign key.
        obj.group.delete()
        self.assertEqual(WorkspaceGroupSharing.history.count(), 2)
        # Make sure you can access it.
        self.assertEqual(WorkspaceGroupSharing.history.earliest().group_id, group_pk)

    def test_same_group_in_two_workspaces(self):
        """The same group can have access to two workspaces."""
        group = factories.ManagedGroupFactory()
        workspace_1 = factories.WorkspaceFactory(name="workspace-1")
        workspace_2 = factories.WorkspaceFactory(name="workspace-2")
        instance = WorkspaceGroupSharing(group=group, workspace=workspace_1)
        instance.save()
        instance = WorkspaceGroupSharing(group=group, workspace=workspace_2)
        instance.save()

    def test_two_groups_and_same_workspace(self):
        """Two accounts can be in the same group."""
        group_1 = factories.ManagedGroupFactory(name="group-1")
        group_2 = factories.ManagedGroupFactory(name="group-2")
        workspace = factories.WorkspaceFactory()
        instance = WorkspaceGroupSharing(group=group_1, workspace=workspace)
        instance.save()
        instance = WorkspaceGroupSharing(group=group_2, workspace=workspace)
        instance.save()

    def test_cannot_have_duplicated_account_and_group_with_same_access(self):
        """Cannot have the same account in the same group with the same access levels twice."""
        group = factories.ManagedGroupFactory()
        workspace = factories.WorkspaceFactory()
        instance_1 = WorkspaceGroupSharing(group=group, workspace=workspace, access=WorkspaceGroupSharing.READER)
        instance_1.save()
        instance_2 = WorkspaceGroupSharing(group=group, workspace=workspace, access=WorkspaceGroupSharing.READER)
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_cannot_have_duplicated_account_and_group_with_different_access(
        self,
    ):
        """Cannot have the same account in the same group with different access levels twice."""
        group = factories.ManagedGroupFactory()
        workspace = factories.WorkspaceFactory()
        instance_1 = WorkspaceGroupSharing(group=group, workspace=workspace, access=WorkspaceGroupSharing.READER)
        instance_1.save()
        instance_2 = WorkspaceGroupSharing(group=group, workspace=workspace, access=WorkspaceGroupSharing.WRITER)
        with self.assertRaises(IntegrityError):
            instance_2.save()
