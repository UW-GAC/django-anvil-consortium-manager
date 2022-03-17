from unittest import skip

from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.db.utils import IntegrityError
from django.test import TestCase

from ..models import (
    Account,
    BillingProject,
    Group,
    GroupAccountMembership,
    GroupGroupMembership,
    Workspace,
    WorkspaceAuthorizationDomain,
    WorkspaceGroupAccess,
)
from . import factories


class BillingProjectTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = BillingProject(name="my_project", has_app_as_user=True)
        instance.save()
        self.assertIsInstance(instance, BillingProject)

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

    def test_unique_name(self):
        """Saving a model with a duplicate name fails."""
        name = "my_project"
        instance = BillingProject(name=name, has_app_as_user=True)
        instance.save()
        instance2 = BillingProject(name=name, has_app_as_user=False)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_name_validation_case_insensitivity(self):
        """Cannot validate two models with the same case-insensitive name."""
        name = "AbAbA"
        factories.BillingProjectFactory.create(name=name)
        instance = BillingProject(name=name.lower())
        with self.assertRaises(ValidationError):
            instance.full_clean()

    @skip("Add this constraint.")
    def test_name_save_case_insensitivity(self):
        """Cannot save two models with the same case-insensitive name."""
        name = "AbAbA"
        factories.BillingProjectFactory.create(name=name)
        instance = BillingProject(name=name.lower())
        with self.assertRaises(IntegrityError):
            instance.save()


class AccountTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = Account(email="email@example.com", is_service_account=False)
        instance.save()
        self.assertIsInstance(instance, Account)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = Account(email="email@example.com", is_service_account=False)
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "email@example.com")

    def test_email_validation_case_insensitive(self):
        instance = Account(email="email@example.com", is_service_account=False)
        instance.save()
        instance2 = Account(email="EMAIL@example.com", is_service_account=False)
        with self.assertRaises(ValidationError):
            instance2.full_clean()

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

    def test_name_validation_case_insensitivity(self):
        """Cannot validate two models with the same case-insensitive name."""
        name = "AbAbA"
        factories.GroupFactory.create(name=name)
        instance = Group(name=name.lower())
        with self.assertRaises(ValidationError):
            instance.full_clean()

    @skip("Add this constraint.")
    def test_name_save_case_insensitivity(self):
        """Cannot save two models with the same case-insensitive name."""
        name = "AbAbA"
        factories.GroupFactory.create(name=name)
        instance = Group(name=name.lower())
        with self.assertRaises(IntegrityError):
            instance.save()

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.GroupFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_unique_name(self):
        """Saving a model with a duplicate name fails."""
        name = "my_group"
        instance = Group(name=name)
        instance.save()
        instance2 = Group(name=name)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_is_managed_by_app(self):
        """Can set the is_managed_by_app field."""
        instance = Group(name="my-group", is_managed_by_app=True)
        instance.full_clean()
        instance.save()
        instance_2 = Group(name="my-group-2", is_managed_by_app=False)
        instance_2.full_clean()
        instance_2.save()

    def test_get_direct_parents_no_parents(self):
        group = factories.GroupFactory(name="group")
        self.assertEqual(group.get_direct_parents().count(), 0)
        self.assertQuerysetEqual(group.get_direct_parents(), Group.objects.none())

    def test_get_direct_parents_one_parent(self):
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(child.get_direct_parents().count(), 1)
        self.assertQuerysetEqual(
            child.get_direct_parents(), Group.objects.filter(pk=parent.pk)
        )

    def test_get_direct_parents_one_child_two_parents(self):
        parent_1 = factories.GroupFactory(name="parent-group-1")
        parent_2 = factories.GroupFactory(name="parent-group-2")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent_1, child_group=child
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent_2, child_group=child
        )
        self.assertEqual(child.get_direct_parents().count(), 2)
        self.assertQuerysetEqual(
            child.get_direct_parents(),
            Group.objects.filter(pk__in=[parent_1.pk, parent_2.pk]),
            ordered=False,
        )

    def test_get_direct_parents_two_children_one_parent(self):
        parent = factories.GroupFactory(name="parent-group-1")
        child_1 = factories.GroupFactory(name="child-group-1")
        child_2 = factories.GroupFactory(name="child-group-2")
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child_1
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child_2
        )
        self.assertEqual(child_1.get_direct_parents().count(), 1)
        self.assertQuerysetEqual(
            child_1.get_direct_parents(), Group.objects.filter(pk=parent.pk)
        )
        self.assertEqual(child_2.get_direct_parents().count(), 1)
        self.assertQuerysetEqual(
            child_2.get_direct_parents(), Group.objects.filter(pk=parent.pk)
        )

    def test_get_direct_parents_with_other_group(self):
        # Create a relationship not involving the group in question.
        factories.GroupGroupMembershipFactory.create()
        # Create a group not related to any other group.
        group = factories.GroupFactory.create()
        self.assertEqual(group.get_direct_parents().count(), 0)

    def test_get_direct_parents_with_only_child(self):
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(parent.get_direct_parents().count(), 0)

    def test_get_direct_parents_with_grandparent(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(child.get_direct_parents().count(), 1)
        self.assertQuerysetEqual(
            child.get_direct_parents(), Group.objects.filter(pk=parent.pk)
        )

    def test_get_direct_children_no_children(self):
        group = factories.GroupFactory(name="group")
        self.assertEqual(group.get_direct_children().count(), 0)
        self.assertQuerysetEqual(group.get_direct_children(), Group.objects.none())

    def test_get_direct_children_one_child(self):
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(parent.get_direct_children().count(), 1)
        self.assertQuerysetEqual(
            parent.get_direct_children(), Group.objects.filter(pk=child.pk)
        )

    def test_get_direct_children_one_parent_two_children(self):
        child_1 = factories.GroupFactory(name="child-group-1")
        child_2 = factories.GroupFactory(name="child-group-2")
        parent = factories.GroupFactory(name="parent-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child_1
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child_2
        )
        self.assertEqual(parent.get_direct_children().count(), 2)
        self.assertQuerysetEqual(
            parent.get_direct_children(),
            Group.objects.filter(pk__in=[child_1.pk, child_2.pk]),
            ordered=False,
        )

    def test_get_direct_parents_two_parents_one_child(self):
        child = factories.GroupFactory(name="child-group-1")
        parent_1 = factories.GroupFactory(name="parent-group-1")
        parent_2 = factories.GroupFactory(name="parent-group-2")
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent_1, child_group=child
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent_2, child_group=child
        )
        self.assertEqual(parent_1.get_direct_children().count(), 1)
        self.assertQuerysetEqual(
            parent_1.get_direct_children(), Group.objects.filter(pk=child.pk)
        )
        self.assertEqual(parent_2.get_direct_children().count(), 1)
        self.assertQuerysetEqual(
            parent_2.get_direct_children(), Group.objects.filter(pk=child.pk)
        )

    def test_get_direct_children_with_other_group(self):
        # Create a relationship not involving the group in question.
        factories.GroupGroupMembershipFactory.create()
        # Create a group not related to any other group.
        group = factories.GroupFactory.create()
        self.assertEqual(group.get_direct_children().count(), 0)

    def test_get_direct_children_with_only_parent(self):
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(child.get_direct_children().count(), 0)

    def test_get_direct_children_with_grandchildren(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(grandparent.get_direct_children().count(), 1)
        self.assertQuerysetEqual(
            grandparent.get_direct_children(), Group.objects.filter(pk=parent.pk)
        )

    def test_get_all_parents_no_parents(self):
        group = factories.GroupFactory(name="group")
        self.assertEqual(group.get_all_parents().count(), 0)
        self.assertQuerysetEqual(group.get_all_parents(), Group.objects.none())

    def test_get_all_parents_one_parent(self):
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(child.get_all_parents().count(), 1)
        self.assertQuerysetEqual(
            child.get_all_parents(), Group.objects.filter(pk=parent.pk)
        )

    def test_get_all_parents_one_grandparent(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(child.get_all_parents().count(), 2)
        self.assertQuerysetEqual(
            child.get_all_parents(),
            Group.objects.filter(pk__in=[grandparent.pk, parent.pk]),
            ordered=False,
        )

    def test_get_all_parents_two_grandparents_same_parent(self):
        grandparent_1 = factories.GroupFactory(name="grandparent-group-1")
        grandparent_2 = factories.GroupFactory(name="grandparent-group-2")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent_1, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent_2, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(child.get_all_parents().count(), 3)
        self.assertQuerysetEqual(
            child.get_all_parents(),
            Group.objects.filter(
                pk__in=[grandparent_1.pk, grandparent_2.pk, parent.pk]
            ),
            ordered=False,
        )

    def test_get_all_parents_two_grandparents_two_parents(self):
        grandparent_1 = factories.GroupFactory(name="grandparent-group-1")
        grandparent_2 = factories.GroupFactory(name="grandparent-group-2")
        parent_1 = factories.GroupFactory(name="parent-group-1")
        parent_2 = factories.GroupFactory(name="parent-group-2")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent_1, child_group=parent_1
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent_2, child_group=parent_2
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent_1, child_group=child
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent_2, child_group=child
        )
        self.assertEqual(child.get_all_parents().count(), 4)
        self.assertQuerysetEqual(
            child.get_all_parents(),
            Group.objects.filter(
                pk__in=[grandparent_1.pk, grandparent_2.pk, parent_1.pk, parent_2.pk]
            ),
            ordered=False,
        )

    def test_get_all_parents_multiple_paths_to_same_group(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        # Then create a grandparent-child direct relationship.
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=child
        )
        self.assertEqual(child.get_all_parents().count(), 2)
        self.assertQuerysetEqual(
            child.get_all_parents(),
            Group.objects.filter(pk__in=[grandparent.pk, parent.pk]),
            ordered=False,
        )

    def test_all_parents_greatgrandparent(self):
        greatgrandparent = factories.GroupFactory(name="greatgrandparent-group")
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(
            parent_group=greatgrandparent, child_group=grandparent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(child.get_all_parents().count(), 3)
        self.assertQuerysetEqual(
            child.get_all_parents(),
            Group.objects.filter(
                pk__in=[greatgrandparent.pk, grandparent.pk, parent.pk]
            ),
            ordered=False,
        )

    def test_get_all_parents_with_other_group(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        # Create a group with no relationships
        group = factories.GroupFactory.create(name="other-group")
        self.assertEqual(group.get_all_parents().count(), 0)

    def test_get_all_children_no_children(self):
        group = factories.GroupFactory(name="group")
        self.assertEqual(group.get_all_children().count(), 0)
        self.assertQuerysetEqual(group.get_all_children(), Group.objects.none())

    def test_get_all_children_one_child(self):
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(parent.get_all_children().count(), 1)
        self.assertQuerysetEqual(
            parent.get_all_children(), Group.objects.filter(pk=child.pk)
        )

    def test_get_all_children_one_grandchild(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(grandparent.get_all_children().count(), 2)
        self.assertQuerysetEqual(
            grandparent.get_all_children(),
            Group.objects.filter(pk__in=[parent.pk, child.pk]),
            ordered=False,
        )

    def test_get_all_children_two_grandchildren_same_parent(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child_1 = factories.GroupFactory(name="child-group-1")
        child_2 = factories.GroupFactory(name="child-group-2")
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child_1
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child_2
        )
        self.assertEqual(grandparent.get_all_children().count(), 3)
        self.assertQuerysetEqual(
            grandparent.get_all_children(),
            Group.objects.filter(pk__in=[parent.pk, child_1.pk, child_2.pk]),
            ordered=False,
        )

    def test_get_all_children_two_grandchildren_two_parents(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent_1 = factories.GroupFactory(name="parent-group-1")
        parent_2 = factories.GroupFactory(name="parent-group-2")
        child_1 = factories.GroupFactory(name="child-group-1")
        child_2 = factories.GroupFactory(name="child-group-2")
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent_1
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent_2
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent_1, child_group=child_1
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent_2, child_group=child_2
        )
        self.assertEqual(grandparent.get_all_children().count(), 4)
        self.assertQuerysetEqual(
            grandparent.get_all_children(),
            Group.objects.filter(
                pk__in=[parent_1.pk, parent_2.pk, child_1.pk, child_2.pk]
            ),
            ordered=False,
        )

    def test_get_all_children_multiple_paths_to_same_group(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        # Then create a grandparent-child direct relationship.
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=child
        )
        self.assertEqual(grandparent.get_all_children().count(), 2)
        self.assertQuerysetEqual(
            grandparent.get_all_children(),
            Group.objects.filter(pk__in=[parent.pk, child.pk]),
            ordered=False,
        )

    def test_all_children_greatgrandparent(self):
        greatgrandparent = factories.GroupFactory(name="greatgrandparent-group")
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(
            parent_group=greatgrandparent, child_group=grandparent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        self.assertEqual(greatgrandparent.get_all_children().count(), 3)
        self.assertQuerysetEqual(
            greatgrandparent.get_all_children(),
            Group.objects.filter(pk__in=[grandparent.pk, parent.pk, child.pk]),
            ordered=False,
        )

    def test_get_all_children_with_other_group(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        # Create the standard grandparent-parent-child relationship
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        # Create a group with no relationships
        group = factories.GroupFactory.create(name="other-group")
        self.assertEqual(group.get_all_children().count(), 0)

    def test_cannot_delete_group_used_as_auth_domain(self):
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        workspace.authorization_domains.add(group)
        with self.assertRaises(ProtectedError):
            group.delete()
        self.assertEqual(len(Group.objects.all()), 1)
        self.assertIn(group, Group.objects.all())


class WorkspaceTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        billing_project = factories.BillingProjectFactory.create()
        instance = Workspace(billing_project=billing_project, name="my-name")
        instance.save()
        self.assertIsInstance(instance, Workspace)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        billing_project = factories.BillingProjectFactory.create(name="my-project")
        instance = Workspace(billing_project=billing_project, name="my-name")
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "my-project/my-name")

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.WorkspaceFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_name_validation_case_insensitivity(self):
        """Cannot validate two models with the same case-insensitive name in the same billing project."""
        billing_project = factories.BillingProjectFactory.create()
        name = "AbAbA"
        factories.WorkspaceFactory.create(billing_project=billing_project, name=name)
        instance = Workspace(billing_project=billing_project, name=name.lower())
        with self.assertRaises(ValidationError):
            instance.full_clean()

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
        billing_project_1 = factories.BillingProjectFactory.create(
            name="test-project-1"
        )
        billing_project_2 = factories.BillingProjectFactory.create(
            name="test-project-2"
        )
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

    def test_one_auth_domain(self):
        """Can create a workspace with one authorization domain."""
        auth_domain = factories.GroupFactory.create()
        billing_project = factories.BillingProjectFactory.create(name="test-project")
        instance = Workspace(billing_project=billing_project, name="test-name")
        instance.save()
        instance.authorization_domains.set(Group.objects.all())
        self.assertEqual(len(instance.authorization_domains.all()), 1)
        self.assertIn(auth_domain, instance.authorization_domains.all())

    def test_two_auth_domains(self):
        """Can create a workspace with two authorization domains."""
        auth_domain_1 = factories.GroupFactory.create()
        auth_domain_2 = factories.GroupFactory.create()
        billing_project = factories.BillingProjectFactory.create(name="test-project")
        instance = Workspace(billing_project=billing_project, name="test-name")
        instance.save()
        instance.authorization_domains.set(Group.objects.all())
        self.assertEqual(len(instance.authorization_domains.all()), 2)
        self.assertIn(auth_domain_1, instance.authorization_domains.all())
        self.assertIn(auth_domain_2, instance.authorization_domains.all())

    def test_auth_domain_unique(self):
        """Adding the same auth domain twice does nothing."""
        auth_domain = factories.GroupFactory.create()
        billing_project = factories.BillingProjectFactory.create(name="test-project")
        instance = Workspace(billing_project=billing_project, name="test-name")
        instance.save()
        instance.authorization_domains.add(auth_domain)
        instance.authorization_domains.add(auth_domain)
        self.assertEqual(len(instance.authorization_domains.all()), 1)
        self.assertIn(auth_domain, instance.authorization_domains.all())
        print(instance.authorization_domains.all())

    def test_can_delete_workspace_with_auth_domain(self):
        auth_domain = factories.GroupFactory.create()
        billing_project = factories.BillingProjectFactory.create(name="test-project")
        instance = Workspace(billing_project=billing_project, name="test-name")
        instance.save()
        instance.authorization_domains.add(auth_domain)
        instance.save()
        # Now try to delete it.
        instance.refresh_from_db()
        instance.delete()
        self.assertEqual(len(Workspace.objects.all()), 0)
        self.assertEqual(len(WorkspaceAuthorizationDomain.objects.all()), 0)
        # The group has not been deleted.
        self.assertIn(auth_domain, Group.objects.all())


class WorkspaceAuthorizationDomainTestCase(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.GroupFactory.create()
        instance = WorkspaceAuthorizationDomain(workspace=workspace, group=group)
        instance.save()
        self.assertIsInstance(instance, WorkspaceAuthorizationDomain)

    def test_str_method(self):
        """Creation using the model constructor and .save() works."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.GroupFactory.create()
        instance = WorkspaceAuthorizationDomain(workspace=workspace, group=group)
        instance.save()
        self.assertIsInstance(instance.__str__(), str)


class GroupGroupMembershipTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        parent_group = factories.GroupFactory.create(name="parent")
        child_group = factories.GroupFactory.create(name="child")
        instance = GroupGroupMembership(
            parent_group=parent_group, child_group=child_group
        )
        self.assertIsInstance(instance, GroupGroupMembership)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        parent_group = factories.GroupFactory.create(name="parent")
        child_group = factories.GroupFactory.create(name="child")
        instance = GroupGroupMembership(
            parent_group=parent_group, child_group=child_group
        )
        self.assertIsInstance(instance.__str__(), str)
        expected_string = "child as MEMBER in parent"
        self.assertEqual(instance.__str__(), expected_string)

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.GroupGroupMembershipFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_same_group_with_two_parent_groups(self):
        """The same group can be a child in two groups."""
        child_group = factories.GroupFactory(name="child")
        group_1 = factories.GroupFactory(name="parent-1")
        group_2 = factories.GroupFactory(name="parent-2")
        instance = GroupGroupMembership(parent_group=group_1, child_group=child_group)
        instance.save()
        instance = GroupGroupMembership(parent_group=group_2, child_group=child_group)
        instance.save()
        self.assertEqual(GroupGroupMembership.objects.count(), 2)

    def test_two_groups_in_same_parent_group(self):
        """Two accounts can be in the same group."""
        child_1 = factories.GroupFactory(name="child-1")
        child_2 = factories.GroupFactory(name="child-2")
        parent = factories.GroupFactory(name="parent")
        instance = GroupGroupMembership(parent_group=parent, child_group=child_1)
        instance.save()
        instance = GroupGroupMembership(parent_group=parent, child_group=child_2)
        instance.save()
        self.assertEqual(GroupGroupMembership.objects.count(), 2)

    def test_cannot_have_duplicated_parent_and_child_with_same_role(self):
        """Cannot have the same child in the same group with the same role twice."""
        child_group = factories.GroupFactory()
        parent_group = factories.GroupFactory()
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
        child_group = factories.GroupFactory()
        parent_group = factories.GroupFactory()
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
        group = factories.GroupFactory()
        instance = GroupGroupMembership(
            parent_group=group, child_group=group, role=GroupGroupMembership.MEMBER
        )
        with self.assertRaises(ValidationError):
            instance.clean()

    def test_cant_add_a_group_to_itself_admin(self):
        group = factories.GroupFactory()
        instance = GroupGroupMembership(
            parent_group=group, child_group=group, role=GroupGroupMembership.ADMIN
        )
        with self.assertRaisesRegex(ValidationError, "add a group to itself"):
            instance.clean()

    def test_circular_cant_add_parent_group_as_a_child(self):
        obj = factories.GroupGroupMembershipFactory.create(
            role=GroupGroupMembership.MEMBER
        )
        instance = GroupGroupMembership(
            parent_group=obj.child_group,
            child_group=obj.parent_group,
            role=GroupGroupMembership.MEMBER,
        )
        with self.assertRaisesRegex(ValidationError, "circular"):
            instance.clean()

    def test_circular_cant_add_grandparent_group_as_a_grandchild(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        instance = GroupGroupMembership(
            parent_group=child,
            child_group=grandparent,
            role=GroupGroupMembership.MEMBER,
        )
        with self.assertRaisesRegex(ValidationError, "circular"):
            instance.clean()

    def test_circular_multiple_paths(self):
        grandparent = factories.GroupFactory(name="grandparent-group")
        parent = factories.GroupFactory(name="parent-group")
        child = factories.GroupFactory(name="child-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        # Also create a grandparent-child relationship.
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=child
        )
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
        group = factories.GroupFactory.create()
        instance = GroupAccountMembership(account=account, group=group)
        self.assertIsInstance(instance, GroupAccountMembership)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        email = "email@example.com"
        group = "test-group"
        account = factories.AccountFactory(email=email)
        group = factories.GroupFactory(name=group)
        instance = GroupAccountMembership(
            account=account, group=group, role=GroupAccountMembership.MEMBER
        )
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        expected_string = "{email} as MEMBER in {group}".format(
            email=email, group=group
        )
        self.assertEqual(instance.__str__(), expected_string)

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.GroupAccountMembershipFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_same_account_in_two_groups(self):
        """The same account can be in two groups."""
        account = factories.AccountFactory()
        group_1 = factories.GroupFactory(name="group-1")
        group_2 = factories.GroupFactory(name="group-2")
        instance = GroupAccountMembership(account=account, group=group_1)
        instance.save()
        instance = GroupAccountMembership(account=account, group=group_2)
        instance.save()

    def test_two_accounts_in_same_group(self):
        """Two accounts can be in the same group."""
        account_1 = factories.AccountFactory(email="email_1@example.com")
        account_2 = factories.AccountFactory(email="email_2@example.com")
        group = factories.GroupFactory()
        instance = GroupAccountMembership(account=account_1, group=group)
        instance.save()
        instance = GroupAccountMembership(account=account_2, group=group)
        instance.save()

    def test_cannot_have_duplicated_account_and_group_with_same_role(self):
        """Cannot have the same account in the same group with the same role twice."""
        account = factories.AccountFactory()
        group = factories.GroupFactory()
        instance_1 = GroupAccountMembership(
            account=account, group=group, role=GroupAccountMembership.MEMBER
        )
        instance_1.save()
        instance_2 = GroupAccountMembership(
            account=account, group=group, role=GroupAccountMembership.MEMBER
        )
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_cannot_have_duplicated_account_and_group_with_different_role(self):
        """Cannot have the same account in the same group with different roles twice."""
        account = factories.AccountFactory()
        group = factories.GroupFactory()
        instance_1 = GroupAccountMembership(
            account=account, group=group, role=GroupAccountMembership.MEMBER
        )
        instance_1.save()
        instance_2 = GroupAccountMembership(
            account=account, group=group, role=GroupAccountMembership.ADMIN
        )
        with self.assertRaises(IntegrityError):
            instance_2.save()


class WorkspaceGroupAccessTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        instance = WorkspaceGroupAccess(
            group=group, workspace=workspace, access=WorkspaceGroupAccess.READER
        )
        self.assertIsInstance(instance, WorkspaceGroupAccess)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        billing_project_name = "test-namespace"
        workspace_name = "test-workspace"
        group_name = "test-group"
        billing_project = factories.BillingProjectFactory(name=billing_project_name)
        group = factories.GroupFactory(name=group_name)
        workspace = factories.WorkspaceFactory(
            billing_project=billing_project, name=workspace_name
        )
        instance = WorkspaceGroupAccess(
            group=group, workspace=workspace, access=WorkspaceGroupAccess.READER
        )
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        expected_string = "test-group with READER to test-namespace/test-workspace"
        self.assertEqual(instance.__str__(), expected_string)

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.WorkspaceGroupAccessFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_same_group_in_two_workspaces(self):
        """The same group can have access to two workspaces."""
        group = factories.GroupFactory()
        workspace_1 = factories.WorkspaceFactory(name="workspace-1")
        workspace_2 = factories.WorkspaceFactory(name="workspace-2")
        instance = WorkspaceGroupAccess(group=group, workspace=workspace_1)
        instance.save()
        instance = WorkspaceGroupAccess(group=group, workspace=workspace_2)
        instance.save()

    def test_two_groups_and_same_workspace(self):
        """Two accounts can be in the same group."""
        group_1 = factories.GroupFactory(name="group-1")
        group_2 = factories.GroupFactory(name="group-2")
        workspace = factories.WorkspaceFactory()
        instance = WorkspaceGroupAccess(group=group_1, workspace=workspace)
        instance.save()
        instance = WorkspaceGroupAccess(group=group_2, workspace=workspace)
        instance.save()

    def test_cannot_have_duplicated_account_and_group_with_same_access(self):
        """Cannot have the same account in the same group with the same access levels twice."""
        group = factories.GroupFactory()
        workspace = factories.WorkspaceFactory()
        instance_1 = WorkspaceGroupAccess(
            group=group, workspace=workspace, access=WorkspaceGroupAccess.READER
        )
        instance_1.save()
        instance_2 = WorkspaceGroupAccess(
            group=group, workspace=workspace, access=WorkspaceGroupAccess.READER
        )
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_cannot_have_duplicated_account_and_group_with_different_access(
        self,
    ):
        """Cannot have the same account in the same group with different access levels twice."""
        group = factories.GroupFactory()
        workspace = factories.WorkspaceFactory()
        instance_1 = WorkspaceGroupAccess(
            group=group, workspace=workspace, access=WorkspaceGroupAccess.READER
        )
        instance_1.save()
        instance_2 = WorkspaceGroupAccess(
            group=group, workspace=workspace, access=WorkspaceGroupAccess.WRITER
        )
        with self.assertRaises(IntegrityError):
            instance_2.save()
