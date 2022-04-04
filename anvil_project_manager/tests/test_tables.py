from django.test import TestCase

from .. import models, tables
from . import factories


class BillingProjectTableTest(TestCase):
    model = models.BillingProject
    model_factory = factories.BillingProjectFactory
    table_class = tables.BillingProjectTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)

    def test_number_of_workspaces(self):
        self.model_factory.create()
        billing_project_1 = self.model_factory.create()
        billing_project_2 = self.model_factory.create()
        factories.WorkspaceFactory.create_batch(1, billing_project=billing_project_1)
        factories.WorkspaceFactory.create_batch(2, billing_project=billing_project_2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(table.rows[0].get_cell("number_workspaces"), 0)
        self.assertEqual(table.rows[1].get_cell("number_workspaces"), 1)
        self.assertEqual(table.rows[2].get_cell("number_workspaces"), 2)


class AccountTableTest(TestCase):
    model = models.Account
    model_factory = factories.AccountFactory
    table_class = tables.AccountTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)


class ManagedGroupTableTest(TestCase):
    model = models.ManagedGroup
    model_factory = factories.ManagedGroupFactory
    table_class = tables.ManagedGroupTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)

    def test_number_of_groups(self):
        """The number of child groups displayed is correct."""
        self.model_factory.create()
        instance_1 = self.model_factory.create()
        instance_2 = self.model_factory.create()
        factories.GroupGroupMembershipFactory.create_batch(1, parent_group=instance_1)
        factories.GroupGroupMembershipFactory.create_batch(2, parent_group=instance_2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(table.rows[0].get_cell("number_groups"), 0)
        self.assertEqual(table.rows[1].get_cell("number_groups"), 1)
        self.assertEqual(table.rows[2].get_cell("number_groups"), 2)

    def test_number_of_accounts(self):
        """The number of accounts displayed is correct."""
        self.model_factory.create()
        instance_1 = self.model_factory.create()
        instance_2 = self.model_factory.create()
        factories.GroupAccountMembershipFactory.create_batch(1, group=instance_1)
        factories.GroupAccountMembershipFactory.create_batch(2, group=instance_2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(table.rows[0].get_cell("number_accounts"), 0)
        self.assertEqual(table.rows[1].get_cell("number_accounts"), 1)
        self.assertEqual(table.rows[2].get_cell("number_accounts"), 2)


class WorkspaceTableTest(TestCase):
    model = models.Workspace
    model_factory = factories.WorkspaceFactory
    table_class = tables.WorkspaceTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)

    def test_number_of_groups(self):
        """The number of groups with access displayed is correct."""
        self.model_factory.create()
        instance_1 = self.model_factory.create()
        instance_2 = self.model_factory.create()
        factories.WorkspaceGroupAccessFactory.create_batch(1, workspace=instance_1)
        factories.WorkspaceGroupAccessFactory.create_batch(2, workspace=instance_2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(table.rows[0].get_cell("number_groups"), 0)
        self.assertEqual(table.rows[1].get_cell("number_groups"), 1)
        self.assertEqual(table.rows[2].get_cell("number_groups"), 2)


class GroupGroupMembershipTableTest(TestCase):
    model = models.GroupGroupMembership
    model_factory = factories.GroupGroupMembershipFactory
    table_class = tables.GroupGroupMembershipTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)


class GroupAccountMembershipTableTest(TestCase):
    model = models.GroupAccountMembership
    model_factory = factories.GroupAccountMembershipFactory
    table_class = tables.GroupAccountMembershipTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)


class WorkspaceGroupAccessTable(TestCase):
    model = models.WorkspaceGroupAccess
    model_factory = factories.WorkspaceGroupAccessFactory
    table_class = tables.WorkspaceGroupAccessTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)
