"""Test forms for the anvil_consortium_manager.auditor app."""

from django.core.exceptions import NON_FIELD_ERRORS
from django.test import TestCase

from anvil_consortium_manager.tests.factories import WorkspaceFactory

from .. import forms
from . import factories


class IgnoredManagedGroupMembershipForm(TestCase):
    """Tests for the IgnoredManagedGroupMembershipForm class."""

    form_class = forms.IgnoredManagedGroupMembershipForm

    def setUp(self):
        """Create a group and account for use in tests."""
        self.group = factories.ManagedGroupFactory.create()

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "group": self.group,
            "ignored_email": "test_email@example.com",
            "note": "test note",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_group(self):
        """Form is invalid when missing email."""
        form_data = {
            # "group": self.group,
            "ignored_email": "test_email@example.com",
            "note": "test note",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("group", form.errors)
        self.assertEqual(len(form.errors["group"]), 1)
        self.assertIn("required", form.errors["group"][0])

    def test_invalid_missing_email(self):
        """Form is invalid when missing email."""
        form_data = {
            "group": self.group,
            # "ignored_email": "test_email@example.com",
            "note": "test note",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("ignored_email", form.errors)
        self.assertEqual(len(form.errors["ignored_email"]), 1)
        self.assertIn("required", form.errors["ignored_email"][0])

    def test_invalid_missing_note(self):
        """Form is invalid when missing email."""
        form_data = {
            "group": self.group,
            "ignored_email": "test_email@example.com",
            # "note": "test note",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("note", form.errors)
        self.assertEqual(len(form.errors["note"]), 1)
        self.assertIn("required", form.errors["note"][0])

    def test_invalid_duplicate(self):
        """Form is invalid with a duplicated instance."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create(group=self.group)
        form_data = {
            "group": obj.group,
            "ignored_email": obj.ignored_email,
            "note": "foo",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn(NON_FIELD_ERRORS, form.errors)
        self.assertEqual(len(form.errors[NON_FIELD_ERRORS]), 1)
        self.assertIn("already exists", form.errors[NON_FIELD_ERRORS][0])


class IgnoredWorkspaceSharingFormTest(TestCase):
    """Tests for the IgnoredWorkspaceSharingForm class."""

    form_class = forms.IgnoredWorkspaceSharingForm

    def setUp(self):
        """Create a group and account for use in tests."""
        self.workspace = WorkspaceFactory.create()

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "workspace": self.workspace,
            "ignored_email": "test_email@example.com",
            "note": "test note",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing workspace."""
        form_data = {
            # "workspace": self.workspace,
            "ignored_email": "test_email@example.com",
            "note": "test note",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("required", form.errors["workspace"][0])

    def test_invalid_missing_email(self):
        """Form is invalid when missing email."""
        form_data = {
            "workspace": self.workspace,
            # "ignored_email": "test_email@example.com",
            "note": "test note",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("ignored_email", form.errors)
        self.assertEqual(len(form.errors["ignored_email"]), 1)
        self.assertIn("required", form.errors["ignored_email"][0])

    def test_invalid_missing_note(self):
        """Form is invalid when missing email."""
        form_data = {
            "workspace": self.workspace,
            "ignored_email": "test_email@example.com",
            # "note": "test note",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("note", form.errors)
        self.assertEqual(len(form.errors["note"]), 1)
        self.assertIn("required", form.errors["note"][0])

    def test_invalid_duplicate(self):
        """Form is invalid with a duplicated instance."""
        obj = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        form_data = {
            "workspace": obj.workspace,
            "ignored_email": obj.ignored_email,
            "note": "foo",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn(NON_FIELD_ERRORS, form.errors)
        self.assertEqual(len(form.errors[NON_FIELD_ERRORS]), 1)
        self.assertIn("already exists", form.errors[NON_FIELD_ERRORS][0])
