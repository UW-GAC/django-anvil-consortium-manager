"""Test forms for the anvil_project_manager app."""

from django.test import TestCase

from .. import forms, models
from . import factories


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

    def test_valid_one_auth_domain(self):
        """Form is valid with necessary input plus one authorization domain."""
        billing_project = factories.BillingProjectFactory.create()
        factories.GroupFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": models.Group.objects.all(),
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_two_auth_domains(self):
        """Form is valid with necessary input plus two authorization domains."""
        billing_project = factories.BillingProjectFactory.create()
        factories.GroupFactory.create_batch(2)
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": models.Group.objects.all(),
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_billing_project(self):
        """Form is invalid when missing a billing project."""
        form_data = {
            "name": "test-workspace",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_missing_name(self):
        """Form is invalid when missing name."""
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_different_class_for_billing_group(self):
        """Form is invalid with a incorrect billing group class."""
        # Create an Group to use as the billing project.
        group = factories.GroupFactory.create()
        form_data = {
            "billing_project": group,
            "name": "test-workspace",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_invalid_name(self):
        """Form is invalid with an invalid name."""
        billing_project = factories.BillingProjectFactory.create()
        form_data = {"billing_project": billing_project, "name": "a bad name"}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_invalid_auth_domain(self):
        """Form is invalid with an incorrect auth domain class."""
        billing_project = factories.BillingProjectFactory.create()
        # Create an Account to use as the authorization domain.
        factories.AccountFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": models.Account.objects.all(),
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("authorization_domains", form.errors)
        self.assertEqual(len(form.errors), 1)


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
