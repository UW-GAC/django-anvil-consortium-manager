from django.contrib.auth import get_user_model
from django.test import TestCase

from .. import models, tables
from ..adapters.default import DefaultWorkspaceAdapter
from . import factories


class BillingProjectStaffTableTest(TestCase):
    model = models.BillingProject
    model_factory = factories.BillingProjectFactory
    table_class = tables.BillingProjectStaffTable

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


class AccountStaffTableTest(TestCase):
    model = models.Account
    model_factory = factories.AccountFactory
    table_class = tables.AccountStaffTable

    def tearDown(self):
        # One of the testes dynamically sets the get_absolute_url method..
        try:
            del get_user_model().get_absolute_url
        except AttributeError:
            pass

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

    def test_render_user_without_get_absolute_url(self):
        """Table renders the user string method without a link when user does not have get_absolute_url."""
        user = factories.UserFactory.create()
        self.model_factory.create(user=user)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(table.rows[0].get_cell("user"), str(user))

    def test_render_user_with_get_absolute_url(self):
        """Table renders a link to the user profile when the user has a get_absolute_url method."""

        # Dynamically set the get_absolute_url method. This is hacky...
        def foo(self):
            return "test_profile_{}".format(self.username)

        UserModel = get_user_model()
        setattr(UserModel, "get_absolute_url", foo)
        user = UserModel.objects.create(username="testuser", password="testpassword")
        self.model_factory.create(user=user)
        table = self.table_class(self.model.objects.all())
        self.assertIn(str(user), table.rows[0].get_cell("user"))
        self.assertIn("test_profile_testuser", table.rows[0].get_cell("user"))


class ManagedGroupStaffTableTest(TestCase):
    model = models.ManagedGroup
    model_factory = factories.ManagedGroupFactory
    table_class = tables.ManagedGroupStaffTable

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

    def test_number_of_groups_not_managed_by_app(self):
        """Table displays a --- for number of groups if the group is not managed by the app."""
        group = self.model_factory.create(is_managed_by_app=False)
        factories.GroupGroupMembershipFactory.create_batch(2, parent_group=group)
        table = self.table_class(self.model.objects.filter(pk=group.pk))
        self.assertEqual(table.rows[0].get_cell("number_groups"), table.default)

    def test_number_of_accounts_not_managed_by_app(self):
        """Table displays a --- for number of accounts if the group is not managed by the app."""
        group = self.model_factory.create(is_managed_by_app=False)
        factories.GroupAccountMembershipFactory.create_batch(2, group=group)
        table = self.table_class(self.model.objects.filter(pk=group.pk))
        self.assertEqual(table.rows[0].get_cell("number_accounts"), table.default)


class WorkspaceStaffTableTest(TestCase):
    model = models.Workspace
    model_factory = factories.WorkspaceFactory
    table_class = tables.WorkspaceStaffTable

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
        self.model_factory.create(name="a")
        instance_1 = self.model_factory.create(name="b")
        instance_2 = self.model_factory.create(name="c")
        factories.WorkspaceGroupSharingFactory.create_batch(1, workspace=instance_1)
        factories.WorkspaceGroupSharingFactory.create_batch(2, workspace=instance_2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(table.rows[0].get_cell("number_groups"), 0)
        self.assertEqual(table.rows[1].get_cell("number_groups"), 1)
        self.assertEqual(table.rows[2].get_cell("number_groups"), 2)

    def test_workspace_type_display(self):
        """workspace_type field shows the name of the workspace in the adapter."""
        workspace_type = DefaultWorkspaceAdapter().get_type()
        workspace_name = DefaultWorkspaceAdapter().get_name()
        self.model_factory.create(workspace_type=workspace_type)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(table.rows[0].get_cell("workspace_type"), workspace_name)

    def test_order_by(self):
        """table is ordered by workspace name."""
        instance_1 = self.model_factory.create(name="zzz")
        instance_2 = self.model_factory.create(name="aaa")
        table = self.table_class(self.model.objects.all())
        self.assertEqual(table.data[0], instance_2)
        self.assertEqual(table.data[1], instance_1)
        # self.assertEqual(table.rows[0].get_cell("number_groups"), 0)
        # self.assertEqual(table.rows[1].get_cell("number_groups"), 1)
        # self.assertEqual(table.rows[2].get_cell("number_groups"), 2)


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

    def test_row_count_with_inactive_account(self):
        membership = self.model_factory.create()
        membership.account.status = models.Account.INACTIVE_STATUS
        membership.account.save()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)


class WorkspaceGroupSharingTable(TestCase):
    model = models.WorkspaceGroupSharing
    model_factory = factories.WorkspaceGroupSharingFactory
    table_class = tables.WorkspaceGroupSharingTable

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
