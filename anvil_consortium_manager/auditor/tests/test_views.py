import responses
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, User
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.forms import HiddenInput
from django.http.response import Http404
from django.shortcuts import resolve_url
from django.test import RequestFactory
from django.urls import reverse
from faker import Faker

from anvil_consortium_manager.audit import base as base_audit
from anvil_consortium_manager.models import (
    Account,
    AnVILProjectManagerAccess,
)
from anvil_consortium_manager.tests.factories import (
    BillingProjectFactory,
    ManagedGroupFactory,
)
from anvil_consortium_manager.tests.utils import AnVILAPIMockTestMixin, TestCase

from .. import forms, models, views
from . import factories

fake = Faker()


class BillingProjectAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the BillingProjectAudit view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with only view permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:audit:billing_projects:all", args=args)

    def get_api_url(self, billing_project_name):
        return self.api_client.rawls_entry_point + "/api/billing/v2/" + billing_project_name

    def get_api_json_response(self):
        return {
            "roles": ["User"],
        }

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectAudit.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_template(self):
        """Template loads successfully."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_audit_verified(self):
        """audit_verified is in the context data."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("verified_table", response.context_data)
        self.assertIsInstance(response.context_data["verified_table"], base_audit.VerifiedTable)
        self.assertEqual(len(response.context_data["verified_table"].rows), 0)

    def test_audit_verified_one_record(self):
        """audit_verified with one verified record."""
        billing_project = BillingProjectFactory.create()
        api_url = self.get_api_url(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=self.get_api_json_response(),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("verified_table", response.context_data)
        self.assertEqual(len(response.context_data["verified_table"].rows), 1)

    def test_audit_errors(self):
        """audit_errors is in the context data."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("error_table", response.context_data)
        self.assertIsInstance(response.context_data["error_table"], base_audit.ErrorTable)
        self.assertEqual(len(response.context_data["error_table"].rows), 0)

    def test_audit_errors_one_record(self):
        """audit_errors with one verified record."""
        billing_project = BillingProjectFactory.create()
        api_url = self.get_api_url(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("error_table", response.context_data)
        self.assertEqual(len(response.context_data["error_table"].rows), 1)

    def test_audit_not_in_app(self):
        """audit_errors is in the context data."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("not_in_app_table", response.context_data)
        self.assertIsInstance(response.context_data["not_in_app_table"], base_audit.NotInAppTable)
        self.assertEqual(len(response.context_data["not_in_app_table"].rows), 0)

    def test_audit_ok_is_ok(self):
        """audit_ok when audit_results.ok() is True."""
        billing_project = BillingProjectFactory.create()
        api_url = self.get_api_url(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_ok", response.context_data)
        self.assertEqual(response.context_data["audit_ok"], True)

    def test_audit_ok_is_not_ok(self):
        """audit_ok when audit_results.ok() is True."""
        billing_project = BillingProjectFactory.create()
        api_url = self.get_api_url(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_ok", response.context_data)
        self.assertEqual(response.context_data["audit_ok"], False)


class IgnoredManagedGroupMembershipDetailTest(TestCase):
    """Tests for the IgnoredManagedGroupMembershipDetail view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:audit:managed_groups:membership:ignored:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.IgnoredManagedGroupMembershipDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar@example.com"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar@example.com"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertEqual(response.status_code, 200)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
        request = self.factory.get(self.get_url("foo", "bar@example.com"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo1", "bar@example.com"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_invalid_obj(self):
        """Raises a 404 error with an invalid object pk."""
        request = self.factory.get(self.get_url("foo1", "bar@example.com"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request)

    def test_invalid_obj_different_group(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        request = self.factory.get(self.get_url("foo", obj.ignored_email))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request)

    def test_invalid_obj_different_email(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        email = fake.email()
        request = self.factory.get(self.get_url(obj.group.name, email))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request)

    def test_detail_page_links_staff_view(self):
        """Links to other object detail pages appear correctly when user has staff view permission."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        html = """<a href="{url}">{text}</a>""".format(url=obj.group.get_absolute_url(), text=str(obj.group))
        self.assertContains(response, html)
        # "Added by" link is tested in a separate test, since not all projects will have an absolute url for the user.
        # Action buttons.
        expected_url = reverse(
            "anvil_consortium_manager:audit:managed_groups:membership:ignored:delete",
            args=[obj.group.name, obj.ignored_email],
        )
        self.assertNotContains(response, expected_url)
        expected_url = reverse(
            "anvil_consortium_manager:audit:managed_groups:membership:ignored:update",
            args=[obj.group.name, obj.ignored_email],
        )
        self.assertNotContains(response, expected_url)

    def test_detail_page_links_staff_edit(self):
        """Links to other object detail pages appear correctly when user has staff edit permission."""
        user = User.objects.create_user(username="staff-edit", password="testpassword")
        user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(user)
        response = self.client.get(obj.get_absolute_url())
        html = """<a href="{url}">{text}</a>""".format(url=obj.group.get_absolute_url(), text=str(obj.group))
        self.assertContains(response, html)
        # "Added by" link is tested in a separate test, since not all projects will have an absolute url for the user.
        # Action buttons.
        expected_url = reverse(
            "anvil_consortium_manager:audit:managed_groups:membership:ignored:delete",
            args=[obj.group.name, obj.ignored_email],
        )
        self.assertContains(response, expected_url)
        expected_url = reverse(
            "anvil_consortium_manager:audit:managed_groups:membership:ignored:update",
            args=[obj.group.name, obj.ignored_email],
        )
        self.assertContains(response, expected_url)

    def test_detail_page_links_user_get_absolute_url(self):
        """HTML includes a link to the user profile when the added_by user has a get_absolute_url method."""

        # Dynamically set the get_absolute_url method. This is hacky...
        def foo(self):
            return "test_profile_{}".format(self.username)

        UserModel = get_user_model()
        setattr(UserModel, "get_absolute_url", foo)
        user = UserModel.objects.create(username="testuser2", password="testpassword")
        obj = factories.IgnoredManagedGroupMembershipFactory.create(added_by=user)
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertContains(response, user.get_absolute_url())


class IgnoredManagedGroupMembershipCreateTest(TestCase):
    """Tests for the IgnoredManagedGroupMembershipCreate view."""

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.group = ManagedGroupFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:audit:managed_groups:membership:ignored:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.IgnoredManagedGroupMembershipCreate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar@example.com"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar@example.com"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name, "foo@bar.com"))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar@example.com"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
        request = self.factory.get(self.get_url("foo", "bar@example.com"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar@example.com"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name, fake.email()))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.IgnoredManagedGroupMembershipForm)

    def test_context_group(self):
        """Context contains the group."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name, fake.email()))
        self.assertTrue("group" in response.context_data)
        self.assertEqual(response.context_data["group"], self.group)

    def test_context_email(self):
        """Context contains the email."""
        email = fake.email()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name, email))
        self.assertTrue("email" in response.context_data)
        self.assertEqual(response.context_data["email"], email)

    def test_form_hidden_input(self):
        """The proper inputs are hidden in the form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name, fake.email()))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"].fields["group"].widget, HiddenInput)
        self.assertIsInstance(response.context_data["form"].fields["ignored_email"].widget, HiddenInput)

    def test_get_initial(self):
        """Initial data is set correctly."""
        email = fake.email()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name, email))
        initial = response.context_data["form"].initial
        self.assertIn("group", initial)
        self.assertEqual(self.group, initial["group"])
        self.assertIn("ignored_email", initial)
        self.assertEqual(email, initial["ignored_email"])

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, "my@email.com"),
            {"group": self.group.pk, "ignored_email": "my@email.com", "note": "foo bar"},
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.IgnoredManagedGroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.IgnoredManagedGroupMembership)
        self.assertEqual(new_object.group, self.group)
        self.assertEqual(new_object.ignored_email, "my@email.com")
        self.assertEqual(new_object.note, "foo bar")
        self.assertEqual(new_object.added_by, self.user)

    def test_success_message(self):
        """Response includes a success message if successful."""
        email = fake.email()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, email),
            {
                "group": self.group.pk,
                "ignored_email": email,
                "note": fake.sentence(),
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.IgnoredManagedGroupMembershipCreate.success_message, str(messages[0]))

    def test_success_redirect(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        email = fake.email()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, email),
            {
                "group": self.group.pk,
                "ignored_email": email,
                "note": fake.sentence(),
            },
        )
        obj = models.IgnoredManagedGroupMembership.objects.latest("pk")
        self.assertRedirects(response, obj.get_absolute_url())

    def test_cannot_create_duplicate_object(self):
        """Cannot create a second object for the same group and email."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create(note="original note")
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, obj.ignored_email),
            {"group": obj.group.pk, "ignored_email": obj.ignored_email, "note": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        # import ipdb; ipdb.set_trace()
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.IgnoredManagedGroupMembership.objects.all(),
            models.IgnoredManagedGroupMembership.objects.filter(pk=obj.pk),
        )
        obj.refresh_from_db()
        self.assertEqual(obj.note, "original note")

    def test_get_group_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("foo", "test@eaxmple.com"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(models.IgnoredManagedGroupMembership.objects.count(), 0)

    def test_post_group_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url("foo", "test@eaxmple.com"),
            {
                "group": "foo",
                "ignored_email": "test@example.com",
                "note": "a note",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(models.IgnoredManagedGroupMembership.objects.count(), 0)

    def test_group_not_managed_by_app(self):
        """Form is not valid if the group is not managed by the app."""
        group = ManagedGroupFactory.create(is_managed_by_app=False)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(group.name, "test@example.com"),
            {
                "group": group.pk,
                "ignored_email": "test@example.com",
                "note": " a note",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("group", form.errors)
        self.assertEqual(len(form.errors["group"]), 1)
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.IgnoredManagedGroupMembership.objects.count(), 0)

    def test_invalid_input_email(self):
        """Posting invalid data to role field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, "foo"),
            {
                "group": self.group.pk,
                "ignored_email": "foo",
                "note": "bar",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("ignored_email", form.errors.keys())
        self.assertEqual(len(form.errors["ignored_email"]), 1)
        self.assertIn("valid email", form.errors["ignored_email"][0])
        self.assertEqual(models.IgnoredManagedGroupMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(self.group.name, "foo@bar.com"), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("ignored_email", form.errors.keys())
        self.assertIn("required", form.errors["ignored_email"][0])
        self.assertIn("note", form.errors.keys())
        self.assertIn("required", form.errors["note"][0])
        self.assertEqual(models.IgnoredManagedGroupMembership.objects.count(), 0)

    def test_post_blank_data_group(self):
        """Posting blank data to the group field does not create an object."""
        email = fake.email(0)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, email),
            {
                "ignored_email": email,
                "note": "foo bar",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.IgnoredManagedGroupMembership.objects.count(), 0)

    def test_post_blank_data_email(self):
        """Posting blank data to the account field does not create an object."""
        email = fake.email(0)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, email),
            {
                "group": self.group.pk,
                # "ignored_email": email,
                "note": "foo bar",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("ignored_email", form.errors.keys())
        self.assertIn("required", form.errors["ignored_email"][0])
        self.assertEqual(models.IgnoredManagedGroupMembership.objects.count(), 0)

    def test_post_blank_data_note(self):
        """Posting blank data to the note field does not create an object."""
        email = fake.email(0)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, email),
            {
                "group": self.group.pk,
                "ignored_email": email,
                # "note": "foo bar",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("note", form.errors.keys())
        self.assertIn("required", form.errors["note"][0])
        self.assertEqual(models.IgnoredManagedGroupMembership.objects.count(), 0)


class IgnoredManagedGroupMembershipDeleteTest(TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:audit:managed_groups:membership:ignored:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.IgnoredManagedGroupMembershipDelete.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar"))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar"))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.group, obj.ignored_email))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, slug="foo", email="bar")

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, slug="foo", email="bar")

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, slug="foo", email="bar")

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, slug="foo", email="bar")

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.group, obj.ignored_email), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Account.objects.count(), 0)
        # History is added.
        self.assertEqual(obj.history.count(), 2)
        self.assertEqual(obj.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.group, obj.ignored_email), {"submit": ""}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.IgnoredManagedGroupMembershipDelete.success_message, str(messages[0]))

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        other_obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.group, obj.ignored_email), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.IgnoredManagedGroupMembership.objects.count(), 1)
        self.assertQuerySetEqual(
            Account.objects.all(),
            Account.objects.filter(pk=other_obj.pk),
        )

    def test_success_url(self):
        """Redirects to the expected page."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        # Need to use the client instead of RequestFactory to check redirection url.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.group, obj.ignored_email), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, obj.group.get_absolute_url())


class IgnoredManagedGroupMembershipUpdateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:audit:managed_groups:membership:ignored:update", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.IgnoredManagedGroupMembershipUpdate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar"))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar"))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.group.name, obj.ignored_email))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, slug="foo", email="bar")

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, slug="foo", email="bar")

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, slug="foo", email="bar")

    def test_object_does_not_exist(self):
        """Raises Http404 if object does not exist."""
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, slug="foo", email="bar")

    def test_has_form_in_context(self):
        """Response includes a form."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.group.name, obj.ignored_email))
        self.assertTrue("form" in response.context_data)
        # Form is auto-generated by the view, so don't check the class.

    def test_can_modify_note(self):
        """Can set the note when creating a billing project."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create(note="original note")
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.group.name, obj.ignored_email), {"note": "new note"})
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.note, "new note")

    def test_success_message(self):
        """Response includes a success message if successful."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.group.name, obj.ignored_email), {"note": "new note"}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.IgnoredManagedGroupMembershipUpdate.success_message, str(messages[0]))

    def test_redirects_to_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.group.name, obj.ignored_email), {"note": "new note"})
        self.assertRedirects(response, obj.get_absolute_url())

    def test_missing_note(self):
        obj = factories.IgnoredManagedGroupMembershipFactory.create(note="original note")
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.group.name, obj.ignored_email), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("note", form.errors)
        self.assertEqual(len(form.errors["note"]), 1)
        self.assertIn("required", form.errors["note"][0])
        obj.refresh_from_db()
        self.assertEqual(obj.note, "original note")

    def test_blank_note(self):
        obj = factories.IgnoredManagedGroupMembershipFactory.create(note="original note")
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.group.name, obj.ignored_email), {"note": ""})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("note", form.errors)
        self.assertEqual(len(form.errors["note"]), 1)
        self.assertIn("required", form.errors["note"][0])
        obj.refresh_from_db()
        self.assertEqual(obj.note, "original note")
