from django.db.utils import IntegrityError
from django.test import TestCase

from ..models import Group, GroupMembership, Investigator, Workspace
from . import factories


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

    def test_unique_email(self):
        """Saving a model with a duplicate email fails."""
        email = "email@example.com"
        instance = Investigator(email=email)
        instance.save()
        instance2 = Investigator(email=email)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_unique_email_case_insensitive(self):
        """Email uniqueness does not depend on case."""
        instance = Investigator(email="email@example.com")
        instance.save()
        instance2 = Investigator(email="EMAIL@example.com")
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

    def test_unique_name(self):
        """Saving a model with a duplicate name fails."""
        name = "my_group"
        instance = Group(name=name)
        instance.save()
        instance2 = Group(name=name)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_unique_name_case_insensitive(self):
        """Email uniqueness does not depend on case."""
        instance = Group(name="my_group")
        instance.save()
        instance2 = Group(name="My_GrOuP")
        with self.assertRaises(IntegrityError):
            instance2.save()


class WorkspaceTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = Workspace(namespace="my-namespace", name="my-name")
        instance.save()
        self.assertIsInstance(instance, Workspace)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = Workspace(namespace="my-namespace", name="my-name")
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "my-namespace/my-name")

    def test_can_have_authorization_domain(self):
        """A workspace can have a group as its authorization domain."""
        auth_domain_group = factories.GroupFactory.create()
        instance = Workspace(
            namespace="test-namespace",
            name="test-name",
            authorization_domain=auth_domain_group,
        )
        instance.save()

    def test_cannot_have_duplicated_namespace_and_name(self):
        """Cannot have two workspaces with the same namespace and name."""
        namespace = "test-namespace"
        name = "test-name"
        instance1 = Workspace(namespace=namespace, name=name)
        instance1.save()
        instance2 = Workspace(namespace=namespace, name=name)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_can_have_same_name_in_different_namespace(self):
        """Can have two workspaces with the same name but in different namespaces."""
        name = "test-name"
        instance1 = Workspace(namespace="namespace-1", name=name)
        instance1.save()
        instance2 = Workspace(namespace="namespace-2", name=name)
        instance2.save()

    def test_can_have_same_namespace_with_different_names(self):
        """Can have two workspaces with different names in the same namespace."""
        namespace = "test-namespace"
        instance1 = Workspace(namespace=namespace, name="name-1")
        instance1.save()
        instance2 = Workspace(namespace=namespace, name="name-2")
        instance2.save()


class GroupMembershipTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        investigator = factories.InvestigatorFactory.create()
        group = factories.GroupFactory.create()
        instance = GroupMembership(investigator=investigator, group=group)
        self.assertIsInstance(instance, GroupMembership)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        email = "email@example.com"
        group = "test-group"
        investigator = factories.InvestigatorFactory(email=email)
        group = factories.GroupFactory(name=group)
        instance = GroupMembership(
            investigator=investigator, group=group, role=GroupMembership.MEMBER
        )
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        expected_string = "{email} as MEMBER in {group}".format(
            email=email, group=group
        )
        self.assertEquals(instance.__str__(), expected_string)

    def test_same_investigator_in_two_groups(self):
        """The same investigator can be in two groups."""
        investigator = factories.InvestigatorFactory()
        group_1 = factories.GroupFactory(name="group-1")
        group_2 = factories.GroupFactory(name="group-2")
        instance = GroupMembership(investigator=investigator, group=group_1)
        instance.save()
        instance = GroupMembership(investigator=investigator, group=group_2)
        instance.save()

    def test_two_investigators_in_same_group(self):
        """Two investigators can be in the same group."""
        investigator_1 = factories.InvestigatorFactory(email="email_1@example.com")
        investigator_2 = factories.InvestigatorFactory(email="email_2@example.com")
        group = factories.GroupFactory()
        instance = GroupMembership(investigator=investigator_1, group=group)
        instance.save()
        instance = GroupMembership(investigator=investigator_2, group=group)
        instance.save()

    def test_cannot_have_duplicated_investigator_and_group_with_same_role(self):
        """Cannot have the same investigator in the same group with the same role twice."""
        investigator = factories.InvestigatorFactory()
        group = factories.GroupFactory()
        instance_1 = GroupMembership(
            investigator=investigator, group=group, role=GroupMembership.MEMBER
        )
        instance_1.save()
        instance_2 = GroupMembership(
            investigator=investigator, group=group, role=GroupMembership.MEMBER
        )
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_cannot_have_duplicated_investigator_and_group_with_different_role(self):
        """Cannot have the same investigator in the same group with different roles twice."""
        investigator = factories.InvestigatorFactory()
        group = factories.GroupFactory()
        instance_1 = GroupMembership(
            investigator=investigator, group=group, role=GroupMembership.MEMBER
        )
        instance_1.save()
        instance_2 = GroupMembership(
            investigator=investigator, group=group, role=GroupMembership.ADMIN
        )
        with self.assertRaises(IntegrityError):
            instance_2.save()
