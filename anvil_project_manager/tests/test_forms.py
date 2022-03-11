"""Test forms for the anvil_project_manager app."""

from django.test import TestCase

from .. import forms


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
