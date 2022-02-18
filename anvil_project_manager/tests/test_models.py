from django.db.utils import IntegrityError
from django.test import TestCase

from ..models import (
    BillingProject,
    Group,
    GroupMembership,
    Researcher,
    Workspace,
    WorkspaceGroupAccess,
)
from . import factories


class BillingProjectTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = BillingProject(name="my_project")
        instance.save()
        self.assertIsInstance(instance, BillingProject)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = BillingProject(name="my_project")
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
        instance = BillingProject(name=name)
        instance.save()
        instance2 = BillingProject(name=name)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_unique_name_case_insensitive(self):
        """Name uniqueness does not depend on case."""
        instance = BillingProject(name="my_project")
        instance.save()
        instance2 = BillingProject(name="My_PrOjEcT")
        with self.assertRaises(IntegrityError):
            instance2.save()


class ResearcherTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = Researcher(email="email@example.com")
        instance.save()
        self.assertIsInstance(instance, Researcher)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = Researcher(email="email@example.com")
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "email@example.com")

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.ResearcherFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_unique_email(self):
        """Saving a model with a duplicate email fails."""
        email = "email@example.com"
        instance = Researcher(email=email)
        instance.save()
        instance2 = Researcher(email=email)
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_unique_email_case_insensitive(self):
        """Email uniqueness does not depend on case."""
        instance = Researcher(email="email@example.com")
        instance.save()
        instance2 = Researcher(email="EMAIL@example.com")
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


class GroupMembershipTest(TestCase):
    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        researcher = factories.ResearcherFactory.create()
        group = factories.GroupFactory.create()
        instance = GroupMembership(researcher=researcher, group=group)
        self.assertIsInstance(instance, GroupMembership)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        email = "email@example.com"
        group = "test-group"
        researcher = factories.ResearcherFactory(email=email)
        group = factories.GroupFactory(name=group)
        instance = GroupMembership(
            researcher=researcher, group=group, role=GroupMembership.MEMBER
        )
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        expected_string = "{email} as MEMBER in {group}".format(
            email=email, group=group
        )
        self.assertEqual(instance.__str__(), expected_string)

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.GroupMembershipFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_same_researcher_in_two_groups(self):
        """The same researcher can be in two groups."""
        researcher = factories.ResearcherFactory()
        group_1 = factories.GroupFactory(name="group-1")
        group_2 = factories.GroupFactory(name="group-2")
        instance = GroupMembership(researcher=researcher, group=group_1)
        instance.save()
        instance = GroupMembership(researcher=researcher, group=group_2)
        instance.save()

    def test_two_researchers_in_same_group(self):
        """Two researchers can be in the same group."""
        researcher_1 = factories.ResearcherFactory(email="email_1@example.com")
        researcher_2 = factories.ResearcherFactory(email="email_2@example.com")
        group = factories.GroupFactory()
        instance = GroupMembership(researcher=researcher_1, group=group)
        instance.save()
        instance = GroupMembership(researcher=researcher_2, group=group)
        instance.save()

    def test_cannot_have_duplicated_researcher_and_group_with_same_role(self):
        """Cannot have the same researcher in the same group with the same role twice."""
        researcher = factories.ResearcherFactory()
        group = factories.GroupFactory()
        instance_1 = GroupMembership(
            researcher=researcher, group=group, role=GroupMembership.MEMBER
        )
        instance_1.save()
        instance_2 = GroupMembership(
            researcher=researcher, group=group, role=GroupMembership.MEMBER
        )
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_cannot_have_duplicated_researcher_and_group_with_different_role(self):
        """Cannot have the same researcher in the same group with different roles twice."""
        researcher = factories.ResearcherFactory()
        group = factories.GroupFactory()
        instance_1 = GroupMembership(
            researcher=researcher, group=group, role=GroupMembership.MEMBER
        )
        instance_1.save()
        instance_2 = GroupMembership(
            researcher=researcher, group=group, role=GroupMembership.ADMIN
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
        """Two researchers can be in the same group."""
        group_1 = factories.GroupFactory(name="group-1")
        group_2 = factories.GroupFactory(name="group-2")
        workspace = factories.WorkspaceFactory()
        instance = WorkspaceGroupAccess(group=group_1, workspace=workspace)
        instance.save()
        instance = WorkspaceGroupAccess(group=group_2, workspace=workspace)
        instance.save()

    def test_cannot_have_duplicated_researcher_and_group_with_same_access(self):
        """Cannot have the same researcher in the same group with the same access levels twice."""
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

    def test_cannot_have_duplicated_researcher_and_group_with_different_access(
        self,
    ):
        """Cannot have the same researcher in the same group with different access levels twice."""
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
