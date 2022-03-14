"""Test forms for the anvil_project_manager app."""

from django.test import TestCase

from .. import forms, models
from . import factories


class WorkspaceImportFormTest(TestCase):
    form_class = forms.WorkspaceImportForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "billing_project_name": "test-billing-project",
            "workspace_name": "test-workspace",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_billing_project(self):
        """Form is invalid when missing billing_project_name."""
        form_data = {"workspace_name": "test-workspace"}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project_name", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing billing_project_name."""
        form_data = {"billing_project_name": "test-billing-project"}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("workspace_name", form.errors)
        self.assertEqual(len(form.errors), 1)


class GroupGroupMembershipFormTest(TestCase):
    form_class = forms.GroupGroupMembershipForm

    def test_valid(self):
        """Form is valid with necessary input."""
        parent = factories.GroupFactory.create(name="parent")
        child = factories.GroupFactory.create(name="child")
        form_data = {
            "parent_group": parent,
            "child_group": child,
            "role": models.GroupGroupMembership.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_parent_group(self):
        """Form is invalid when missing the parent group."""
        child = factories.GroupFactory.create(name="child")
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
        parent = factories.GroupFactory.create(name="parent")
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
        parent = factories.GroupFactory.create(name="parent")
        child = factories.GroupFactory.create(name="child")
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
        parent = factories.GroupFactory.create(name="parent", is_managed_by_app=False)
        child = factories.GroupFactory.create(name="child")
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
        group = factories.GroupFactory.create()
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
        group = factories.GroupFactory.create()
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
        group = factories.GroupFactory.create()
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
        group = factories.GroupFactory.create(is_managed_by_app=False)
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
