"""Test forms for the anvil_consortium_manager app."""

from django.core.exceptions import NON_FIELD_ERRORS
from django.test import TestCase

from .. import forms, models
from . import factories


class BillingProjectImportFormTest(TestCase):
    """Tests for the AccountImportForm class."""

    form_class = forms.BillingProjectImportForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "name": "test-billing",
        }
        billing_project_choices = [("test-billing", "test-billing")]
        form = self.form_class(billing_project_choices=billing_project_choices, data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_note(self):
        """Form is valid with the note field."""
        form_data = {"name": "test-billing", "note": "test note"}
        billing_project_choices = [("test-billing", "test-billing")]
        form = self.form_class(billing_project_choices=billing_project_choices, data=form_data)
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

    def test_invalid_name_choice(self):
        """Form is invalid with a name not in choices."""
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "name": billing_project.name,
        }
        billing_project_choices = [("test-billing", "test-billing")]
        form = self.form_class(billing_project_choices=billing_project_choices, data=form_data)

        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors["name"]), 1)
        self.assertIn("not one of the available choices", form.errors["name"][0])

    def test_duplicate_name_choice_case_insensitive(self):
        """Form is invalid with a case insensitive name that already exists."""
        factories.BillingProjectFactory.create(name="TEST-BILLING")
        form_data = {
            "name": "test-billing",
        }
        billing_project_choices = [("test-billing", "test-billing")]
        form = self.form_class(billing_project_choices=billing_project_choices, data=form_data)

        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("name", form.errors)
        self.assertEqual(len(form.errors["name"]), 1)
        self.assertIn("BillingProject with this Name already exists", form.errors["name"][0])


class BillingProjectUpdateFormTest(TestCase):
    """Tests for the BillingProjectUpdateForm class."""

    form_class = forms.BillingProjectUpdateForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {}
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_note(self):
        """Form is valid with the note field."""
        form_data = {"note": "test note"}
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())


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

    def test_valid_with_note(self):
        """Form is valid with necessary input."""
        form_data = {
            "email": "test_email@example.com",
            "is_service_account": True,
            "note": "test note",
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


class AccountUpdateFormTest(TestCase):
    """Tests for the AccountUpdateForm class."""

    form_class = forms.AccountUpdateForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {}
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_note(self):
        """Form is valid with the note field."""
        form_data = {"note": "test note"}
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())


class UserEmailEntryFormTest(TestCase):
    """Tests for the UserEmailEntryForm class."""

    form_class = forms.UserEmailEntryForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "email": "test_email@example.com",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_invalid_email(self):
        """Form is invalid when an invalid email is entered."""
        form_data = {"email": "foo"}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("email", form.errors)
        self.assertEqual(len(form.errors["email"]), 1)
        self.assertIn("valid email", form.errors["email"][0])

    def test_invalid_missing_email(self):
        """Form is invalid when missing email."""
        form_data = {}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("email", form.errors)
        self.assertEqual(len(form.errors["email"]), 1)
        self.assertIn("required", form.errors["email"][0])

    def test_service_account_email(self):
        """Raises ValidationError if a service account email is entered."""
        form_data = {
            "email": "test_email@TEST.iam.gserviceaccount.com",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("email", form.errors)
        self.assertEqual(len(form.errors["email"]), 1)
        self.assertIn("service account", form.errors["email"][0])


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

    def test_valid_with_note(self):
        """Form is valid with necessary input and note is specified."""
        form_data = {
            "name": "test-group-name",
            "note": "test note",
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


class ManagedGroupUpdateFormTest(TestCase):
    """Tests for the ManagedGroupUpdateForm class."""

    form_class = forms.ManagedGroupUpdateForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {}
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_note(self):
        """Form is valid with the note field."""
        form_data = {"note": "test note"}
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())


class WorkspaceFormTest(TestCase):
    """Tests for the WorkspaceForm class."""

    form_class = forms.WorkspaceForm

    def test_valid(self):
        """Form is valid with necessary input."""
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_with_note(self):
        """Form is valid with necessary input and note is specified."""
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "note": "test note",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_billing_project(self):
        """Form is invalid when missing billing_project_name."""
        form_data = {"name": "test-workspace"}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors)
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
        self.assertEqual(len(form.errors), 1)
        self.assertIn("billing_project", form.errors)
        self.assertEqual(len(form.errors["billing_project"]), 1)
        self.assertIn("has_app_as_user", form.errors["billing_project"][0])

    def test_invalid_case_insensitive_duplicate(self):
        """Cannot validate with the same case-insensitive name in the same billing project as an existing workspace."""
        billing_project = factories.BillingProjectFactory.create()
        name = "AbAbA"
        factories.WorkspaceFactory.create(billing_project=billing_project, name=name)
        form_data = {"billing_project": billing_project, "name": name.lower()}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn(NON_FIELD_ERRORS, form.errors)
        self.assertEqual(len(form.errors[NON_FIELD_ERRORS]), 1)
        self.assertIn("already exists", form.errors[NON_FIELD_ERRORS][0])


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

    def test_valid_with_note(self):
        """Form is valid with necessary input and note is specified."""
        form_data = {
            "workspace": "test-billing-project/test-workspace",
            "note": "test note",
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


class WorkspaceCloneFormMixinTest(TestCase):
    """Tests for the WorkspaceCloneFormMixin."""

    def setUp(self):
        """Create a workspace to clone for use in tests."""
        self.workspace_to_clone = factories.WorkspaceFactory.create()

    def get_form_class(self):
        """Create a subclass using the mixin."""

        class TestForm(forms.WorkspaceCloneFormMixin, forms.WorkspaceForm):
            class Meta(forms.WorkspaceForm.Meta):
                pass

        return TestForm

    def test_valid_no_required_auth_domains(self):
        """Form is valid with a workspace to clone with no auth domains, and no auth domains selected."""
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_no_required_auth_domains_with_one_selected_auth_domain(self):
        """Form is valid with a workspace to clone with no auth domains, and one auth domain selected."""
        billing_project = factories.BillingProjectFactory.create()
        new_auth_domain = factories.ManagedGroupFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [new_auth_domain],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_no_required_auth_domains_with_two_selected_auth_domains(self):
        """Form is valid with a workspace to clone with no auth domains, and two auth domains selected."""
        billing_project = factories.BillingProjectFactory.create()
        new_auth_domain_1 = factories.ManagedGroupFactory.create()
        new_auth_domain_2 = factories.ManagedGroupFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [new_auth_domain_1, new_auth_domain_2],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_one_required_auth_domains(self):
        """Form is valid with a workspace to clone with one auth domain, and that auth domain selected."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.workspace_to_clone.authorization_domains.add(auth_domain)
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [auth_domain],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_one_required_auth_domains_no_auth_domains_selected(self):
        """Form is not valid when no auth domains are selected but workspace to clone has one auth domain."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.workspace_to_clone.authorization_domains.add(auth_domain)
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("authorization_domains", form.errors)
        self.assertEqual(len(form.errors["authorization_domains"]), 1)
        self.assertIn(
            "contain all original workspace authorization domains",
            form.errors["authorization_domains"][0],
        )
        self.assertIn(auth_domain.name, form.errors["authorization_domains"][0])

    def test_invalid_one_required_auth_domains_different_auth_domains_selected(self):
        """Form is not valid when no auth domains are selected but workspace to clone has one auth domain."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.workspace_to_clone.authorization_domains.add(auth_domain)
        billing_project = factories.BillingProjectFactory.create()
        other_auth_domain = factories.ManagedGroupFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [other_auth_domain],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("authorization_domains", form.errors)
        self.assertEqual(len(form.errors["authorization_domains"]), 1)
        self.assertIn(
            "contain all original workspace authorization domains",
            form.errors["authorization_domains"][0],
        )
        self.assertIn(auth_domain.name, form.errors["authorization_domains"][0])

    def test_valid_one_required_auth_domains_with_extra_selected_auth_domain(self):
        """Form is valid with a workspace to clone with one auth domains, and an extra auth domain selected."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.workspace_to_clone.authorization_domains.add(auth_domain)
        billing_project = factories.BillingProjectFactory.create()
        new_auth_domain = factories.ManagedGroupFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [auth_domain, new_auth_domain],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_two_required_auth_domains(self):
        """Form is valid with a workspace to clone with two auth domains, and both auth domains selected."""
        auth_domain_1 = factories.ManagedGroupFactory.create()
        auth_domain_2 = factories.ManagedGroupFactory.create()
        self.workspace_to_clone.authorization_domains.add(auth_domain_1, auth_domain_2)
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [auth_domain_1, auth_domain_2],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_two_required_auth_domains_no_auth_domains_selected(self):
        """Form is not valid when no auth domains are selected but workspace to clone has two auth domain."""
        auth_domain_1 = factories.ManagedGroupFactory.create()
        auth_domain_2 = factories.ManagedGroupFactory.create()
        self.workspace_to_clone.authorization_domains.add(auth_domain_1, auth_domain_2)
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("authorization_domains", form.errors)
        self.assertEqual(len(form.errors["authorization_domains"]), 1)
        self.assertIn(
            "contain all original workspace authorization domains",
            form.errors["authorization_domains"][0],
        )
        self.assertIn(auth_domain_1.name, form.errors["authorization_domains"][0])
        self.assertIn(auth_domain_2.name, form.errors["authorization_domains"][0])

    def test_invalid_two_required_auth_domains_one_auth_domain_selected(self):
        """Form is not valid when no auth domains are selected but workspace to clone has two auth domain."""
        auth_domain_1 = factories.ManagedGroupFactory.create()
        auth_domain_2 = factories.ManagedGroupFactory.create()
        self.workspace_to_clone.authorization_domains.add(auth_domain_1, auth_domain_2)
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [auth_domain_1],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("authorization_domains", form.errors)
        self.assertEqual(len(form.errors["authorization_domains"]), 1)
        self.assertIn(
            "contain all original workspace authorization domains",
            form.errors["authorization_domains"][0],
        )
        self.assertIn(auth_domain_1.name, form.errors["authorization_domains"][0])
        self.assertIn(auth_domain_2.name, form.errors["authorization_domains"][0])

    def test_invalid_two_required_auth_domains_different_auth_domains_selected(self):
        """Form is not valid when different auth domains are selected but workspace to clone has two auth domains."""
        auth_domain_1 = factories.ManagedGroupFactory.create()
        auth_domain_2 = factories.ManagedGroupFactory.create()
        self.workspace_to_clone.authorization_domains.add(auth_domain_1, auth_domain_2)
        billing_project = factories.BillingProjectFactory.create()
        other_auth_domain_1 = factories.ManagedGroupFactory.create()
        other_auth_domain_2 = factories.ManagedGroupFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [other_auth_domain_1, other_auth_domain_2],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("authorization_domains", form.errors)
        self.assertEqual(len(form.errors["authorization_domains"]), 1)
        self.assertIn(
            "contain all original workspace authorization domains",
            form.errors["authorization_domains"][0],
        )
        self.assertIn(auth_domain_1.name, form.errors["authorization_domains"][0])
        self.assertIn(auth_domain_2.name, form.errors["authorization_domains"][0])

    def test_valid_two_required_auth_domains_with_extra_selected_auth_domain(self):
        """Form is valid with a workspace to clone with one auth domains, and an extra auth domain selected."""
        auth_domain_1 = factories.ManagedGroupFactory.create()
        auth_domain_2 = factories.ManagedGroupFactory.create()
        self.workspace_to_clone.authorization_domains.add(auth_domain_1, auth_domain_2)
        billing_project = factories.BillingProjectFactory.create()
        new_auth_domain = factories.ManagedGroupFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [auth_domain_1, auth_domain_2, new_auth_domain],
        }
        form = self.get_form_class()(self.workspace_to_clone, data=form_data)
        self.assertTrue(form.is_valid())

    def test_custom_workspace_form_with_clean_auth_domain_error_in_custom_form(self):
        # Create a test workspace form with a custom clean_authorization_domains method.
        class TestWorkspaceForm(forms.WorkspaceForm):
            class Meta:
                model = models.Workspace
                fields = ("billing_project", "name", "authorization_domains")

            def clean_authorization_domains(self):
                # No return statement because the test never gets there, and it breaks coverage.
                authorization_domains = self.cleaned_data.get("authorization_domains")
                if authorization_domains:
                    for auth_domain in authorization_domains:
                        if auth_domain.name == "invalid-name":
                            raise forms.ValidationError("Test error")

        class TestWorkspaceCloneForm(forms.WorkspaceCloneFormMixin, TestWorkspaceForm):
            class Meta(TestWorkspaceForm.Meta):
                pass

        auth_domain = factories.ManagedGroupFactory.create(name="invalid-name")
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [auth_domain],
        }
        form = TestWorkspaceCloneForm(self.workspace_to_clone, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("authorization_domains", form.errors)
        self.assertEqual(len(form.errors["authorization_domains"]), 1)
        self.assertIn(
            "Test error",
            form.errors["authorization_domains"][0],
        )

    def test_custom_workspace_form_with_clean_auth_domain_error_in_mixin(self):
        # Create a test workspace form with a custom clean_authorization_domains method.
        class TestWorkspaceForm(forms.WorkspaceForm):
            class Meta:
                model = models.Workspace
                fields = ("billing_project", "name", "authorization_domains")

            def clean_authorization_domains(self):
                authorization_domains = self.cleaned_data.get("authorization_domains")
                return authorization_domains

        class TestWorkspaceCloneForm(forms.WorkspaceCloneFormMixin, TestWorkspaceForm):
            class Meta(TestWorkspaceForm.Meta):
                pass

        auth_domain = factories.ManagedGroupFactory.create(name="other-name")
        self.workspace_to_clone.authorization_domains.add(auth_domain)
        billing_project = factories.BillingProjectFactory.create()
        form_data = {
            "billing_project": billing_project,
            "name": "test-workspace",
            "authorization_domains": [],
        }
        form = TestWorkspaceCloneForm(self.workspace_to_clone, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("authorization_domains", form.errors)
        self.assertEqual(len(form.errors["authorization_domains"]), 1)
        self.assertIn(
            "contain all original workspace authorization domains",
            form.errors["authorization_domains"][0],
        )
        self.assertIn(auth_domain.name, form.errors["authorization_domains"][0])


class WorkspaceRequesterPaysFormTest(TestCase):
    """Tests for the WorkspaceRequesterPaysForm class."""

    form_class = forms.WorkspaceRequesterPaysForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "is_requester_pays": True,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_blank_is_requester_pays(self):
        """Form is valid when missing is_requester_pays."""
        # This likely evaluates as False.
        form_data = {
            # "is_requester_pays": True,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())


class GroupGroupMembershipFormTest(TestCase):
    form_class = forms.GroupGroupMembershipForm

    def test_valid(self):
        """Form is valid with necessary input."""
        parent = factories.ManagedGroupFactory.create(name="parent")
        child = factories.ManagedGroupFactory.create(name="child")
        form_data = {
            "parent_group": parent,
            "child_group": child,
            "role": models.GroupGroupMembership.RoleChoices.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_parent_group(self):
        """Form is invalid when missing the parent group."""
        child = factories.ManagedGroupFactory.create(name="child")
        form_data = {
            "child_group": child,
            "role": models.GroupGroupMembership.RoleChoices.MEMBER,
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
            "role": models.GroupGroupMembership.RoleChoices.MEMBER,
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
            # "role": models.GroupGroupMembership.RoleChoices.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_parent_not_managed(self):
        """Form is invalid when the parent group is not managed by the app."""
        parent = factories.ManagedGroupFactory.create(name="parent", is_managed_by_app=False)
        child = factories.ManagedGroupFactory.create(name="child")
        form_data = {
            "parent_group": parent,
            "child_group": child,
            "role": models.GroupGroupMembership.RoleChoices.MEMBER,
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
            "role": models.GroupAccountMembership.RoleChoices.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_parent_group(self):
        """Form is invalid when missing the group."""
        account = factories.AccountFactory.create()
        form_data = {
            "account": account,
            "role": models.GroupAccountMembership.RoleChoices.MEMBER,
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
            "role": models.GroupAccountMembership.RoleChoices.MEMBER,
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
            "role": models.GroupAccountMembership.RoleChoices.MEMBER,
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
            "role": models.GroupAccountMembership.RoleChoices.MEMBER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("account", form.errors)
        self.assertEqual(len(form.errors["account"]), 1)
        self.assertIn("valid choice", form.errors["account"][0])
        self.assertEqual(len(form.errors), 1)

    def test_account_includes_only_active_accounts(self):
        """Form only displays active accounts."""
        inactive_account = factories.AccountFactory.create(status=models.Account.INACTIVE_STATUS)
        active_account = factories.AccountFactory.create()
        form = self.form_class()
        self.assertIn(active_account, form.fields["account"].queryset)
        self.assertNotIn(inactive_account, form.fields["account"].queryset)


class WorkspaceGroupSharingFormTest(TestCase):
    """Tests for the WorkspaceGroupSharingForm class."""

    form_class = forms.WorkspaceGroupSharingForm

    def test_valid(self):
        """Form is valid with necessary input."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        form_data = {
            "workspace": workspace,
            "group": group,
            "access": models.WorkspaceGroupSharing.READER,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_group(self):
        """Form is invalid when missing the group."""
        workspace = factories.WorkspaceFactory.create()
        form_data = {
            "workspace": workspace,
            "access": models.WorkspaceGroupSharing.READER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("group", form.errors)
        self.assertEqual(len(form.errors["group"]), 1)
        self.assertIn("required", form.errors["group"][0])

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing the workspace."""
        group = factories.ManagedGroupFactory.create()
        form_data = {
            "group": group,
            "access": models.WorkspaceGroupSharing.READER,
        }
        form = self.form_class(data=form_data)
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("required", form.errors["workspace"][0])

    def test_invalid_missing_access(self):
        """Form is invalid when missing access."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        form_data = {
            "workspace": workspace,
            "group": group,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("access", form.errors)
        self.assertEqual(len(form.errors["access"]), 1)
        self.assertIn("required", form.errors["access"][0])

    def test_invalid_reader_can_compute(self):
        """Form is invalid when the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        form_data = {
            "workspace": workspace,
            "group": group,
            "access": models.WorkspaceGroupSharing.READER,
            "can_compute": True,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("__all__", form.errors)
        self.assertEqual(len(form.errors["__all__"]), 1)
        self.assertIn("compute privileges", form.errors["__all__"][0])

    def test_invalid_owner_can_compute_false(self):
        """Form is invalid when the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        form_data = {
            "workspace": workspace,
            "group": group,
            "access": models.WorkspaceGroupSharing.OWNER,
            "can_compute": False,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("__all__", form.errors)
        self.assertEqual(len(form.errors["__all__"]), 1)
        self.assertIn("compute privileges", form.errors["__all__"][0])

    def test_invalid_workspace_not_managed(self):
        """Form is invalid when the workspace is not managed by the app."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create(is_managed_by_app=False)
        form_data = {
            "workspace": workspace,
            "group": group,
            "access": models.WorkspaceGroupSharing.READER,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("valid choice", form.errors["workspace"][0])
