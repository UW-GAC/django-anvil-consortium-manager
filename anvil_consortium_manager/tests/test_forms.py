"""Test forms for the anvil_consortium_manager app."""

from django.test import TestCase

from .. import forms, models
from . import factories


class BillingProjectImportFormTest(TestCase):
    """Tests for the AccountImportForm class."""

    form_class = forms.BillingProjectImportForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "name": "foo",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_name(self):
        """Form is invalid when missing name."""
        form_data = {}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors["name"]), 1)
        self.assertIn("required", form.errors["name"][0])

    def test_invalid_duplicate_name(self):
        """Form is invalid with a duplicated name."""
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "name": billing_project.name,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors["name"]), 1)
        self.assertIn("already exists", form.errors["name"][0])

    def test_invalid_duplicate_email_case_insensitive(self):
        """Form is invalid with a duplicated email, regardless of case."""
        factories.BillingProjectFactory.create(name="foo")
        form_data = {
            "name": "FOO",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors["name"]), 1)
        self.assertIn("already exists", form.errors["name"][0])


class AccountImportFormTest(TestCase):
    """Tests for the AccountImportForm class."""

    form_class = forms.AccountImportForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "email": "test_email@example.com",
            "is_service_account": True,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_email(self):
        """Form is invalid when missing email."""
        form_data = {"is_service_account": True}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("email", form.errors)
        self.assertEqual(len(form.errors["email"]), 1)
        self.assertIn("required", form.errors["email"][0])

    def test_valid_missing_is_service_account(self):
        """Form is invalid when missing is_service_account."""
        form_data = {"email": "test_email@example.com"}
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["is_service_account"], False)

    def test_invalid_duplicate_email(self):
        """Form is invalid with a duplicated email."""
        account = factories.AccountFactory.create()
        form_data = {
            "email": account.email,
            "is_service_account": True,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("email", form.errors)
        self.assertEqual(len(form.errors["email"]), 1)
        self.assertIn("already exists", form.errors["email"][0])

    def test_invalid_duplicate_email_case_insensitive(self):
        """Form is invalid with a duplicated email, regardless of case."""
        factories.AccountFactory.create(email="foo@example.com")
        form_data = {
            "email": "FOO@example.com",
            "is_service_account": True,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("email", form.errors)
        self.assertEqual(len(form.errors["email"]), 1)
        self.assertIn("already exists", form.errors["email"][0])


class ManagedGroupCreateFormTest(TestCase):
    """Tests for the ManagedGroupCreateForm class."""

    form_class = forms.ManagedGroupCreateForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "name": "test-group-name",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_name(self):
        """Form is invalid when missing name."""
        form_data = {}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors["name"]), 1)
        self.assertIn("required", form.errors["name"][0])

    def test_invalid_with_invalid_name(self):
        """Form is invalid when name is invalid."""
        form_data = {"name": "test group"}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors["name"]), 1)
        self.assertIn("slug", form.errors["name"][0])

    def test_invalid_duplicate_name(self):
        """Form is invalid with a duplicated name."""
        group = factories.ManagedGroupFactory.create()
        form_data = {
            "name": group.name,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors["name"]), 1)
        self.assertIn("already exists", form.errors["name"][0])

    def test_invalid_duplicate_email_case_insensitive(self):
        """Form is invalid with a duplicated name, regardless of case."""
        factories.ManagedGroupFactory.create(name="test-group")
        form_data = {
            "name": "TEST-GROUP",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors["name"]), 1)
        self.assertIn("already exists", form.errors["name"][0])


class WorkspaceCreateFormTest(TestCase):
    """Tests for the WorkspaceCreateForm class."""

    form_class = forms.WorkspaceCreateForm

    def test_valid(self):
        """Form is valid with necessary input."""
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_billing_project(self):
        """Form is invalid when missing billing_project_name."""
        form_data = {"name": "test-workspace"}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors)
        print(form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing billing_project_name."""
        billing_project = factories.BillingProjectFactory.create()
        form_data = {"billing_project": billing_project}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_valid_with_one_authorization_domain(self):
        billing_project = factories.BillingProjectFactory.create()
        factories.ManagedGroupFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": models.ManagedGroup.objects.all(),
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_with_two_authorization_domains(self):
        billing_project = factories.BillingProjectFactory.create()
        factories.ManagedGroupFactory.create_batch(2)
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": models.ManagedGroup.objects.all(),
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_not_user_of_billing_project(self):
        billing_project = factories.BillingProjectFactory.create(has_app_as_user=False)
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors)
        print(form.errors)
        self.assertEqual(len(form.errors), 1)


class WorkspaceImportFormTest(TestCase):
    form_class = forms.WorkspaceImportForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "workspace": "test-billing-project/test-workspace",
        }
        workspace_choices = [
            ("test-billing-project/test-workspace", 1),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_not_in_choices(self):
        """Form is not valid when the selected workspace isn't one of the available choices."""
        form_data = {
            "workspace": "foo",
        }
        workspace_choices = [
            ("test-billing-project/test-workspace", 1),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_empty_string(self):
        """Form is not valid when an empty string is passed."""
        form_data = {
            "workspace": "",
        }
        workspace_choices = [
            ("test-billing-project/test-workspace", 1),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing billing_project_name."""
        workspace_choices = [
            ("test-billing-project/test-workspace", 1),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data={})
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors), 1)


class GroupGroupMembershipFormTest(TestCase):
    form_class = forms.GroupGroupMembershipForm

    def test_valid(self):
        """Form is valid with necessary input."""
        parent = factories.ManagedGroupFactory.create(name="parent")
        child = factories.ManagedGroupFactory.create(name="child")
        form_data = {
            "parent_group": parent,
            "child_group": child,
            "role": models.GroupGroupMembership.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_parent_group(self):
        """Form is invalid when missing the parent group."""
        child = factories.ManagedGroupFactory.create(name="child")
        form_data = {
            "child_group": child,
            "role": models.GroupGroupMembership.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_missing_child_group(self):
        """Form is invalid when missing the child group."""
        parent = factories.ManagedGroupFactory.create(name="parent")
        form_data = {
            "parent_group": parent,
            "role": models.GroupGroupMembership.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("child_group", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_missing_role(self):
        """Form is invalid when missing the role."""
        parent = factories.ManagedGroupFactory.create(name="parent")
        child = factories.ManagedGroupFactory.create(name="child")
        form_data = {
            "parent_group": parent,
            "child_group": child,
            # "role": models.GroupGroupMembership.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_parent_not_managed(self):
        """Form is invalid when the parent group is not managed by the app."""
        parent = factories.ManagedGroupFactory.create(
            name="parent", is_managed_by_app=False
        )
        child = factories.ManagedGroupFactory.create(name="child")
        form_data = {
            "parent_group": parent,
            "child_group": child,
            "role": models.GroupGroupMembership.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors)
        self.assertEqual(len(form.errors), 1)


class GroupAccountMembershipFormTest(TestCase):
    form_class = forms.GroupAccountMembershipForm

    def test_valid(self):
        """Form is valid with necessary input."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        form_data = {
            "group": group,
            "account": account,
            "role": models.GroupAccountMembership.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_parent_group(self):
        """Form is invalid when missing the group."""
        account = factories.AccountFactory.create()
        form_data = {
            "account": account,
            "role": models.GroupAccountMembership.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_missing_child_group(self):
        """Form is invalid when missing the account."""
        group = factories.ManagedGroupFactory.create()
        form_data = {
            "group": group,
            "role": models.GroupAccountMembership.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("account", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_missing_role(self):
        """Form is invalid when missing the role."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        form_data = {
            "group": group,
            "account": account,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_parent_not_managed(self):
        """Form is invalid when the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        account = factories.AccountFactory.create()
        form_data = {
            "group": group,
            "account": account,
            "role": models.GroupAccountMembership.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_inactive_account(self):
        """Form is invalid when the account is inactive."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create(status=models.Account.INACTIVE_STATUS)
        form_data = {
            "group": group,
            "account": account,
            "role": models.GroupAccountMembership.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("account", form.errors)
        self.assertEqual(len(form.errors["account"]), 1)
        self.assertIn("valid choice", form.errors["account"][0])
        self.assertEqual(len(form.errors), 1)

    def test_account_includes_only_active_accounts(self):
        """Form only displays active accounts."""
        inactive_account = factories.AccountFactory.create(
            status=models.Account.INACTIVE_STATUS
        )
        active_account = factories.AccountFactory.create()
        form = self.form_class()
        self.assertIn(active_account, form.fields["account"].queryset)
        self.assertNotIn(inactive_account, form.fields["account"].queryset)
