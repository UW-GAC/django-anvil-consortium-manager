import datetime
import json
from unittest import skip
from unittest.mock import patch
from uuid import uuid4

import responses
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, User
from django.contrib.messages import get_messages
from django.contrib.sites.models import Site
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.forms import BaseInlineFormSet, HiddenInput
from django.http.response import Http404
from django.shortcuts import resolve_url
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from faker import Faker
from freezegun import freeze_time

from .. import __version__, filters, forms, models, tables, views
from ..adapters.account import get_account_adapter
from ..adapters.default import DefaultWorkspaceAdapter
from ..adapters.workspace import workspace_adapter_registry
from ..tokens import account_verification_token
from . import factories
from .test_app import forms as app_forms
from .test_app import models as app_models
from .test_app import tables as app_tables
from .test_app.adapters import (
    TestAccountAdapter,
    TestAccountHookFailAdapter,
    TestAfterWorkspaceCreateAdapter,
    TestAfterWorkspaceImportAdapter,
    TestBeforeWorkspaceCreateAdapter,
    TestForeignKeyWorkspaceAdapter,
    TestWorkspaceAdapter,
)
from .test_app.factories import TestWorkspaceDataFactory
from .test_app.filters import TestAccountListFilter
from .utils import AnVILAPIMockTestMixin, TestCase  # Redefined to work with Django < 4.2 and Django=4.2.

fake = Faker()


class IndexTest(TestCase):
    """Tests for the index page."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with view permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:index", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.Index.as_view()

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

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_context_data_version(self):
        """Context data includes version."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("app_version", response.context_data)
        self.assertEqual(response.context_data["app_version"], __version__)


class ViewEditUrlTest(TestCase):
    """Test that urls appear correctly based on user permissions."""

    view_urls = (
        reverse("anvil_consortium_manager:index"),
        reverse("anvil_consortium_manager:status"),
        reverse("anvil_consortium_manager:accounts:list"),
        reverse("anvil_consortium_manager:auditor:accounts:all"),
        reverse("anvil_consortium_manager:billing_projects:list"),
        reverse("anvil_consortium_manager:auditor:billing_projects:all"),
        reverse("anvil_consortium_manager:managed_groups:list"),
        reverse("anvil_consortium_manager:managed_groups:visualization"),
        reverse("anvil_consortium_manager:auditor:managed_groups:all"),
        reverse("anvil_consortium_manager:workspaces:landing_page"),
        reverse("anvil_consortium_manager:workspaces:list_all"),
        reverse("anvil_consortium_manager:auditor:workspaces:all"),
    )

    # other_urls = (
    #     reverse("anvil_consortium_manager:accounts:list_active"),
    #     reverse("anvil_consortium_manager:accounts:list_inactive"),
    #     reverse("anvil_consortium_manager:accounts:deactivate"),
    #     reverse("anvil_consortium_manager:accounts:delete"),
    #     reverse("anvil_consortium_manager:accounts:reactivate"),
    #     reverse("anvil_consortium_manager:managed_groups:delete"),
    #     reverse("anvil_consortium_manager:workspaces:sharing:delete"),
    #     reverse("anvil_consortium_manager:managed_groups:member_accounts:delete"),
    #     reverse("anvil_consortium_manager:managed_groups:member_groups:delete"),
    #     reverse("anvil_consortium_manager:workspaces:sharing:update"),
    #     reverse("anvil_consortium_manager:workspaces:delete"),
    #     reverse("anvil_consortium_manager:auditor:managed_groups:membership:by_group:all"),
    #     reverse("anvil_consortium_manager:auditor:workspaces:all_access"),
    # )

    edit_urls = (
        reverse("anvil_consortium_manager:accounts:import"),
        reverse("anvil_consortium_manager:billing_projects:import"),
        reverse("anvil_consortium_manager:group_account_membership:new"),
        reverse("anvil_consortium_manager:group_group_membership:new"),
        reverse("anvil_consortium_manager:managed_groups:new"),
        reverse("anvil_consortium_manager:workspace_group_sharing:new"),
    )

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with view permission.
        self.view_user = User.objects.create_user(username="test_view", password="view")
        self.view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        # Create a user with view permission.
        self.edit_user = User.objects.create_user(username="test_edit", password="test")
        self.edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )

    def test_view_navbar(self):
        """Links to edit required do not appear in the index when user only has view permission."""
        self.client.force_login(self.view_user)
        # Test with the BillingProjectList page for now, since we're testing the navbar only.
        response = self.client.get(reverse("anvil_consortium_manager:billing_projects:list"))
        for url in self.edit_urls:
            self.assertNotContains(response, url)
        for url in self.view_urls:
            self.assertContains(response, url)

    def test_edit_navbar(self):
        """Links to edit required do not appear in the index when user only has view permission."""
        self.client.force_login(self.edit_user)
        # Test with the BillingProjectList page for now, since we're testing the navbar only.
        response = self.client.get(reverse("anvil_consortium_manager:billing_projects:list"))
        for url in self.edit_urls:
            self.assertContains(response, url)
        for url in self.view_urls:
            self.assertContains(response, url)

    def test_view_index(self):
        """Links to edit required do not appear in the index when user only has view permission."""
        self.client.force_login(self.view_user)
        response = self.client.get(reverse("anvil_consortium_manager:index"))
        for url in self.edit_urls:
            self.assertNotContains(response, url)
        for url in self.view_urls:
            self.assertContains(response, url)

    def test_edit_index(self):
        """Links to edit required do not appear in the index when user only has view permission."""
        self.client.force_login(self.edit_user)
        response = self.client.get(reverse("anvil_consortium_manager:index"))
        for url in self.edit_urls:
            self.assertContains(response, url)
        for url in self.view_urls:
            self.assertContains(response, url)


class AnVILStatusTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with view permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_json_me_data(self):
        json_data = {
            "enabled": True,
            "userEmail": "test-user@example.com",
            "userSubjectId": "121759663603983501425",
        }
        return json_data

    def get_json_status_data(self, status_ok=True):
        json_data = {
            "ok": status_ok,
            "systems": {
                "system1": {"ok": True},
                "system2": {"ok": False, "messages": ["Error"]},
            },
        }
        return json_data

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:status", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AnVILStatus.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        url_me = self.api_client.firecloud_entry_point + "/me?userDetailsOnly=true"
        self.anvil_response_mock.add(responses.GET, url_me, status=200, json=self.get_json_me_data())
        url_status = self.api_client.firecloud_entry_point + "/status"
        self.anvil_response_mock.add(responses.GET, url_status, status=200, json=self.get_json_status_data())
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
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_context_data_anvil_status_ok(self):
        """Context data contains anvil_status."""
        url_me = self.api_client.firecloud_entry_point + "/me?userDetailsOnly=true"
        self.anvil_response_mock.add(responses.GET, url_me, status=200, json=self.get_json_me_data())
        url_status = self.api_client.firecloud_entry_point + "/status"
        self.anvil_response_mock.add(responses.GET, url_status, status=200, json=self.get_json_status_data())
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("anvil_status", response.context_data)
        self.assertEqual(response.context_data["anvil_status"], {"ok": True})
        self.assertIn("anvil_systems_status", response.context_data)

    def test_context_data_anvil_status_not_ok(self):
        """Context data contains anvil_status."""
        url_me = self.api_client.firecloud_entry_point + "/me?userDetailsOnly=true"
        self.anvil_response_mock.add(responses.GET, url_me, status=200, json=self.get_json_me_data())
        url_status = self.api_client.firecloud_entry_point + "/status"
        self.anvil_response_mock.add(
            responses.GET,
            url_status,
            status=200,
            json=self.get_json_status_data(status_ok=False),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("anvil_status", response.context_data)
        self.assertEqual(response.context_data["anvil_status"], {"ok": False})
        self.assertIn("anvil_systems_status", response.context_data)

    def test_context_data_status_api_error(self):
        """Page still loads if there is an AnVIL API error in the status call."""
        url_me = self.api_client.firecloud_entry_point + "/me?userDetailsOnly=true"
        self.anvil_response_mock.add(responses.GET, url_me, status=200, json=self.get_json_me_data())
        # Error in status API
        url_status = self.api_client.firecloud_entry_point + "/status"
        self.anvil_response_mock.add(responses.GET, url_status, status=499)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: error checking API status", str(messages[0]))

    def test_context_data_status_me_error(self):
        """Page still loads if there is an AnVIL API error in the me call."""
        url_me = self.api_client.firecloud_entry_point + "/me?userDetailsOnly=true"
        self.anvil_response_mock.add(responses.GET, url_me, status=499)
        url_status = self.api_client.firecloud_entry_point + "/status"
        self.anvil_response_mock.add(
            responses.GET,
            url_status,
            status=200,
            json=self.get_json_status_data(status_ok=False),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: error checking API user", str(messages[0]))

    def test_context_data_both_api_error(self):
        """Page still loads if there is an AnVIL API error in both the status and me call."""
        url_me = self.api_client.firecloud_entry_point + "/me?userDetailsOnly=true"
        self.anvil_response_mock.add(responses.GET, url_me, status=499)
        # Error in status API
        url_status = self.api_client.firecloud_entry_point + "/status"
        self.anvil_response_mock.add(responses.GET, url_status, status=499)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 2)
        self.assertEqual("AnVIL API Error: error checking API status", str(messages[0]))
        self.assertEqual("AnVIL API Error: error checking API user", str(messages[1]))


class BillingProjectImportTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_api_url(self, billing_project_name):
        """Get the AnVIL API url that is called by the anvil_exists method."""
        return self.api_client.rawls_entry_point + "/api/billing/v2/" + billing_project_name

    def get_api_json_response(self):
        return {
            "roles": ["User"],
        }

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:billing_projects:import", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectImport.as_view()

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

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.BillingProjectImportForm)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        billing_project_name = "test-billing"
        url = self.get_api_url(billing_project_name)
        self.anvil_response_mock.add(responses.GET, url, status=200, json=self.get_api_json_response())
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": billing_project_name})
        self.assertEqual(response.status_code, 302)
        new_object = models.BillingProject.objects.latest("pk")
        self.assertIsInstance(new_object, models.BillingProject)
        self.assertEqual(new_object.name, billing_project_name)
        self.assertEqual(new_object.has_app_as_user, True)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_set_note(self):
        """Can set the note when creating a billing project."""
        billing_project_name = "test-billing"
        url = self.get_api_url(billing_project_name)
        self.anvil_response_mock.add(responses.GET, url, status=200, json=self.get_api_json_response())
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": billing_project_name, "note": "test note"})
        self.assertEqual(response.status_code, 302)
        new_object = models.BillingProject.objects.latest("pk")
        self.assertEqual(new_object.note, "test note")

    def test_success_message(self):
        """Response includes a success message if successful."""
        billing_project_name = "test-billing"
        url = self.get_api_url(billing_project_name)
        self.anvil_response_mock.add(responses.GET, url, status=200, json=self.get_api_json_response())
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": billing_project_name}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.BillingProjectImport.success_message, str(messages[0]))

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        billing_project_name = "test-billing"
        url = self.get_api_url(billing_project_name)
        self.anvil_response_mock.add(responses.GET, url, status=200, json=self.get_api_json_response())
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": billing_project_name})
        new_object = models.BillingProject.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())

    def test_cannot_create_duplicate_object(self):
        """Cannot create two billing projects with the same name."""
        obj = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": obj.name})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("already exists", form.errors["name"][0])
        self.assertQuerySetEqual(
            models.BillingProject.objects.all(),
            models.BillingProject.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_case_insensitive(self):
        """Cannot create two billing projects with the same name."""
        obj = factories.BillingProjectFactory.create(name="project")
        # No API calls should be made.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "PROJECT"})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("already exists", form.errors["name"][0])
        self.assertQuerySetEqual(
            models.BillingProject.objects.all(),
            models.BillingProject.objects.filter(pk=obj.pk),
        )

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": ""})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_not_users_of_billing_project(self):
        """Posting valid data to the form does not create an object if we are not users on AnVIL."""
        billing_project_name = "test-billing"
        url = self.get_api_url(billing_project_name)
        self.anvil_response_mock.add(responses.GET, url, status=404, json={"message": "other"})
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": billing_project_name})
        self.assertEqual(response.status_code, 200)
        # the form is valid...
        self.assertIn("form", response.context)
        form = response.context["form"]
        self.assertTrue(form.is_valid())
        # ...but there were issues with the API call.
        # No object was created.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        # There is a message on the page.
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            str(messages[0]),
            views.BillingProjectImport.message_not_users_of_billing_project,
        )
        # No accounts were created.
        self.assertEqual(models.Account.objects.count(), 0)

    def test_api_error(self):
        """Does not create a new Account if the API returns some other error."""
        billing_project_name = "test-billing"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project_name),
            status=500,
            json={"message": "other error"},
        )
        # Need the client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": billing_project_name})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        form = response.context["form"]
        # The form is valid...
        self.assertTrue(form.is_valid())
        # ...but there was some error from the API.
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: other error", str(messages[0]))
        # No accounts were created.
        self.assertEqual(models.BillingProject.objects.count(), 0)


class BillingProjectUpdateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:billing_projects:update", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectUpdate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo"))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo"))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        instance = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(instance.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, slug="foo")

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, slug="foo")

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, slug="foo")

    def test_object_does_not_exist(self):
        """Raises Http404 if object does not exist."""
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, slug="foo")

    def test_has_form_in_context(self):
        """Response includes a form."""
        instance = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(instance.name))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.BillingProjectUpdateForm)

    def test_can_modify_note(self):
        """Can set the note when creating a billing project."""
        instance = factories.BillingProjectFactory.create(note="original note")
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.name), {"note": "new note"})
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        self.assertEqual(instance.note, "new note")

    def test_success_message(self):
        """Response includes a success message if successful."""
        instance = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.name), {}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.BillingProjectUpdate.success_message, str(messages[0]))

    def test_redirects_to_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        instance = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.name), {})
        self.assertRedirects(response, instance.get_absolute_url())


class BillingProjectDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:billing_projects:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo"))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo"))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.name))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_status_code_with_existing_object_not_user(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.BillingProjectFactory.create(has_app_as_user=False)
        # Only clients load the template.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.name))
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_slug(self):
        """Raises a 404 error with an invalid object slug."""
        factories.BillingProjectFactory.create()
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, slug="foo")

    def test_workspace_table(self):
        """The workspace table exists."""
        obj = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.name))
        self.assertIn("workspace_table", response.context_data)
        self.assertIsInstance(response.context_data["workspace_table"], tables.WorkspaceStaffTable)

    def test_workspace_table_none(self):
        """No workspaces are shown if the billing project does not have any workspaces."""
        billing_project = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(billing_project.name))
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)

    def test_workspace_table_one(self):
        """One workspace is shown if the group have access to one workspace."""
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(billing_project=billing_project)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(billing_project.name))
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 1)

    def test_workspace_table_two(self):
        """Two workspaces are shown if the group have access to two workspaces."""
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(billing_project=billing_project, name="w1")
        factories.WorkspaceFactory.create(billing_project=billing_project, name="w2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(billing_project.name))
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 2)

    def test_shows_workspace_for_only_this_group(self):
        """Only shows workspcaes that this group has access to."""
        billing_project = factories.BillingProjectFactory.create()
        other_billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(billing_project=other_billing_project)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(billing_project.name))
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)


class BillingProjectListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:billing_projects:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectList.as_view()

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

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_template_with_user_permission(self):
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

    def test_view_has_correct_table_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.BillingProjectStaffTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.BillingProjectFactory()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.BillingProjectFactory.create(name="bp1")
        factories.BillingProjectFactory.create(name="bp2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_filter_return_no_object(self):
        factories.BillingProjectFactory.create(name="Billing_project")
        factories.BillingProjectFactory.create(name="Project")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"name__icontains": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_returns_one_object_exact(self):
        instance = factories.BillingProjectFactory.create(name="billing_project")
        factories.BillingProjectFactory.create(name="project")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"name__icontains": "billing_project"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_case_insensitive(self):
        instance = factories.BillingProjectFactory.create(name="Billing_project")
        factories.BillingProjectFactory.create(name="Project")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"name__icontains": "billing_project"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_case_contains(self):
        instance = factories.BillingProjectFactory.create(name="Billing_project")
        factories.BillingProjectFactory.create(name="Project")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"name__icontains": "illing"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_mutiple_objects(self):
        factories.BillingProjectFactory.create(name="project1")
        factories.BillingProjectFactory.create(name="project_2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"name__icontains": "project"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class BillingProjectAutocompleteTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with the correct permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:billing_projects:autocomplete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectAutocomplete.as_view()

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
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_returns_all_objects(self):
        """Queryset returns all objects when there is no query."""
        objects = factories.BillingProjectFactory.create_batch(10)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 10)
        self.assertEqual(sorted(returned_ids), sorted([object.pk for object in objects]))

    def test_returns_correct_object_match(self):
        """Queryset returns the correct objects when query matches the name."""
        object = factories.BillingProjectFactory.create(name="test-bp")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "test-bp"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        object = factories.BillingProjectFactory.create(name="test-bp")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "test"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_returns_correct_object_containing_query(self):
        """Queryset returns the correct objects when the name contains the query."""
        object = factories.BillingProjectFactory.create(name="test-bp")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "bp"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        object = factories.BillingProjectFactory.create(name="TEST-BP")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "test-bp"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_does_not_return_billing_projects_where_app_is_not_user(self):
        """Queryset does not return groups that are not managed by the app."""
        factories.BillingProjectFactory.create(name="test-bp", has_app_as_user=False)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(json.loads(response.content.decode("utf-8"))["results"], [])


class AccountDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def tearDown(self):
        # One of the testes dynamically sets the get_absolute_url method..
        try:
            del get_user_model().get_absolute_url
        except AttributeError:
            pass

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        uuid = uuid4()
        response = self.client.get(self.get_url(uuid))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(uuid))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        uuid = uuid4()
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(uuid4()))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_context_active_account(self):
        """An is_inactive flag is included in the context."""
        active_account = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(active_account.uuid))
        context = response.context_data
        self.assertIn("is_inactive", context)
        self.assertFalse(context["is_inactive"])
        self.assertIn("show_deactivate_button", context)
        self.assertTrue(context["show_deactivate_button"])
        self.assertIn("show_reactivate_button", context)
        self.assertFalse(context["show_reactivate_button"])

    def test_context_inactive_account(self):
        """An is_inactive flag is included in the context."""
        active_account = factories.AccountFactory.create(status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(active_account.uuid))
        context = response.context_data
        self.assertIn("is_inactive", context)
        self.assertTrue(context["is_inactive"])
        self.assertIn("show_deactivate_button", context)
        self.assertFalse(context["show_deactivate_button"])
        self.assertIn("show_reactivate_button", context)
        self.assertTrue(context["show_reactivate_button"])

    def test_context_unlinked_users_no_unlinked_user(self):
        account = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        context = response.context_data
        self.assertIn("unlinked_users", context)
        self.assertEqual(len(context["unlinked_users"]), 0)

    def test_context_unlinked_users_one_unlinked_user(self):
        account = factories.AccountFactory.create()
        user = User.objects.create_user(username="test_unlinked", password="test")
        account.unlinked_users.add(user)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        context = response.context_data
        self.assertIn("unlinked_users", context)
        self.assertEqual(len(context["unlinked_users"]), 1)
        self.assertIn(user, context["unlinked_users"])
        self.assertIn(str(user), response.content.decode())

    def test_context_unlinked_users_two_unlinked_users(self):
        account = factories.AccountFactory.create()
        user_1 = User.objects.create_user(username="test_unlinked_1", password="test")
        user_2 = User.objects.create_user(username="test_unlinked_2", password="test")
        account.unlinked_users.add(user_1, user_2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        context = response.context_data
        self.assertIn("unlinked_users", context)
        self.assertEqual(len(context["unlinked_users"]), 2)
        self.assertIn(user_1, context["unlinked_users"])
        self.assertIn(user_2, context["unlinked_users"])
        self.assertIn(str(user_1), response.content.decode())
        self.assertIn(str(user_2), response.content.decode())

    def test_context_show_unlink_button_linked_account(self):
        """An is_inactive flag is included in the context."""
        account = factories.AccountFactory.create(verified=True)
        edit_user = User.objects.create_user(username="edit", password="test")
        edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )
        self.client.force_login(edit_user)
        response = self.client.get(self.get_url(account.uuid))
        context = response.context_data
        self.assertIn("show_unlink_button", context)
        self.assertTrue(context["show_unlink_button"])
        self.assertContains(
            response, reverse("anvil_consortium_manager:accounts:unlink", kwargs={"uuid": account.uuid})
        )

    def test_context_show_unlink_button_linked_account_view_permission(self):
        """An is_inactive flag is included in the context."""
        account = factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        context = response.context_data
        self.assertIn("show_unlink_button", context)
        self.assertTrue(context["show_unlink_button"])
        self.assertNotContains(
            response, reverse("anvil_consortium_manager:accounts:unlink", kwargs={"uuid": account.uuid})
        )

    def test_context_show_unlink_button_unlinked_account(self):
        """An is_inactive flag is included in the context."""
        account = factories.AccountFactory.create(verified=False)
        edit_user = User.objects.create_user(username="edit", password="test")
        edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )
        self.client.force_login(edit_user)
        response = self.client.get(self.get_url(account.uuid))
        context = response.context_data
        self.assertIn("show_unlink_button", context)
        self.assertFalse(context["show_unlink_button"])
        self.assertNotContains(
            response, reverse("anvil_consortium_manager:accounts:unlink", kwargs={"uuid": account.uuid})
        )

    def test_context_show_unlink_button_previously_linked(self):
        """An is_inactive flag is included in the context."""
        account = factories.AccountFactory.create(verified=True)
        account.unlinked_users.add(self.user)
        account.user = None
        account.save()
        edit_user = User.objects.create_user(username="edit", password="test")
        edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )
        self.client.force_login(edit_user)
        response = self.client.get(self.get_url(account.uuid))
        context = response.context_data
        self.assertIn("show_unlink_button", context)
        self.assertFalse(context["show_unlink_button"])
        self.assertNotContains(
            response, reverse("anvil_consortium_manager:accounts:unlink", kwargs={"uuid": account.uuid})
        )

    def test_template_verified_account(self):
        """The template renders with a verified account."""
        obj = factories.AccountFactory.create(verified=True)
        # Only clients load the template.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_existing_object_service_account(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.AccountFactory.create(is_service_account=True)
        # Only clients load the template.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, uuid=uuid)

    def test_group_account_membership_table(self):
        """The group membership table exists."""
        obj = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertIn("group_table", response.context_data)
        self.assertIsInstance(response.context_data["group_table"], tables.GroupAccountMembershipStaffTable)

    def test_group_account_membership_none(self):
        """No groups are shown if the account is not part of any groups."""
        account = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)

    def test_group_account_membership_one(self):
        """One group is shown if the account is part of one group."""
        account = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create(account=account)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 1)

    def test_group_account_membership_two(self):
        """Two groups are shown if the account is part of two groups."""
        account = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create(group__name="g1", account=account)
        factories.GroupAccountMembershipFactory.create(group__name="g2", account=account)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 2)

    def test_shows_group_account_membership_for_only_that_user(self):
        """Only shows groups that this research is part of."""
        account = factories.AccountFactory.create(email="email_1@example.com")
        other_account = factories.AccountFactory.create(email="email_2@example.com")
        factories.GroupAccountMembershipFactory.create(account=other_account)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)

    def test_edit_permission(self):
        """Links to reactivate/deactivate/delete pages appear if the user has edit permission."""
        edit_user = User.objects.create_user(username="edit", password="test")
        edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )
        self.client.force_login(edit_user)
        account = factories.AccountFactory.create()
        response = self.client.get(self.get_url(account.uuid))
        self.assertIn("show_edit_links", response.context_data)
        self.assertTrue(response.context_data["show_edit_links"])
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:accounts:delete",
                kwargs={"uuid": account.uuid},
            ),
        )

    def test_view_permission(self):
        """Links to reactivate/deactivate/delete pages appear if the user has edit permission."""
        view_user = User.objects.create_user(username="view", password="test")
        view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
        )
        self.client.force_login(view_user)
        account = factories.AccountFactory.create()
        response = self.client.get(self.get_url(account.uuid))
        self.assertIn("show_edit_links", response.context_data)
        self.assertFalse(response.context_data["show_edit_links"])
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:accounts:delete",
                kwargs={"uuid": account.uuid},
            ),
        )

    def test_accessible_workspace_table(self):
        """The accessible workspace table exists."""
        obj = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertIn("accessible_workspace_table", response.context_data)
        self.assertIsInstance(
            response.context_data["accessible_workspace_table"],
            tables.WorkspaceGroupSharingStaffTable,
        )

    def test_accessible_workspace_none(self):
        """No accessible_workspaces are shown if there are no accessible workspace for the account."""
        account = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        self.assertIn("accessible_workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["accessible_workspace_table"].rows), 0)

    def test_accessible_workspace_one(self):
        """One accessible_workspace is shown if there is one accessible workspace for the account."""
        account = factories.AccountFactory.create()
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        self.assertIn("accessible_workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["accessible_workspace_table"].rows), 1)

    def test_accessible_workspace_two(self):
        """Two accessible_workspaces are shown if there are two accessible workspaces for the account."""
        account = factories.AccountFactory.create()
        workspace_1 = factories.WorkspaceFactory.create(name="w1")
        workspace_2 = factories.WorkspaceFactory.create(name="w2")
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace_2, group=group)
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace_1, group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        self.assertIn("accessible_workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["accessible_workspace_table"].rows), 2)

    def test_accessible_workspace_for_only_that_user(self):
        """Only shows accessible_workspace that is accessible to the account."""
        account = factories.AccountFactory.create()
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        self.assertIn("accessible_workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["accessible_workspace_table"].rows), 0)

    def test_accessible_workspace_one_workspace_shared_twice(self):
        """Two records are shown for the same workspace if it is shared with an account twice."""
        account = factories.AccountFactory.create()
        workspace = factories.WorkspaceFactory.create()
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group_1, account=account)
        factories.GroupAccountMembershipFactory.create(group=group_2, account=account)
        factories.WorkspaceGroupSharingFactory.create(
            workspace=workspace,
            group=group_1,
            access=models.WorkspaceGroupSharing.READER,
        )
        factories.WorkspaceGroupSharingFactory.create(
            workspace=workspace,
            group=group_2,
            access=models.WorkspaceGroupSharing.WRITER,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        self.assertIn("accessible_workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["accessible_workspace_table"].rows), 2)

    def test_accessible_workspace_only_groups_for_this_account(self):
        """Only shows workspaces shared with one of the account's groups (or parent groups)."""
        account = factories.AccountFactory.create()
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        sharing = factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Share the workspace with a different group that the account is not part of.
        other_group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=other_group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        table = response.context_data["accessible_workspace_table"]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(sharing, table.data)

    def test_render_with_user_get_absolute_url(self):
        """HTML includes a link to the user profile when the linked user has a get_absolute_url method."""

        # Dynamically set the get_absolute_url method. This is hacky...
        def foo(self):
            return "test_profile_{}".format(self.username)

        UserModel = get_user_model()
        setattr(UserModel, "get_absolute_url", foo)
        user = UserModel.objects.create(username="testuser2", password="testpassword")
        account = factories.AccountFactory.create(verified=True, verified_email_entry__user=user)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(account.uuid))
        self.assertInHTML(
            """<a href="test_profile_testuser2">testuser2</a>""",
            response.content.decode(),
        )


class AccountImportTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_api_url(self, email):
        """Get the AnVIL API url that is called by the anvil_exists method."""
        return self.api_client.sam_entry_point + "/api/users/v1/" + email

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:import", args=args)

    def get_api_json_response(self, email):
        id = fake.bothify(text="#" * 21)
        return {
            "googleSubjectId": id,
            "userEmail": email,
            "userSubjectId": id,
        }

    def get_view(self):
        """Return the view being tested."""
        return views.AccountImport.as_view()

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

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.AccountImportForm)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        email = "test@example.com"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(email),
            status=200,
            json=self.get_api_json_response(email),
        )
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 302)
        new_object = models.Account.objects.latest("pk")
        self.assertIsInstance(new_object, models.Account)
        self.assertFalse(new_object.is_service_account)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_create_an_object_with_note(self):
        """Posting valid data with a note field to the form creates an object."""
        email = "test@example.com"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(email),
            status=200,
            json=self.get_api_json_response(email),
        )
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email, "note": "test note"})
        self.assertEqual(response.status_code, 302)
        new_object = models.Account.objects.latest("pk")
        self.assertIsInstance(new_object, models.Account)
        self.assertEqual(new_object.note, "test note")

    def test_success_message(self):
        """Response includes a success message if successful."""
        email = "test@example.com"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(email),
            status=200,
            json=self.get_api_json_response(email),
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountImport.success_message, str(messages[0]))

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        email = "test@example.com"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(email),
            status=200,
            json=self.get_api_json_response(email),
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        new_object = models.Account.objects.latest("pk")
        self.assertRedirects(
            response,
            new_object.get_absolute_url(),
        )

    def test_cannot_create_duplicate_object(self):
        """Cannot create two accounts with the same email."""
        obj = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": obj.email})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("already exists", form.errors["email"][0])
        self.assertQuerySetEqual(
            models.Account.objects.all(),
            models.Account.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_case_insensitive(self):
        """Cannot import two accounts with the same email, regardless of case."""
        obj = factories.AccountFactory.create(email="foo@example.com")
        # No API calls should be made.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": "FOO@example.com"})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("already exists", form.errors["email"][0])
        self.assertQuerySetEqual(
            models.Account.objects.all(),
            models.Account.objects.filter(pk=obj.pk),
        )

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": "1"})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("valid email", form.errors["email"][0])
        self.assertEqual(models.Account.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("required", form.errors["email"][0])
        self.assertEqual(models.Account.objects.count(), 0)

    def test_can_create_service_account(self):
        """Can create a service account."""
        email = "test@example.com"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(email),
            status=200,
            json=self.get_api_json_response(email),
        )
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email, "is_service_account": True})
        self.assertEqual(response.status_code, 302)
        new_object = models.Account.objects.latest("pk")
        self.assertIsInstance(new_object, models.Account)
        self.assertTrue(new_object.is_service_account)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_does_not_exist_on_anvil(self):
        """Does not create a new Account when it doesn't exist on AnVIL."""
        email = "test@example.com"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(email),
            status=404,
            json={"message": "other error"},
        )
        # Need the client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        form = response.context["form"]
        # The form is valid...
        self.assertTrue(form.is_valid())
        # ...but the account doesn't exist on AnVIL
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountImport.message_account_does_not_exist)
        # No accounts were created.
        self.assertEqual(models.Account.objects.count(), 0)

    def test_email_is_associated_with_group(self):
        """Does not create a new Account if the API returns a code associated with a group."""
        email = "test@example.com"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(email),
            status=204,
        )
        # Need the client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        form = response.context["form"]
        # The form is valid...
        self.assertTrue(form.is_valid())
        # ...but there was some error from the API.
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountImport.message_account_does_not_exist, str(messages[0]))
        # No accounts were created.
        self.assertEqual(models.Account.objects.count(), 0)

    def test_api_error(self):
        """Does not create a new Account if the API returns some other error."""
        email = "test@example.com"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(email),
            status=500,
            json={"message": "other error"},
        )
        # Need the client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        form = response.context["form"]
        # The form is valid...
        self.assertTrue(form.is_valid())
        # ...but there was some error from the API.
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: other error", str(messages[0]))
        # No accounts were created.
        self.assertEqual(models.Account.objects.count(), 0)


class AccountUpdateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:update", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountUpdate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        uuid = uuid4()
        response = self.client.get(self.get_url(uuid))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(uuid))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        instance = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(instance.uuid))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        uuid = uuid4()
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=uuid)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(uuid4()))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        uuid = uuid4()
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=uuid)

    def test_object_does_not_exist(self):
        """Raises Http404 if object does not exist."""
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, uuid=uuid)

    def test_has_form_in_context(self):
        """Response includes a form."""
        instance = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(instance.uuid))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.AccountUpdateForm)

    def test_can_modify_note(self):
        """Can set the note when creating a billing project."""
        instance = factories.AccountFactory.create(note="original note")
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {"note": "new note"})
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        self.assertEqual(instance.note, "new note")

    def test_success_message(self):
        """Response includes a success message if successful."""
        instance = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountUpdate.success_message, str(messages[0]))

    def test_redirects_to_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        instance = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {})
        self.assertRedirects(response, instance.get_absolute_url())


class AccountLinkTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the AccountLink view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.ACCOUNT_LINK_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:link", args=args)

    def get_api_url(self, email):
        """Get the AnVIL API url that is called by the anvil_exists method."""
        return self.api_client.sam_entry_point + "/api/users/v1/" + email

    def get_api_json_response(self, email):
        id = fake.bothify(text="#" * 21)
        return {
            "googleSubjectId": id,
            "userEmail": email,
            "userSubjectId": id,
        }

    def get_view(self):
        """Return the view being tested."""
        return views.AccountLink.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

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
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_user_with_perms_can_access_view(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.UserEmailEntryForm)

    def test_can_create_an_entry(self):
        """Posting valid data to the form works as expected."""
        email = "test@example.com"
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        timestamp_lower_limit = timezone.now()
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 302)
        # A new UserEmailEntry is created.
        self.assertEqual(models.UserEmailEntry.objects.count(), 1)
        # The new UserEmailentry is linked to the logged-in user.
        new_object = models.UserEmailEntry.objects.latest("pk")
        self.assertEqual(new_object.email, email)
        self.assertEqual(new_object.user, self.user)
        self.assertIsNotNone(new_object.date_verification_email_sent)
        self.assertGreaterEqual(new_object.date_verification_email_sent, timestamp_lower_limit)
        self.assertLessEqual(new_object.date_verification_email_sent, timezone.now())
        self.assertIsNone(new_object.date_verified)
        # No account is linked.
        with self.assertRaises(ObjectDoesNotExist):
            new_object.verified_account
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")
        # API call to AnVIL is made.

    def test_success_message(self):
        """A success message is added."""
        email = "test@example.com"
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLink.success_message)

    def test_redirect(self):
        """View redirects to the correct URL."""
        email = "test@example.com"
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertRedirects(response, reverse(settings.LOGIN_REDIRECT_URL))

    @override_settings(ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountAdapter")
    def test_redirect_custom(self):
        """View redirects to the correct URL."""
        email = "test@example.com"
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        # import ipdb; ipdb.set_trace()
        self.assertRedirects(response, reverse("test_login"))

    # This test occasionally fails if the time flips one second between sending the email and
    # regenerating the token. Use freezegun's freeze_time decorator to fix the time and avoid
    # this spurious failure.
    @freeze_time("2022-11-22 03:12:34")
    def test_email_is_sent(self):
        """An email is sent when the form is submitted correctly."""
        email = "test@example.com"
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        # Need a client because messages are added.
        self.client.force_login(self.user)
        self.client.post(self.get_url(), {"email": email})
        email_entry = models.UserEmailEntry.objects.get(email=email)
        # One message has been sent.
        self.assertEqual(len(mail.outbox), 1)
        # The subject is correct.
        self.assertEqual(mail.outbox[0].subject, "Verify your AnVIL account email")
        url = "http://example.com" + reverse(
            "anvil_consortium_manager:accounts:verify",
            args=[email_entry.uuid, account_verification_token.make_token(email_entry)],
        )
        # The body contains the correct url.
        self.assertIn(url, mail.outbox[0].body)

    @freeze_time("2022-11-22 03:12:34")
    @override_settings(ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountAdapter")
    def test_email_is_sent_custom_subject(self):
        """An email is sent when the form is submitted correctly."""
        email = "test@example.com"
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        # Need a client because messages are added.
        self.client.force_login(self.user)
        self.client.post(self.get_url(), {"email": email})
        # One message has been sent.
        self.assertEqual(len(mail.outbox), 1)
        # The subject is correct.
        self.assertEqual(mail.outbox[0].subject, "custom subject")

    @freeze_time("2022-11-22 03:12:34")
    def test_email_is_sent_site_domain(self):
        """An email is sent when the form is submitted correctly."""
        site = Site.objects.create(domain="foobar.com", name="test")
        site.save()
        with self.settings(SITE_ID=site.id):
            email = "test@example.com"
            api_url = self.get_api_url(email)
            self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
            # Need a client because messages are added.
            self.client.force_login(self.user)
            self.client.post(self.get_url(), {"email": email})
            email_entry = models.UserEmailEntry.objects.get(email=email)
            # One message has been sent.
            self.assertEqual(len(mail.outbox), 1)
            url = "http://foobar.com" + reverse(
                "anvil_consortium_manager:accounts:verify",
                args=[email_entry.uuid, account_verification_token.make_token(email_entry)],
            )
            # The body contains the correct url.
            self.assertIn(url, mail.outbox[0].body)

    def test_get_user_already_linked_to_an_existing_verified_account(self):
        """View redirects with a message when the user already has an AnVIL account linked."""
        account = factories.AccountFactory.create(user=self.user, verified=True)
        email_entry = account.verified_email_entry
        # No API call should be made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No email is sent.
        self.assertEqual(len(mail.outbox), 0)
        # No new entry is created.
        self.assertEqual(models.UserEmailEntry.objects.count(), 1)
        self.assertIn(email_entry, models.UserEmailEntry.objects.all())
        # A message is included.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLink.message_user_already_linked)

    def test_post_user_already_linked_to_an_existing_verified_account(self):
        """View redirects with a message when the user already has an AnVIL account linked."""
        account = factories.AccountFactory.create(user=self.user, verified=True)
        email_entry = account.verified_email_entry
        # No API call should be made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": "foo@bar.com"}, follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new user entry is created.
        self.assertEqual(models.UserEmailEntry.objects.count(), 1)
        self.assertEqual(models.UserEmailEntry.objects.latest("pk"), email_entry)
        # No email is sent.
        self.assertEqual(len(mail.outbox), 0)
        # A message is included.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLink.message_user_already_linked)

    def test_same_user_same_email_unverified(self):
        """A UserEmailEntry record already exists for this user and email combo, but it is not verified yet."""
        email = "test@example.com"
        original_date = timezone.now() - datetime.timedelta(days=30)
        email_entry = factories.UserEmailEntryFactory.create(
            user=self.user, email=email, date_verification_email_sent=original_date
        )
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        # Need a client because messages are added.
        timestamp_lower_limit = timezone.now()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 302)
        # No new UserEmailEntry is created.
        email_entry.refresh_from_db()
        self.assertEqual(models.UserEmailEntry.objects.count(), 1)
        self.assertIn(email_entry, models.UserEmailEntry.objects.all())
        # date_verification_email_sent is updated.
        self.assertGreater(email_entry.date_verification_email_sent, original_date)
        self.assertGreaterEqual(email_entry.date_verification_email_sent, timestamp_lower_limit)
        # An email is sent.
        self.assertEqual(len(mail.outbox), 1)
        # But it still does not have a verified account.
        with self.assertRaises(ObjectDoesNotExist):
            email_entry.verified_account
        # History is added.
        self.assertEqual(email_entry.history.count(), 2)
        self.assertEqual(email_entry.history.latest().history_type, "~")
        # API call to AnVIL is made.

    def test_account_already_linked_to_different_user_and_verified(self):
        """A different user already has already verified this email."""
        email = "test@example.com"
        other_user = User.objects.create_user(username="test2", password="test2")
        other_account = factories.AccountFactory.create(user=other_user, email=email, verified=True)
        other_email_entry = other_account.verified_email_entry
        # No API call should be made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email}, follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new UserEmailEntry is created.
        self.assertEqual(models.UserEmailEntry.objects.count(), 1)
        self.assertEqual(models.UserEmailEntry.objects.latest("pk"), other_email_entry)
        # No email is sent.
        self.assertEqual(len(mail.outbox), 0)
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLink.message_account_already_exists)

    def test_account_does_not_exist_on_anvil(self):
        """Page is reloaded with a message if the account does not exist on AnVIL."""
        email = "test@example.com"
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=404, json={"message": "mock message"})
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 200)
        # The form is valid.
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertTrue(form.is_valid())
        # No email is sent.
        self.assertEqual(len(mail.outbox), 0)
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLink.message_account_does_not_exist)
        # No new Accounts are created.
        self.assertEqual(models.Account.objects.count(), 0)
        # API call to AnVIL was made.

    def test_invalid_email(self):
        """Posting invalid data to email field returns a form error."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": "foo"})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("valid email", form.errors["email"][0])
        self.assertEqual(models.Account.objects.count(), 0)

    def test_blank_email(self):
        """Posting invalid data to email field returns a form error."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("required", form.errors["email"][0])
        self.assertEqual(models.Account.objects.count(), 0)

    def test_account_exists_with_email_but_not_linked_to_user(self):
        """An Account with this email exists but is not linked to a user."""
        email = "test@example.com"
        # Create an account with this email.
        factories.AccountFactory.create(email=email)
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        timestamp_lower_limit = timezone.now()
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 302)
        # A new UserEmailEntry is created.
        self.assertEqual(models.UserEmailEntry.objects.count(), 1)
        # The new UserEmailentry is linked to the logged-in user.
        new_object = models.UserEmailEntry.objects.latest("pk")
        self.assertEqual(new_object.email, email)
        self.assertEqual(new_object.user, self.user)
        self.assertIsNotNone(new_object.date_verification_email_sent)
        self.assertGreaterEqual(new_object.date_verification_email_sent, timestamp_lower_limit)
        self.assertLessEqual(new_object.date_verification_email_sent, timezone.now())
        self.assertIsNone(new_object.date_verified)
        # No account is linked.
        with self.assertRaises(ObjectDoesNotExist):
            new_object.verified_account
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")
        # One message has been sent.
        self.assertEqual(len(mail.outbox), 1)
        # The subject is correct.
        self.assertEqual(mail.outbox[0].subject, "Verify your AnVIL account email")

    def test_account_exists_previously_linked_to_user(self):
        """An Account with this email exists but is not linked to a user."""
        email = "test@example.com"
        # Create an account with this email, and unlink it.
        account = factories.AccountFactory.create(email=email, verified=True)
        account.unlink_user()
        # No API call should be made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email}, follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new UserEmailEntry is created.
        self.assertEqual(models.UserEmailEntry.objects.count(), 1)
        self.assertEqual(
            models.UserEmailEntry.objects.latest("pk"), account.accountuserarchive_set.first().verified_email_entry
        )
        # No email is sent.
        self.assertEqual(len(mail.outbox), 0)
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLink.message_account_already_exists)

    # This test occasionally fails if the time flips one second between sending the email and
    # regenerating the token. Use freezegun's freeze_time decorator to fix the time and avoid
    # this spurious failure.
    @freeze_time("2022-11-22 03:12:34")
    def test_user_can_enter_two_different_emails(self):
        """A user can attempt to link two different emails."""
        other_timestamp = timezone.now() - datetime.timedelta(days=30)
        other_email_entry = factories.UserEmailEntryFactory.create(
            user=self.user,
            email="other@test.com",
            date_verification_email_sent=other_timestamp,
        )
        email = "test@example.com"
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        timestamp_lower_limit = timezone.now()
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 302)
        # A new UserEmailEntry is created.
        self.assertEqual(models.UserEmailEntry.objects.count(), 2)
        self.assertIn(other_email_entry, models.UserEmailEntry.objects.all())
        # The new UserEmailentry is linked to the logged-in user.
        new_object = models.UserEmailEntry.objects.latest("pk")
        self.assertEqual(new_object.email, email)
        self.assertEqual(new_object.user, self.user)
        self.assertIsNotNone(new_object.date_verification_email_sent)
        self.assertGreaterEqual(new_object.date_verification_email_sent, timestamp_lower_limit)
        self.assertLessEqual(new_object.date_verification_email_sent, timezone.now())
        with self.assertRaises(ObjectDoesNotExist):
            new_object.verified_account
        # An email is sent using the new email.
        self.assertEqual(len(mail.outbox), 1)
        # The contents have the correct link.
        self.assertIn(str(new_object.uuid), mail.outbox[0].body)
        self.assertIn(account_verification_token.make_token(new_object), mail.outbox[0].body)
        # The timestamp on the other entry hasn't changed.
        other_email_entry.refresh_from_db()
        self.assertLess(other_email_entry.date_verification_email_sent, timestamp_lower_limit)
        self.assertEqual(other_email_entry.date_verification_email_sent, other_timestamp)
        self.assertEqual(other_email_entry.history.count(), 1)
        self.assertEqual(other_email_entry.history.latest().history_type, "+")
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")
        # API call to AnVIL is made.

    # This test occasionally fails if the time flips one second between sending the email and
    # regenerating the token. Use freezegun's freeze_time decorator to fix the time and avoid
    # this spurious failure.
    @freeze_time("2022-11-22 03:12:34")
    def test_two_different_users_can_attempt_to_link_same_email(self):
        """Two different users can enter the same email."""
        email = "test@example.com"
        other_timestamp = timezone.now() - datetime.timedelta(days=30)
        other_user = factories.UserFactory.create()
        other_email_entry = factories.UserEmailEntryFactory.create(
            user=other_user, email=email, date_verification_email_sent=other_timestamp
        )
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        timestamp_lower_limit = timezone.now()
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 302)
        # A new UserEmailEntry is created.
        self.assertEqual(models.UserEmailEntry.objects.count(), 2)
        self.assertIn(other_email_entry, models.UserEmailEntry.objects.all())
        # The new UserEmailentry is linked to the logged-in user.
        new_object = models.UserEmailEntry.objects.latest("pk")
        self.assertEqual(new_object.email, email)
        self.assertEqual(new_object.user, self.user)
        self.assertIsNotNone(new_object.date_verification_email_sent)
        self.assertGreaterEqual(new_object.date_verification_email_sent, timestamp_lower_limit)
        self.assertLessEqual(new_object.date_verification_email_sent, timezone.now())
        with self.assertRaises(ObjectDoesNotExist):
            new_object.verified_account
        # An email is sent using the new object.
        self.assertEqual(len(mail.outbox), 1)
        # The contents have the correct link.
        self.assertIn(str(new_object.uuid), mail.outbox[0].body)
        self.assertIn(account_verification_token.make_token(new_object), mail.outbox[0].body)
        # The other entry hasn't changed.
        other_email_entry.refresh_from_db()
        self.assertEqual(other_email_entry.email, email)
        self.assertEqual(other_email_entry.user, other_user)
        self.assertLess(other_email_entry.date_verification_email_sent, timestamp_lower_limit)
        self.assertEqual(other_email_entry.date_verification_email_sent, other_timestamp)
        self.assertEqual(other_email_entry.history.count(), 1)
        self.assertEqual(other_email_entry.history.latest().history_type, "+")
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    # This test occasionally fails if the time flips one second between sending the email and
    # regenerating the token. Use freezegun's freeze_time decorator to fix the time and avoid
    # this spurious failure.
    @freeze_time("2022-11-22 03:12:34")
    def test_email_case_insensitive(self):
        """Case sensitivity."""
        email = "TEST@example.com"
        original_date = timezone.now() - datetime.timedelta(days=30)
        email_entry = factories.UserEmailEntryFactory.create(
            user=self.user,
            email=email.lower(),
            date_verification_email_sent=original_date,
        )
        # API call will be made with the existing entry.
        api_url = self.get_api_url(email_entry.email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        # Need a client because messages are added.
        timestamp_lower_limit = timezone.now()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 302)
        # No new UserEmailEntry is created.
        email_entry.refresh_from_db()
        self.assertEqual(models.UserEmailEntry.objects.count(), 1)
        self.assertIn(email_entry, models.UserEmailEntry.objects.all())
        # date_verification_email_sent is updated.
        self.assertGreater(email_entry.date_verification_email_sent, original_date)
        self.assertGreaterEqual(email_entry.date_verification_email_sent, timestamp_lower_limit)
        # An email is sent.
        self.assertEqual(len(mail.outbox), 1)
        # The email has the correct link generated from the lowercase email.
        self.assertIn(str(email_entry.uuid), mail.outbox[0].body)
        self.assertIn(account_verification_token.make_token(email_entry), mail.outbox[0].body)
        # But it still does not have a verified account.
        with self.assertRaises(ObjectDoesNotExist):
            email_entry.verified_account
        # History is added.
        self.assertEqual(email_entry.history.count(), 2)
        self.assertEqual(email_entry.history.latest().history_type, "~")

    def test_api_error(self):
        """Does not create a new entry or send email if the API returns some other error."""
        email = "test@example.com"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(email),
            status=500,
            json={"message": "other error"},
        )
        # Need the client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        form = response.context["form"]
        # The form is valid...
        self.assertTrue(form.is_valid())
        # ...but there was some error from the API.
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: other error", str(messages[0]))
        # No accounts were created.
        self.assertEqual(models.UserEmailEntry.objects.count(), 0)
        # No email is sent.
        self.assertEqual(len(mail.outbox), 0)

    def test_email_associated_with_group(self):
        """Does not create a new entry or send email if the email is associated with a group."""
        email = "test@example.com"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(email),
            status=204,
        )
        # Need the client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        form = response.context["form"]
        # The form is valid...
        self.assertTrue(form.is_valid())
        # ...but there was some error from the API.
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountLink.message_account_does_not_exist, str(messages[0]))
        # No accounts were created.
        self.assertEqual(models.UserEmailEntry.objects.count(), 0)
        # No email is sent.
        self.assertEqual(len(mail.outbox), 0)


class AccountLinkVerifyTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the AccountLinkVerify view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with no special permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.ACCOUNT_LINK_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:verify", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountLinkVerify.as_view()

    def get_api_url(self, email):
        """Get the AnVIL API url that is called by the anvil_exists method."""
        return self.api_client.sam_entry_point + "/api/users/v1/" + email

    def get_api_json_response(self, email):
        id = fake.bothify(text="#" * 21)
        return {
            "googleSubjectId": id,
            "userEmail": email,
            "userSubjectId": id,
        }

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        uuid = uuid4()
        response = self.client.get(self.get_url(uuid, "bar"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(uuid, "bar"),
        )

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(uuid4(), "bar"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(uuid4(), "bar"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_user_with_perms_can_verify_email(self):
        """A user can successfully verify their email."""
        email = "test@example.com"
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
        token = account_verification_token.make_token(email_entry)
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        timestamp_threshold = timezone.now()
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # A new account is created.
        self.assertEqual(models.Account.objects.count(), 1)
        new_object = models.Account.objects.latest("pk")
        self.assertEqual(new_object.email, email)
        self.assertEqual(new_object.user, self.user)
        self.assertFalse(new_object.is_service_account)
        self.assertEqual(new_object.verified_email_entry, email_entry)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")
        # The UserEmailEntry is linked to this account.
        email_entry.refresh_from_db()
        self.assertEqual(email_entry.verified_account, new_object)
        self.assertIsNotNone(email_entry.date_verified)
        self.assertGreaterEqual(email_entry.date_verified, timestamp_threshold)
        self.assertLessEqual(email_entry.date_verified, timezone.now())
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_success)

    def test_after_account_verification_hook_called(self):
        with patch.object(get_account_adapter(), "after_account_verification") as mock_verify_function:
            email = "test@example.com"
            email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
            token = account_verification_token.make_token(email_entry)
            api_url = self.get_api_url(email)
            self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
            # Need a client because messages are added.
            self.client.force_login(self.user)
            response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)

            # Assert success
            self.assertEqual(response.status_code, 200)

            # Verify hook called
            mock_verify_function.assert_called_once()

    @override_settings(
        ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountHookFailAdapter",
        ADMINS=[("Admin", "admin@example.com")],
    )
    def test_after_account_link_hook_fail_handled(self):
        with self.assertLogs("anvil_consortium_manager", level="ERROR") as log_context:
            email = "test@example.com"
            email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
            token = account_verification_token.make_token(email_entry)
            api_url = self.get_api_url(email)
            self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
            # Need a client because messages are added.
            self.client.force_login(self.user)
            response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
            account_object = models.Account.objects.latest("pk")
            # Assert success
            self.assertEqual(response.status_code, 200)

            # Verify log contents contain message from adapter exception
            self.assertIn(TestAccountHookFailAdapter.account_link_verify_exception_log_msg, log_context.output[0])
            # Verify log contents contain views log of exception caught
            self.assertIn(views.AccountLinkVerify.log_message_after_account_link_failed, log_context.output[0])

            # Get the 2nd email from the outbox
            self.assertEqual(len(mail.outbox), 2)
            email = mail.outbox[0]

            # Verify the recipient
            self.assertEqual(email.to, ["admin@example.com"])

            # Verify the subject. Note that when using mail_admins, django prefixes the subject with
            # settings.EMAIL_SUBJECT_PREFIX
            self.assertIn(
                views.AccountLinkVerify.mail_subject_after_account_link_failed,
                email.subject,
            )

            # Verify content in the email body
            error_description_string = f"Exception: {TestAccountHookFailAdapter.account_link_verify_exception_log_msg}"
            context = {
                "account": account_object,
                "email_entry": email_entry,
                "error_description": error_description_string,
                "hook": "after_account_verification",
            }
            expected_content = render_to_string(
                views.AccountLinkVerify.mail_template_after_account_link_failed, context
            )

            self.assertEqual(email.body, expected_content)

    @override_settings(ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountAdapter")
    def test_custom_redirect(self):
        """A user can successfully verify their email."""
        email = "test@example.com"
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
        token = account_verification_token.make_token(email_entry)
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_login/")

    def test_user_email_entry_does_not_exist(self):
        """ "There is no UserEmailEntry with the uuid."""
        token = "foo"
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(uuid4(), token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new accounts are created.
        self.assertEqual(models.Account.objects.count(), 0)
        # No UserEmailEntry objects exist.
        self.assertEqual(models.UserEmailEntry.objects.count(), 0)
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_link_invalid)

    def test_this_user_already_verified_this_email(self):
        """The user has already verified their email."""
        email = "test@example.com"
        account = factories.AccountFactory.create(user=self.user, email=email, verified=True)
        email_entry = account.verified_email_entry
        token = account_verification_token.make_token(email_entry)
        # No API calls are made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new accounts are created.
        self.assertEqual(models.Account.objects.count(), 1)
        self.assertEqual(account, models.Account.objects.latest("pk"))
        # The exsting email entry object is not changed -- no history is added.
        self.assertEqual(email_entry.history.count(), 1)
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_already_linked)

    def test_user_already_verified_different_email(self):
        """The user already verified a different email."""
        email = "test@example.com"
        existing_account = factories.AccountFactory.create(user=self.user, email="foo@bar.com", verified=True)
        existing_email_entry = existing_account.verified_email_entry
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
        token = account_verification_token.make_token(email_entry)
        # No API calls are made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new accounts are created.
        self.assertEqual(models.Account.objects.count(), 1)
        self.assertEqual(existing_account, models.Account.objects.latest("pk"))
        # The exsting email entry object is not changed -- no history is added.
        self.assertEqual(existing_email_entry.history.count(), 1)
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_already_linked)

    def test_token_does_not_match(self):
        """The token does not match."""
        other_email_entry = factories.UserEmailEntryFactory.create(user=self.user, email="foo@bar.com")
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email="test@example.com")
        # Use the uid from this email entry, but the token from the other email entry.
        token = account_verification_token.make_token(other_email_entry)
        # No API calls are made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No accounts are created.
        self.assertEqual(models.Account.objects.count(), 0)
        # The email entry objects are not changed -- no history is added.
        self.assertEqual(email_entry.history.count(), 1)
        self.assertEqual(other_email_entry.history.count(), 1)
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_link_invalid)

    def test_account_exists_in_app_never_linked_to_user(self):
        """The email already has an Account in the app, but it was never verified by a user."""
        email = "test@example.com"
        # Create an unverified account.
        account = factories.AccountFactory.create(email=email)
        # Create an email entry and a token for this user.
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
        token = account_verification_token.make_token(email_entry)
        # Set up the API call.
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        timestamp_threshold = timezone.now()
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new accounts are created.
        self.assertEqual(models.Account.objects.count(), 1)
        self.assertIn(account, models.Account.objects.all())
        account.refresh_from_db()
        self.assertEqual(account.email, email)
        self.assertEqual(account.user, self.user)
        self.assertFalse(account.is_service_account)
        self.assertEqual(account.verified_email_entry, email_entry)
        self.assertEqual(account.status, models.Account.ACTIVE_STATUS)
        # The UserEmailEntry is linked to this account.
        email_entry.refresh_from_db()
        self.assertEqual(email_entry.verified_account, account)
        self.assertIsNotNone(email_entry.date_verified)
        self.assertGreaterEqual(email_entry.date_verified, timestamp_threshold)
        self.assertLessEqual(email_entry.date_verified, timezone.now())
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_success)

    def test_account_exists_in_app_unlinked_from_user(self):
        email = "test@example.com"
        # Create an account that had previously been verified and then unlinked from the original user.
        account = factories.AccountFactory.create(email=email, verified=True)
        account.unlink_user()
        # Create an email entry and a token for this user.
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
        token = account_verification_token.make_token(email_entry)
        # No API calls are made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new accounts are created.
        self.assertEqual(models.Account.objects.count(), 1)
        self.assertIn(account, models.Account.objects.all())
        account.refresh_from_db()
        # The existing account has not been changed.
        self.assertIsNone(account.user)
        self.assertIsNone(account.verified_email_entry)
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_account_already_exists)

    def test_account_exists_in_app_is_service_account(self):
        email = "test@example.com"
        # Create an account that had previously been verified and then unlinked from the original user.
        account = factories.AccountFactory.create(email=email, is_service_account=True)
        # Create an email entry and a token for this user.
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
        token = account_verification_token.make_token(email_entry)
        # No API calls are made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new accounts are created.
        self.assertEqual(models.Account.objects.count(), 1)
        self.assertIn(account, models.Account.objects.all())
        account.refresh_from_db()
        # The existing account has not been changed.
        self.assertIsNone(account.user)
        self.assertIsNone(account.verified_email_entry)
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_service_account)

    def test_account_exists_in_app_deactivated_never_linked_to_user(self):
        """The email already has a deactivated Account in the app, but it was never verified by a user."""
        email = "test@example.com"
        # Create an unverified account.
        account = factories.AccountFactory.create(email=email)
        account.deactivate()
        # Create an email entry and a token for this user.
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
        token = account_verification_token.make_token(email_entry)
        # Set up the API call.
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        timestamp_threshold = timezone.now()
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new accounts are created.
        self.assertEqual(models.Account.objects.count(), 1)
        self.assertIn(account, models.Account.objects.all())
        account.refresh_from_db()
        self.assertEqual(account.email, email)
        self.assertEqual(account.user, self.user)
        self.assertFalse(account.is_service_account)
        self.assertEqual(account.verified_email_entry, email_entry)
        self.assertEqual(account.status, models.Account.INACTIVE_STATUS)
        # The UserEmailEntry is linked to this account.
        email_entry.refresh_from_db()
        self.assertEqual(email_entry.verified_account, account)
        self.assertIsNotNone(email_entry.date_verified)
        self.assertGreaterEqual(email_entry.date_verified, timestamp_threshold)
        self.assertLessEqual(email_entry.date_verified, timezone.now())
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_success)

    def test_account_exists_in_app_deactivated_unlinked_from_user(self):
        email = "test@example.com"
        # Create an account that had previously been verified and then unlinked from the original user.
        account = factories.AccountFactory.create(email=email, verified=True)
        account.unlink_user()
        account.deactivate()
        # Create an email entry and a token for this user.
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
        token = account_verification_token.make_token(email_entry)
        # No API calls are made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new accounts are created.
        self.assertEqual(models.Account.objects.count(), 1)
        self.assertIn(account, models.Account.objects.all())
        account.refresh_from_db()
        # The existing account has not been changed.
        self.assertIsNone(account.user)
        self.assertIsNone(account.verified_email_entry)
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_account_already_exists)

    def test_different_user_verified_this_email(self):
        """The email has already been verified by a different user."""
        email = "test@example.com"
        other_user = factories.UserFactory.create()
        # Create an email entry record for both users with the same email
        other_account = factories.AccountFactory.create(user=other_user, email=email, verified=True)
        other_email_entry = other_account.verified_email_entry
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
        token = account_verification_token.make_token(email_entry)
        # No API calls are made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No new accounts are created.
        self.assertEqual(models.Account.objects.count(), 1)
        self.assertEqual(other_account, models.Account.objects.latest("pk"))
        # The existing account has not been changed.
        other_account.refresh_from_db()
        self.assertEqual(other_account.user, other_user)
        self.assertEqual(other_account.history.count(), 1)
        # The email entry objects are not changed -- no history is added.
        self.assertEqual(email_entry.history.count(), 1)
        self.assertEqual(other_email_entry.history.count(), 1)
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_account_already_exists)

    def test_anvil_account_no_longer_exists(self):
        """The email no longer has an associated AnVIL account."""
        email_entry = factories.UserEmailEntryFactory.create()
        api_url = self.get_api_url(email_entry.email)
        self.anvil_response_mock.add(responses.GET, api_url, status=404, json={"message": "mock message"})
        token = account_verification_token.make_token(email_entry)
        # No API calls are made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No accounts are created.
        self.assertEqual(models.Account.objects.count(), 0)
        # The email_entry object was not updated.
        email_entry.refresh_from_db()
        self.assertIsNone(email_entry.date_verified)
        with self.assertRaises(ObjectDoesNotExist):
            email_entry.verified_account
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_account_does_not_exist)

    def test_email_associated_with_group(self):
        """The email is associated with a group on AnVIL."""
        email_entry = factories.UserEmailEntryFactory.create()
        api_url = self.get_api_url(email_entry.email)
        self.anvil_response_mock.add(responses.GET, api_url, status=204)
        token = account_verification_token.make_token(email_entry)
        # No API calls are made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No accounts are created.
        self.assertEqual(models.Account.objects.count(), 0)
        # The email_entry object was not updated.
        email_entry.refresh_from_db()
        self.assertIsNone(email_entry.date_verified)
        with self.assertRaises(ObjectDoesNotExist):
            email_entry.verified_account
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), views.AccountLinkVerify.message_account_does_not_exist)

    def test_api_call_fails(self):
        """The API call to AnVIL fails."""
        email_entry = factories.UserEmailEntryFactory.create()
        api_url = self.get_api_url(email_entry.email)
        self.anvil_response_mock.add(responses.GET, api_url, status=500, json={"message": "other error"})
        token = account_verification_token.make_token(email_entry)
        # No API calls are made, so do not add a mocked response.
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
        self.assertRedirects(response, "/test_home/")
        # No accounts are created.
        self.assertEqual(models.Account.objects.count(), 0)
        # The email_entry object was not updated.
        email_entry.refresh_from_db()
        self.assertIsNone(email_entry.date_verified)
        with self.assertRaises(ObjectDoesNotExist):
            email_entry.verified_account
        # A message is added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: other error", str(messages[0]))

    def test_no_notification_email(self):
        """Notification email is not sent if account_verification_notification_email is not set"""
        email = "test@example.com"
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
        token = account_verification_token.make_token(email_entry)
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token))
        self.assertEqual(response.status_code, 302)
        # No email is sent.
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountAdapter")
    def test_notification_email(self):
        """Notification email is sent if account_verification_notification_email set."""
        email = "test1@example.com"
        email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
        token = account_verification_token.make_token(email_entry)
        api_url = self.get_api_url(email)
        self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(email_entry.uuid, token))
        self.assertEqual(response.status_code, 302)
        # An email is sent.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(len(mail.outbox[0].to), 1)
        self.assertIn("test@example.com", mail.outbox[0].to)

    @override_settings(
        ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountAdapter",
        ADMINS=[("Admin", "admin@example.com")],
    )
    @patch.object(
        TestAccountAdapter,
        "send_account_verification_notification_email",
    )
    def test_send_account_verification_notification_email_hook_fail_handled(self, mock):
        error_message = "send_account_verification_notification_email:test_exception"
        mock.side_effect = Exception(error_message)
        with self.assertLogs("anvil_consortium_manager", level="ERROR") as log_context:
            email = "test@example.com"
            email_entry = factories.UserEmailEntryFactory.create(user=self.user, email=email)
            token = account_verification_token.make_token(email_entry)
            api_url = self.get_api_url(email)
            self.anvil_response_mock.add(responses.GET, api_url, status=200, json=self.get_api_json_response(email))
            # Need a client because messages are added.
            self.client.force_login(self.user)
            response = self.client.get(self.get_url(email_entry.uuid, token), follow=True)
            account_object = models.Account.objects.latest("pk")
            # Assert success
            self.assertEqual(response.status_code, 200)

            # Verify log contents contain message from adapter exception
            self.assertIn(error_message, log_context.output[0])
            # Verify log contents contain views log of exception caught
            self.assertIn(
                views.AccountLinkVerify.log_message_send_account_verification_notification_email_failed,
                log_context.output[0],
            )

            # Only one the error notification email was sent because the hook failed.
            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]

            # Verify the recipient
            self.assertEqual(email.to, ["admin@example.com"])

            # Verify the subject. Note that when using mail_admins, django prefixes the subject with
            # settings.EMAIL_SUBJECT_PREFIX
            self.assertIn(
                views.AccountLinkVerify.mail_subject_send_account_verification_notification_email_failed,
                email.subject,
            )

            # Verify content in the email body
            error_description_string = f"Exception: {error_message}"
            context = {
                "account": account_object,
                "email_entry": email_entry,
                "error_description": error_description_string,
                "hook": "send_account_verification_notification_email",
            }
            expected_content = render_to_string(
                views.AccountLinkVerify.mail_template_send_account_verification_notification_email_failed, context
            )

            self.assertEqual(email.body, expected_content)


class AccountListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountList.as_view()

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
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.AccountStaffTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.AccountFactory()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.AccountFactory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_filterset_class(self):
        factories.AccountFactory.create(email="account_test1@example.com")
        factories.AccountFactory.create(email="account@example.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("filter", response.context_data)
        self.assertIsInstance(response.context_data["filter"], filters.AccountListFilter)

    def test_view_with_filter_return_no_object(self):
        factories.AccountFactory.create(email="account_test1@example.com")
        factories.AccountFactory.create(email="account@example.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_returns_one_object_exact(self):
        instance = factories.AccountFactory.create(email="account_test1@example.com")
        factories.AccountFactory.create(email="account@example.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "account_test1@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_case_insensitive(self):
        instance = factories.AccountFactory.create(email="account_Test1@example.com")
        factories.AccountFactory.create(email="account@example.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "account_test1@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_contains(self):
        instance = factories.AccountFactory.create(email="account_test1@example.com")
        factories.AccountFactory.create(email="account@example.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "test1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_status(self):
        factories.AccountFactory.create(email="account1@example.com", status=models.Account.ACTIVE_STATUS)
        factories.AccountFactory.create(email="account2@example.com", status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "account"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_filter_returns_all_objects(self):
        factories.AccountFactory.create(email="account1@example.com")
        factories.AccountFactory.create(email="account2@example.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "example"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_service_account(self):
        factories.AccountFactory.create(is_service_account=True)
        factories.AccountFactory.create(is_service_account=False)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_active_and_inactive_accounts(self):
        """Includes both active and inactive accounts."""
        active_object = factories.AccountFactory.create()
        inactive_object = factories.AccountFactory.create()
        inactive_object.deactivate()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)
        self.assertIn(active_object, response.context_data["table"].data)
        self.assertIn(inactive_object, response.context_data["table"].data)

    @override_settings(ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountAdapter")
    def test_adapter(self):
        """Displays the correct table if specified in the adapter."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], app_tables.TestAccountStaffTable)
        self.assertIsInstance(response.context_data["filter"], TestAccountListFilter)


class AccountActiveListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:list_active", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountActiveList.as_view()

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
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.AccountStaffTable)

    def test_filterset_class(self):
        factories.AccountFactory.create(email="account_test1@example.com")
        factories.AccountFactory.create(email="account@example.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("filter", response.context_data)
        self.assertIsInstance(response.context_data["filter"], filters.AccountListFilter)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.AccountFactory()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.AccountFactory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_filter_return_no_object(self):
        factories.AccountFactory.create(email="account_test1@example.com", status=models.Account.ACTIVE_STATUS)
        factories.AccountFactory.create(email="account@example.com", status=models.Account.ACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_returns_one_object_exact(self):
        instance = factories.AccountFactory.create(
            email="account_test1@example.com", status=models.Account.ACTIVE_STATUS
        )
        factories.AccountFactory.create(email="account@example.com", status=models.Account.ACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "account_test1@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_case_insensitive(self):
        instance = factories.AccountFactory.create(
            email="account_Test1@example.com", status=models.Account.ACTIVE_STATUS
        )
        factories.AccountFactory.create(email="account@example.com", status=models.Account.ACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "account_test1@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_active_only(self):
        instance = factories.AccountFactory.create(email="account1@example.com", status=models.Account.ACTIVE_STATUS)
        factories.AccountFactory.create(email="account2@example.com", status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "account"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_contains(self):
        instance = factories.AccountFactory.create(
            email="account_test1@example.com", status=models.Account.ACTIVE_STATUS
        )
        factories.AccountFactory.create(email="account@example.com", status=models.Account.ACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "test1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_all_objects(self):
        factories.AccountFactory.create(email="account1@example.com", status=models.Account.ACTIVE_STATUS)
        factories.AccountFactory.create(email="account2@example.com", status=models.Account.ACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "example"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_service_account(self):
        factories.AccountFactory.create(is_service_account=True)
        factories.AccountFactory.create(is_service_account=False)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_active_and_inactive_accounts(self):
        """Includes both active and inactive accounts."""
        active_object = factories.AccountFactory.create()
        inactive_object = factories.AccountFactory.create()
        inactive_object.deactivate()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(active_object, response.context_data["table"].data)
        self.assertNotIn(inactive_object, response.context_data["table"].data)

    @override_settings(ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountAdapter")
    def test_adapter(self):
        """Displays the correct table if specified in the adapter."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], app_tables.TestAccountStaffTable)
        self.assertIsInstance(response.context_data["filter"], TestAccountListFilter)


class AccountInactiveListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:list_inactive", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountInactiveList.as_view()

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
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.AccountStaffTable)

    def test_filterset_class(self):
        factories.AccountFactory.create(email="account_test1@example.com")
        factories.AccountFactory.create(email="account@example.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("filter", response.context_data)
        self.assertIsInstance(response.context_data["filter"], filters.AccountListFilter)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.AccountFactory(status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.AccountFactory.create_batch(2, status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_filter_return_no_object(self):
        factories.AccountFactory.create(email="account1@example.com", status=models.Account.INACTIVE_STATUS)
        factories.AccountFactory.create(email="account2@example.com", status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_returns_one_object_exact(self):
        instance = factories.AccountFactory.create(email="account1@example.com", status=models.Account.INACTIVE_STATUS)
        factories.AccountFactory.create(email="account2@example.com", status=models.Account.ACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "account1@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_case_insensitive(self):
        instance = factories.AccountFactory.create(email="account1@example.com", status=models.Account.INACTIVE_STATUS)
        factories.AccountFactory.create(email="account2@example.com", status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "Account1@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_inactive_only(self):
        instance = factories.AccountFactory.create(email="account1@example.com", status=models.Account.INACTIVE_STATUS)
        factories.AccountFactory.create(email="account2@example.com", status=models.Account.ACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "account"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_contains(self):
        instance = factories.AccountFactory.create(email="account1@example.com", status=models.Account.INACTIVE_STATUS)
        factories.AccountFactory.create(email="account2@example.com", status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "account1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_all_objects(self):
        factories.AccountFactory.create(email="account1@example.com", status=models.Account.INACTIVE_STATUS)
        factories.AccountFactory.create(email="account2@example.com", status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"email__icontains": "example"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_service_account(self):
        factories.AccountFactory.create(status=models.Account.INACTIVE_STATUS, is_service_account=True)
        factories.AccountFactory.create(status=models.Account.INACTIVE_STATUS, is_service_account=False)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_active_and_inactive_accounts(self):
        """Includes both active and inactive accounts."""
        active_object = factories.AccountFactory.create()
        inactive_object = factories.AccountFactory.create()
        inactive_object.deactivate()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertNotIn(active_object, response.context_data["table"].data)
        self.assertIn(inactive_object, response.context_data["table"].data)

    @override_settings(ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountAdapter")
    def test_adapter(self):
        """Displays the correct table if specified in the adapter."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], app_tables.TestAccountStaffTable)
        self.assertIsInstance(response.context_data["filter"], TestAccountListFilter)


class AccountDeleteTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountDelete.as_view()

    def get_api_remove_from_group_url(self, group_name, account_email):
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member/" + account_email

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        uuid = uuid4()
        # Need a client for redirects.
        response = self.client.get(self.get_url(uuid))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(uuid))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertEqual(response.status_code, 200)

    def test_template_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=uuid)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(uuid4()))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=uuid)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, uuid=uuid)

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        object = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 0)
        # History is added.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        object = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountDelete.success_message, str(messages[0]))

    def test_view_deletes_object_service_account(self):
        """Posting submit to the form successfully deletes the service account object."""
        object = factories.AccountFactory.create(is_service_account=True)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 0)

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.AccountFactory.create()
        other_object = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 1)
        self.assertQuerySetEqual(
            models.Account.objects.all(),
            models.Account.objects.filter(pk=other_object.pk),
        )

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.AccountFactory.create()
        # Need to use the client instead of RequestFactory to check redirection url.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("anvil_consortium_manager:accounts:list"))

    def test_removes_account_from_one_group(self):
        """Deleting an account from the app also removes it from one group."""
        object = factories.AccountFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(account=object)
        group = membership.group
        remove_from_group_url = self.get_api_remove_from_group_url(group.name, object.email)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url, status=204)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 0)
        # Also removes the user from groups.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_removes_account_from_all_groups(self):
        """Deleting an account from the app also removes it from all groups that it is in."""
        object = factories.AccountFactory.create()
        memberships = factories.GroupAccountMembershipFactory.create_batch(2, account=object)
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(group_1.name, object.email)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_1, status=204)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(group_2.name, object.email)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_2, status=204)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 0)
        # Also removes the user from groups.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_when_removing_account_from_groups(self):
        """Message when an API error occurred when removing a user from a group."""
        object = factories.AccountFactory.create()
        memberships = factories.GroupAccountMembershipFactory.create_batch(2, account=object)
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(group_1.name, object.email)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_1, status=204)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(group_2.name, object.email)
        self.anvil_response_mock.add(
            responses.DELETE,
            remove_from_group_url_2,
            status=409,
            json={"message": "test error"},
        )
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""}, follow=True)
        self.assertRedirects(response, object.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.AccountDelete.message_error_removing_from_groups.format("test error"),
            str(messages[0]),
        )
        # The Account is not deleted.
        self.assertEqual(models.Account.objects.count(), 1)
        models.Account.objects.get(pk=object.pk)
        # Does not remove the user from any groups.
        # Removes the user from only the groups where the API call succeeded.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        self.assertNotIn(memberships[0], models.GroupAccountMembership.objects.all())
        self.assertIn(memberships[1], models.GroupAccountMembership.objects.all())


class AccountDeactivateTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:deactivate", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountDeactivate.as_view()

    def get_api_remove_from_group_url(self, group_name, account_email):
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member/" + account_email

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        uuid = uuid4()
        response = self.client.get(self.get_url(uuid))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(uuid))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertEqual(response.status_code, 200)

    def test_template_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=uuid)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(uuid4()))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=uuid)

    def test_get_context_data(self):
        """Context data is correct."""
        object = factories.AccountFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(account=object)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(object.uuid))
        self.assertIn("group_table", response.context_data)
        table = response.context_data["group_table"]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(membership, table.data)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, uuid=uuid)

    def test_view_deactivates_object(self):
        """Posting submit to the form successfully deactivates the object."""
        object = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        object.refresh_from_db()
        self.assertEqual(object.status, object.INACTIVE_STATUS)
        self.assertTrue(object.deactivate_date)
        # History is added.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "~")

    def test_success_message(self):
        """Response includes a success message if successful."""
        object = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountDeactivate.success_message, str(messages[0]))

    def test_view_deactivates_object_service_account(self):
        """Posting submit to the form successfully deactivates a service account object."""
        object = factories.AccountFactory.create(is_service_account=True)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        object.refresh_from_db()
        self.assertEqual(object.status, object.INACTIVE_STATUS)
        self.assertTrue(object.deactivate_date)

    def test_only_deactivates_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.AccountFactory.create()
        other_object = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 2)
        other_object.refresh_from_db()
        self.assertEqual(other_object.status, other_object.ACTIVE_STATUS)

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.AccountFactory.create()
        # Need to use the client instead of RequestFactory to check redirection url.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("anvil_consortium_manager:accounts:detail", args=[object.uuid]),
        )

    def test_removes_account_from_one_group(self):
        """Deactivating an account from the app also removes it from one group on AnVIL."""
        object = factories.AccountFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(account=object)
        group = membership.group
        remove_from_group_url = self.get_api_remove_from_group_url(group.name, object.email)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url, status=204)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        # Memberships are deleted from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)
        # History for group-account membership is *not* added.
        self.assertEqual(models.GroupAccountMembership.history.count(), 2)

    def test_removes_account_from_all_groups(self):
        """Deactivating an account from the app also removes it from all groups that it is in."""
        object = factories.AccountFactory.create()
        memberships = factories.GroupAccountMembershipFactory.create_batch(2, account=object)
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(group_1.name, object.email)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_1, status=204)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(group_2.name, object.email)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_2, status=204)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        # Status was updated.
        object.refresh_from_db()
        self.assertEqual(object.status, object.INACTIVE_STATUS)
        # Memberships are deleted from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_when_removing_account_from_groups(self):
        """Message when an API error occurred when removing a user from a group."""
        object = factories.AccountFactory.create()
        memberships = factories.GroupAccountMembershipFactory.create_batch(2, account=object)
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(group_1.name, object.email)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_1, status=204)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(group_2.name, object.email)
        self.anvil_response_mock.add(
            responses.DELETE,
            remove_from_group_url_2,
            status=409,
            json={"message": "test error"},
        )
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""}, follow=True)
        self.assertRedirects(response, object.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.AccountDeactivate.message_error_removing_from_groups.format("test error"),
            str(messages[0]),
        )
        # The Account is not marked as inactive.
        object.refresh_from_db()
        self.assertEqual(object.status, object.ACTIVE_STATUS)
        # Removes the user from only the groups where the API call succeeded.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        self.assertNotIn(memberships[0], models.GroupAccountMembership.objects.all())
        self.assertIn(memberships[1], models.GroupAccountMembership.objects.all())

    def test_account_already_inactive_get(self):
        """Redirects with a message if account is already deactivated."""
        object = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create_batch(2, account=object)
        object.status = object.INACTIVE_STATUS
        object.save()
        # No API calls are made.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(object.uuid), follow=True)
        self.assertRedirects(response, object.get_absolute_url())
        # The object is unchanged.
        object.refresh_from_db()
        self.assertEqual(object.status, object.INACTIVE_STATUS)
        # Memberships are *not* deleted from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        # A message is shown.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountDeactivate.message_already_inactive, str(messages[0]))

    def test_account_already_inactive_post(self):
        """Redirects with a message if account is already deactivated."""
        object = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create_batch(2, account=object)
        object.status = object.INACTIVE_STATUS
        object.save()
        # No API calls are made.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""}, follow=True)
        self.assertRedirects(response, object.get_absolute_url())
        # The object is unchanged.
        object.refresh_from_db()
        self.assertEqual(object.status, object.INACTIVE_STATUS)
        # Memberships are *not* deleted from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        # A message is shown.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountDeactivate.message_already_inactive, str(messages[0]))


class AccountReactivateTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:reactivate", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountReactivate.as_view()

    def get_api_add_to_group_url(self, group_name, account_email):
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member/" + account_email

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        uuid = uuid4()
        response = self.client.get(self.get_url(uuid))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(uuid))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        obj.status = obj.INACTIVE_STATUS
        obj.save()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertEqual(response.status_code, 200)

    def test_template_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        obj.status = obj.INACTIVE_STATUS
        obj.save()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=uuid)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(uuid4()))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=uuid)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, pk=uuid)

    def test_get_context_data(self):
        """Context data is correct."""
        object = factories.AccountFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(account=object)
        object.status = object.INACTIVE_STATUS
        object.save()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(object.uuid))
        self.assertIn("group_table", response.context_data)
        table = response.context_data["group_table"]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(membership, table.data)

    def test_view_reactivates_object(self):
        """Posting submit to the form successfully deactivates the object."""
        object = factories.AccountFactory.create()
        object.status = object.INACTIVE_STATUS
        object.save()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        object.refresh_from_db()
        self.assertEqual(object.status, object.ACTIVE_STATUS)
        # History is added.
        self.assertEqual(object.history.count(), 3)
        self.assertEqual(object.history.latest().history_type, "~")

    def test_success_message(self):
        """Response includes a success message if successful."""
        object = factories.AccountFactory.create()
        object.status = object.INACTIVE_STATUS
        object.save()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountReactivate.success_message, str(messages[0]))

    def test_view_reactivates_object_service_account(self):
        """Posting submit to the form successfully reactivates a service account object."""
        object = factories.AccountFactory.create(is_service_account=True)
        object.status = object.INACTIVE_STATUS
        object.save()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        object.refresh_from_db()
        self.assertEqual(object.status, object.ACTIVE_STATUS)

    def test_only_reactivates_specified_pk(self):
        """View only reactivates the specified pk."""
        object = factories.AccountFactory.create()
        object.status = object.INACTIVE_STATUS
        object.save()
        other_object = factories.AccountFactory.create()
        other_object.status = other_object.INACTIVE_STATUS
        other_object.save()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 2)
        other_object.refresh_from_db()
        self.assertEqual(other_object.status, other_object.INACTIVE_STATUS)

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.AccountFactory.create()
        object.status = object.INACTIVE_STATUS
        object.save()
        # Need to use the client instead of RequestFactory to check redirection url.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("anvil_consortium_manager:accounts:detail", args=[object.uuid]),
        )

    def test_account_already_active_get(self):
        """Redirects with a message if account is already active."""
        object = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create_batch(2, account=object)
        # No API calls are made.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(object.uuid), follow=True)
        self.assertRedirects(response, object.get_absolute_url())
        # The object is unchanged.
        object.refresh_from_db()
        self.assertEqual(object.status, object.ACTIVE_STATUS)
        # A message is shown.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountReactivate.message_already_active, str(messages[0]))

    def test_account_already_active_post(self):
        """Redirects with a message if account is already deactivated."""
        object = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create_batch(2, account=object)
        # No API calls are made.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""}, follow=True)
        self.assertRedirects(response, object.get_absolute_url())
        # The object is unchanged.
        object.refresh_from_db()
        self.assertEqual(object.status, object.ACTIVE_STATUS)
        # Memberships are *not* deleted from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        # A message is shown.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountReactivate.message_already_active, str(messages[0]))


class AccountUnlinkUserTest(TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:unlink", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountUnlinkUser.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        uuid = uuid4()
        response = self.client.get(self.get_url(uuid))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(uuid))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        instance = factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(instance.uuid))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=uuid)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        uuid = uuid4()
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(uuid))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=uuid)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=uuid)

    def test_get_context_data(self):
        """Context data is correct."""
        instance = factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(instance.uuid))
        self.assertIn("object", response.context_data)
        self.assertEqual(instance, response.context_data["object"])

    def test_view_with_invalid_object(self):
        """Returns a 404 when the object doesn't exist."""
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, uuid=uuid)

    def test_unlinks_user(self):
        """Successful post request unlinks the user from the account."""
        instance = factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        self.assertEqual(instance.user, None)
        self.assertEqual(instance.verified_email_entry, None)

    def test_unlinks_user_not_verified(self):
        """Successful post request unlinks the user from the account."""
        instance = factories.AccountFactory.create()
        user = factories.UserFactory.create()
        instance.user = user
        instance.save()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        self.assertEqual(instance.user, None)
        self.assertEqual(instance.verified_email_entry, None)

    def test_adds_user_to_unlinked_users(self):
        """A record is added to unlinked_users."""
        instance = factories.AccountFactory.create(verified=True)
        verified_email_entry = instance.verified_email_entry
        user = instance.user
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        # User link was archived.
        self.assertIn(user, instance.unlinked_users.all())
        self.assertEqual(models.AccountUserArchive.objects.count(), 1)
        archive = models.AccountUserArchive.objects.first()
        self.assertEqual(archive.account, instance)
        self.assertEqual(archive.user, user)
        self.assertIsNotNone(archive.created)
        self.assertEqual(archive.verified_email_entry, verified_email_entry)

    def test_adds_user_to_unlinked_users_not_verified(self):
        """A record is added to unlinked_users."""
        instance = factories.AccountFactory.create()
        user = factories.UserFactory.create()
        instance.user = user
        instance.save()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        # User link was archived.
        self.assertIn(user, instance.unlinked_users.all())
        self.assertEqual(models.AccountUserArchive.objects.count(), 1)
        archive = models.AccountUserArchive.objects.first()
        self.assertEqual(archive.account, instance)
        self.assertEqual(archive.user, user)
        self.assertIsNotNone(archive.created)
        self.assertIsNone(archive.verified_email_entry)

    def test_can_add_second_user_to_unlinked_users(self):
        """A record is added to unlinked_users."""
        old_user = User.objects.create_user(username="old_user", password="test")
        instance = factories.AccountFactory.create(verified=True)
        instance.unlinked_users.add(old_user)
        user = instance.user
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        # User link was archived.
        self.assertIn(user, instance.unlinked_users.all())
        self.assertEqual(models.AccountUserArchive.objects.count(), 2)
        models.AccountUserArchive.objects.get(account=instance, user=old_user)
        models.AccountUserArchive.objects.get(account=instance, user=user)

    def test_get_account_has_no_user_redirect(self):
        instance = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(instance.uuid), {"submit": ""})
        self.assertRedirects(response, instance.get_absolute_url())

    def test_get_account_no_user_message(self):
        # A message is included.
        instance = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(instance.uuid), {"submit": ""}, follow=True)
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountUnlinkUser.message_no_user, str(messages[0]))
        instance.refresh_from_db()
        self.assertIsNone(instance.user)

    def test_post_account_has_no_user_redirect(self):
        instance = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {"submit": ""})
        self.assertRedirects(response, instance.get_absolute_url())

    def test_post_account_no_user_message(self):
        # A message is included.
        instance = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {"submit": ""}, follow=True)
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountUnlinkUser.message_no_user, str(messages[0]))
        instance.refresh_from_db()
        self.assertIsNone(instance.user)

    def test_success_message(self):
        instance = factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {"submit": ""}, follow=True)
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountUnlinkUser.success_message, str(messages[0]))

    def test_only_unlinks_specified_instance(self):
        """View only deletes the specified pk."""
        instance = factories.AccountFactory.create(verified=True)
        other_instance = factories.AccountFactory.create(verified=True)
        other_user = other_instance.user
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 2)
        instance.refresh_from_db()
        other_instance.refresh_from_db()
        self.assertEqual(instance.user, None)
        self.assertEqual(other_instance.user, other_user)


class AccountAutocompleteTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with the correct permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:autocomplete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountAutocomplete.as_view()

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

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_returns_all_objects(self):
        """Queryset returns all objects when there is no query."""
        groups = factories.AccountFactory.create_batch(10)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 10)
        self.assertEqual(sorted(returned_ids), sorted([group.pk for group in groups]))

    def test_returns_correct_object_match(self):
        """Queryset returns the correct objects when query matches the email."""
        account = factories.AccountFactory.create(email="test@foo.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "test@foo.com"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], account.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Queryset returns the correct objects when query matches the beginning of the email."""
        account = factories.AccountFactory.create(email="test@foo.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "tes"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], account.pk)

    def test_returns_correct_object_containing_query(self):
        """Queryset returns the correct objects when the name contains the query."""
        account = factories.AccountFactory.create(email="test@foo.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "foo"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], account.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        account = factories.AccountFactory.create(email="test@foo.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "TEST@FOO.COM"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], account.pk)

    def test_does_not_return_inactive_accounts(self):
        """Queryset does not return accounts that are inactive."""
        factories.AccountFactory.create(email="test@foo.com", status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "test@foo.com"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 0)

    @override_settings(ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountAdapter")
    def test_adapter_queryset(self):
        """Filters queryset correctly if custom get_autocomplete_queryset is set in adapter."""
        account_1 = factories.AccountFactory.create(email="test@bar.com")
        account_2 = factories.AccountFactory.create(email="foo@test.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "test"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertIn(account_1.pk, returned_ids)
        self.assertNotIn(account_2.pk, returned_ids)

    @override_settings(ANVIL_ACCOUNT_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestAccountAdapter")
    def test_adapter_labels(self):
        """Test view labels."""
        account = factories.AccountFactory.create(email="test@bar.com")

        request = self.factory.get(self.get_url())
        request.user = self.user
        view = views.AccountAutocomplete()
        view.setup(request)
        self.assertEqual(view.get_result_label(account), "TEST test@bar.com")
        self.assertEqual(view.get_selected_result_label(account), "TEST test@bar.com")


class ManagedGroupDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ManagedGroupDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo"))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo"))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_status_code_with_existing_object_not_managed(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        # Only clients load the template.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.name))
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        factories.ManagedGroupFactory.create()
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, slug="foo")

    def test_workspace_table(self):
        """The workspace table exists."""
        obj = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.name))
        self.assertIn("workspace_table", response.context_data)
        self.assertIsInstance(response.context_data["workspace_table"], tables.WorkspaceGroupSharingStaffTable)

    def test_workspace_table_none(self):
        """No workspaces are shown if the group does not have access to any workspaces."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)

    def test_workspace_table_one(self):
        """One workspace is shown if the group have access to one workspace."""
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 1)

    def test_workspace_table_two(self):
        """Two workspaces are shown if the group have access to two workspaces."""
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace__name="w1", group=group)
        factories.WorkspaceGroupSharingFactory.create(workspace__name="w2", group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 2)

    def test_shows_workspace_for_only_this_group(self):
        """Only shows workspcaes that this group has access to."""
        group = factories.ManagedGroupFactory.create(name="group-1")
        other_group = factories.ManagedGroupFactory.create(name="group-2")
        factories.WorkspaceGroupSharingFactory.create(group=other_group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)

    def test_account_table(self):
        """The account table exists."""
        obj = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.name))
        self.assertIn("account_table", response.context_data)
        self.assertIsInstance(
            response.context_data["account_table"],
            tables.GroupAccountMembershipStaffTable,
        )

    def test_account_table_none(self):
        """No accounts are shown if the group has no accounts."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("account_table", response.context_data)
        self.assertEqual(len(response.context_data["account_table"].rows), 0)

    def test_account_table_one(self):
        """One accounts is shown if the group has only that account."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("account_table", response.context_data)
        self.assertEqual(len(response.context_data["account_table"].rows), 1)

    def test_account_table_two(self):
        """Two accounts are shown if the group has only those accounts."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create_batch(2, group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("account_table", response.context_data)
        self.assertEqual(len(response.context_data["account_table"].rows), 2)

    def test_account_table_shows_account_for_only_this_group(self):
        """Only shows accounts that are in this group."""
        group = factories.ManagedGroupFactory.create(name="group-1")
        other_group = factories.ManagedGroupFactory.create(name="group-2")
        factories.GroupAccountMembershipFactory.create(group=other_group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("account_table", response.context_data)
        self.assertEqual(len(response.context_data["account_table"].rows), 0)

    def test_account_table_includes_inactive_accounts(self):
        """Shows inactive accounts in the table. Not that this would represent an internal data consistency issue."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account__status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("account_table", response.context_data)
        self.assertEqual(len(response.context_data["account_table"].rows), 1)

    def test_group_table(self):
        """The group table exists."""
        obj = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.name))
        self.assertIn("group_table", response.context_data)
        self.assertIsInstance(response.context_data["group_table"], tables.GroupGroupMembershipStaffTable)

    def test_group_table_none(self):
        """No groups are shown if the group has no member groups."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)

    def test_group_table_one(self):
        """One group is shown if the group has only that member group."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 1)

    def test_group_table_two(self):
        """Two groups are shown if the group has only those member groups."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(child_group__name="g1", parent_group=group)
        factories.GroupGroupMembershipFactory.create(child_group__name="g2", parent_group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 2)

    def test_group_account_for_only_this_group(self):
        """Only shows member groups that are in this group."""
        group = factories.ManagedGroupFactory.create(name="group-1")
        other_group = factories.ManagedGroupFactory.create(name="group-2")
        factories.GroupGroupMembershipFactory.create(parent_group=other_group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)

    def test_group_table_show_only_direct_members(self):
        """Only shows direct child groups and not grandchildren"""
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        grandchild = factories.ManagedGroupFactory.create()
        parent_child_membership = factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        child_grandchild_membership = factories.GroupGroupMembershipFactory.create(
            parent_group=child, child_group=grandchild
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(parent.name))
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 1)
        self.assertIn(parent_child_membership, response.context_data["group_table"].data)
        self.assertNotIn(child_grandchild_membership, response.context_data["group_table"].data)

    def test_workspace_auth_domain_table(self):
        """The auth_domain table exists."""
        obj = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.name))
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        self.assertIsInstance(
            response.context_data["workspace_authorization_domain_table"],
            tables.WorkspaceStaffTable,
        )

    def test_workspace_auth_domain_table_none(self):
        """No workspaces are shown if the group is not the auth domain for any workspace."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_authorization_domain_table"].rows), 0)

    def test_workspace_auth_domain_table_one(self):
        """One workspace is shown in if the group is the auth domain for it."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        workspace.authorization_domains.add(group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        table = response.context_data["workspace_authorization_domain_table"]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(workspace, table.data)

    def test_workspace_auth_domain_table_two(self):
        """Two workspaces are shown in if the group is the auth domain for them."""
        group = factories.ManagedGroupFactory.create()
        workspace_1 = factories.WorkspaceFactory.create(name="w1")
        workspace_1.authorization_domains.add(group)
        workspace_2 = factories.WorkspaceFactory.create(name="w2")
        workspace_2.authorization_domains.add(group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        table = response.context_data["workspace_authorization_domain_table"]
        self.assertEqual(len(table.rows), 2)
        self.assertIn(workspace_1, table.data)
        self.assertIn(workspace_2, table.data)

    def test_workspace_auth_domain_account_for_only_this_group(self):
        """Only shows workspaces for which this group is the auth domain."""
        group = factories.ManagedGroupFactory.create(name="group")
        other_group = factories.ManagedGroupFactory.create(name="other-group")
        other_workspace = factories.WorkspaceFactory.create()
        other_workspace.authorization_domains.add(other_group)
        factories.GroupGroupMembershipFactory.create(parent_group=other_group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_authorization_domain_table"].rows), 0)

    def test_parent_table(self):
        """The parent table exists."""
        obj = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.name))
        self.assertIn("parent_table", response.context_data)
        self.assertIsInstance(response.context_data["parent_table"], tables.GroupGroupMembershipStaffTable)

    def test_parent_table_none(self):
        """No groups are shown if the group is not a part of any other groups."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("parent_table", response.context_data)
        self.assertEqual(len(response.context_data["parent_table"].rows), 0)

    def test_parent_table_one(self):
        """One group is shown if the group is a part of that group."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(child_group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("parent_table", response.context_data)
        self.assertEqual(len(response.context_data["parent_table"].rows), 1)

    def test_parent_table_two(self):
        """Two groups are shown if the group is a part of both groups."""
        group = factories.ManagedGroupFactory.create(name="group")
        factories.GroupGroupMembershipFactory.create(parent_group__name="g1", child_group=group)
        factories.GroupGroupMembershipFactory.create(parent_group__name="g2", child_group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("parent_table", response.context_data)
        self.assertEqual(len(response.context_data["parent_table"].rows), 2)

    def test_parent_table_shows_only_direct_parents(self):
        """Only show only the direct parent groups"""
        grandparent = factories.ManagedGroupFactory.create()
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        grandparent_parent_membership = factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        parent_child_membership = factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(child.name))
        self.assertIn("parent_table", response.context_data)
        self.assertEqual(len(response.context_data["parent_table"].rows), 1)
        self.assertIn(parent_child_membership, response.context_data["parent_table"].data)
        self.assertNotIn(grandparent_parent_membership, response.context_data["parent_table"].data)

    def test_edit_permission(self):
        """Links to reactivate/deactivate/delete pages appear if the user has edit permission."""
        edit_user = User.objects.create_user(username="edit", password="test")
        edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )
        self.client.force_login(edit_user)
        obj = factories.ManagedGroupFactory.create()
        response = self.client.get(self.get_url(obj.name))
        self.assertIn("show_edit_links", response.context_data)
        self.assertTrue(response.context_data["show_edit_links"])
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:managed_groups:delete",
                kwargs={"slug": obj.name},
            ),
        )

    def test_view_permission(self):
        """Links to reactivate/deactivate/delete pages appear if the user has edit permission."""
        view_user = User.objects.create_user(username="view", password="test")
        view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
        )
        self.client.force_login(view_user)
        obj = factories.ManagedGroupFactory.create()
        response = self.client.get(self.get_url(obj.name))
        self.assertIn("show_edit_links", response.context_data)
        self.assertFalse(response.context_data["show_edit_links"])
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:managed_groups:delete",
                kwargs={"slug": obj.name},
            ),
        )

    def test_group_visualization(self):
        factories.ManagedGroupFactory.create()
        group = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=group, child_group=child)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name))
        self.assertIn("graph", response.context_data)


class ManagedGroupCreateTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 201

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ManagedGroupCreate.as_view()

    def get_api_url(self, group_name):
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name

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

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.ManagedGroupCreateForm)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("test-group")
        self.anvil_response_mock.add(responses.POST, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"})
        self.assertEqual(response.status_code, 302)
        new_object = models.ManagedGroup.objects.latest("pk")
        self.assertIsInstance(new_object, models.ManagedGroup)
        self.assertEqual(new_object.name, "test-group")
        self.assertEqual(new_object.email, "test-group@firecloud.org")
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_create_an_object_with_note(self):
        """Posting valid data including note to the form creates an object."""
        api_url = self.get_api_url("test-group")
        self.anvil_response_mock.add(responses.POST, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group", "note": "test note"})
        self.assertEqual(response.status_code, 302)
        new_object = models.ManagedGroup.objects.latest("pk")
        self.assertIsInstance(new_object, models.ManagedGroup)
        self.assertEqual(new_object.note, "test note")

    def test_success_message(self):
        """Response includes a success message if successful."""
        api_url = self.get_api_url("test-group")
        self.anvil_response_mock.add(responses.POST, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.ManagedGroupCreate.success_message, str(messages[0]))

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        api_url = self.get_api_url("test-group")
        self.anvil_response_mock.add(responses.POST, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"})
        new_object = models.ManagedGroup.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())

    def test_cannot_create_duplicate_object(self):
        """Cannot create two groups with the same name."""
        obj = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": obj.name})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("already exists", form.errors["name"][0])
        self.assertQuerySetEqual(
            models.ManagedGroup.objects.all(),
            models.ManagedGroup.objects.filter(pk=obj.pk),
        )
        self.assertEqual(len(responses.calls), 0)

    def test_cannot_create_duplicate_object_case_insensitive(self):
        """Cannot create two groups with the same name, regardless of case."""
        obj = factories.ManagedGroupFactory.create(name="group")
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "GROUP"})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("already exists", form.errors["name"][0])
        self.assertQuerySetEqual(
            models.ManagedGroup.objects.all(),
            models.ManagedGroup.objects.filter(pk=obj.pk),
        )
        self.assertEqual(len(responses.calls), 0)

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": ""})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.ManagedGroup.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.ManagedGroup.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_api_error_message(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("test-group")
        self.anvil_response_mock.add(
            responses.POST,
            api_url,
            status=500,
            json={"message": "group create test error"},
        )
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: group create test error", str(messages[0]))
        # Make sure that no object is created.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)

    def test_api_group_already_exists(self):
        api_url = self.get_api_url("test-group")
        self.anvil_response_mock.add(responses.POST, api_url, status=409, json={"message": "other error"})
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: other error", str(messages[0]))
        # Make sure that no object is created.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)

    @override_settings(
        ANVIL_MANAGED_GROUP_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestManagedGroupAfterAnVILCreateAdapter"
    )
    def test_post_custom_adapter_after_anvil_create(self):
        """The after_anvil_create method is run after a managed group is created."""
        # Create a group to add this group to
        api_url = self.get_api_url("test-group")
        self.anvil_response_mock.add(responses.POST, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"})
        self.assertEqual(response.status_code, 302)
        # Check that the name was changed by the adaapter.
        new_object = models.ManagedGroup.objects.latest("pk")
        self.assertEqual(new_object.name, "changed-name")

    @override_settings(
        ANVIL_MANAGED_GROUP_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestManagedGroupAfterAnVILCreateForeignKeyAdapter"
    )
    def test_post_custom_adapter_after_anvil_create_fk(self):
        """The view handles using the new group in a foreign key relationship correctly."""
        # Create a group to add this group to.
        parent_group = factories.ManagedGroupFactory.create(name="parent-group")
        api_url = self.get_api_url("test-group")
        self.anvil_response_mock.add(responses.POST, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"})
        self.assertEqual(response.status_code, 302)
        new_object = models.ManagedGroup.objects.latest("pk")
        # Check that the membership was created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        membership = models.GroupGroupMembership.objects.latest("pk")
        self.assertEqual(membership.parent_group, parent_group)
        self.assertEqual(membership.child_group, new_object)
        self.assertEqual(membership.role, models.GroupGroupMembership.MEMBER)


class ManagedGroupUpdateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:update", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ManagedGroupUpdate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo"))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo"))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        instance = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(instance.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, slug="foo")

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, slug="foo")

    def test_object_does_not_exist(self):
        """Raises Http404 if object does not exist."""
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, slug="foo")

    def test_has_form_in_context(self):
        """Response includes a form."""
        instance = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(instance.name))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.ManagedGroupUpdateForm)

    def test_can_modify_note(self):
        """Can set the note when creating a billing project."""
        instance = factories.ManagedGroupFactory.create(note="original note")
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.name), {"note": "new note"})
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        self.assertEqual(instance.note, "new note")

    def test_success_message(self):
        """Response includes a success message if successful."""
        instance = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.name), {}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.ManagedGroupUpdate.success_message, str(messages[0]))

    def test_redirects_to_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        instance = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(instance.name), {})
        self.assertRedirects(response, instance.get_absolute_url())


class ManagedGroupListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ManagedGroupList.as_view()

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

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.ManagedGroupStaffTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.ManagedGroupFactory()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.ManagedGroupFactory.create(name="g1")
        factories.ManagedGroupFactory.create(name="g2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_filter_return_no_object(self):
        factories.ManagedGroupFactory.create(name="group1")
        factories.ManagedGroupFactory.create(name="group2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"name__icontains": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_returns_one_object_exact(self):
        instance = factories.ManagedGroupFactory.create(name="group1")
        factories.ManagedGroupFactory.create(name="group2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"name__icontains": "group1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_case_insensitive(self):
        instance = factories.ManagedGroupFactory.create(name="group1")
        factories.ManagedGroupFactory.create(name="group2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"name__icontains": "Group1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_case_contains(self):
        instance = factories.ManagedGroupFactory.create(name="group1")
        factories.ManagedGroupFactory.create(name="group2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"name__icontains": "roup1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_mutiple_objects(self):
        factories.ManagedGroupFactory.create(name="group1")
        factories.ManagedGroupFactory.create(name="gRouP2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"name__icontains": "Group"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    @override_settings(
        ANVIL_MANAGED_GROUP_ADAPTER="anvil_consortium_manager.tests.test_app.adapters.TestManagedGroupAdapter"
    )
    def test_adapter(self):
        """Displays the correct table if specified in the adapter."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], app_tables.TestManagedGroupTable)


class ManagedGroupDeleteTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:delete", args=args)

    def get_api_url(self, group_name):
        url = self.api_client.sam_entry_point + "/api/groups/v1/" + group_name
        return url

    def get_view(self):
        """Return the view being tested."""
        return views.ManagedGroupDelete.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(1))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(1))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(1))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=1)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(1))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=1)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url(1))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, pk=1)

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        object = factories.ManagedGroupFactory.create(name="test-group")
        api_url = self.get_api_url(object.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.ManagedGroup.objects.count(), 0)
        # History is added.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        object = factories.ManagedGroupFactory.create(name="test-group")
        api_url = self.get_api_url(object.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.name), {"submit": ""}, follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.ManagedGroupDelete.success_message, str(messages[0]))

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.ManagedGroupFactory.create()
        other_object = factories.ManagedGroupFactory.create()
        api_url = self.get_api_url(object.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        self.assertQuerySetEqual(
            models.ManagedGroup.objects.all(),
            models.ManagedGroup.objects.filter(pk=other_object.pk),
        )

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.ManagedGroupFactory.create()
        api_url = self.get_api_url(object.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        # Need to use the client instead of RequestFactory to check redirection url.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("anvil_consortium_manager:managed_groups:list"))

    def test_get_redirect_group_is_a_member_of_another_group(self):
        """Redirect get request when trying to delete a group that is a member of another group.

        This is a behavior enforced by AnVIL."""
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(child.name), follow=True)
        self.assertRedirects(response, child.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_is_member_of_another_group,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 2)
        models.ManagedGroup.objects.get(pk=child.pk)
        # Make sure the relationships still exists.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        models.GroupGroupMembership.objects.get(parent_group=parent, child_group=child)

    def test_post_redirect_group_is_a_member_of_another_group(self):
        """Redirect post request when trying to delete a group that is a member of another group.

        This is a behavior enforced by AnVIL."""
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(child.name), follow=True)
        self.assertRedirects(response, child.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_is_member_of_another_group,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 2)
        models.ManagedGroup.objects.get(pk=child.pk)
        # Make sure the relationships still exists.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        models.GroupGroupMembership.objects.get(parent_group=parent, child_group=child)

    def test_get_redirect_group_used_as_auth_domain(self):
        """Redirect when trying to delete a group used as an auth domain with a get request."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        workspace.authorization_domains.add(group)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.ManagedGroupDelete.message_is_auth_domain, str(messages[0]))
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)

    def test_post_redirect_group_used_as_auth_domain(self):
        """Cannot delete a group used as an auth domain with a post request."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        workspace.authorization_domains.add(group)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(group.name), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.ManagedGroupDelete.message_is_auth_domain, str(messages[0]))
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)

    def test_get_redirect_group_has_access_to_workspace(self):
        """Redirect get request when trying to delete a group that has access to a workspace.

        This is a behavior enforced by AnVIL."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        access = factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_has_access_to_workspace,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        models.ManagedGroup.objects.get(pk=group.pk)
        # Make sure the relationships still exists.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        models.WorkspaceGroupSharing.objects.get(pk=access.pk)

    def test_post_redirect_group_has_access_to_workspace(self):
        """Redirect post request when trying to delete a group that has access to a workspace.

        This is a behavior enforced by AnVIL."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        access = factories.WorkspaceGroupSharingFactory.create(workspace=workspace, group=group)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(group.name), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_has_access_to_workspace,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        models.ManagedGroup.objects.get(pk=group.pk)
        # Make sure the relationships still exists.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        models.WorkspaceGroupSharing.objects.get(pk=access.pk)

    def test_can_delete_group_that_has_child_groups(self):
        """Can delete a group that has other groups as members."""
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        api_url = self.get_api_url(parent.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(parent.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        # Parent was deleted.
        with self.assertRaises(models.ManagedGroup.DoesNotExist):
            models.ManagedGroup.objects.get(pk=parent.pk)
        # Child was not deleted.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        models.ManagedGroup.objects.get(pk=child.pk)
        # The group membership was deleted.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)
        # History is added for the GroupGroupMembership.
        self.assertEqual(models.GroupGroupMembership.history.count(), 2)
        self.assertEqual(models.GroupGroupMembership.history.latest().history_type, "-")

    def test_can_delete_group_if_it_has_account_members(self):
        """Can delete a group that has other groups as members."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        api_url = self.get_api_url(group.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(group.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        # The group was deleted.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)
        # Thee membership was deleted.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)
        # The account still exists.
        models.Account.objects.get(pk=account.pk)
        # History is added for GroupAccountMemberships.
        self.assertEqual(models.GroupAccountMembership.history.count(), 2)
        self.assertEqual(models.GroupAccountMembership.history.latest().history_type, "-")

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.ManagedGroupFactory.create()
        api_url = self.get_api_url(object.name)
        self.anvil_response_mock.add(
            responses.DELETE,
            api_url,
            status=500,
            json={"message": "group delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.name), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: group delete test error", str(messages[0]))
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)

    def test_get_redirect_group_not_managed_by_app(self):
        """Redirect when trying to delete a group that the app doesn't manage."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.ManagedGroupDelete.message_not_managed_by_app, str(messages[0]))
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)

    def test_post_redirect_group_not_managed_by_app(self):
        """Redirect when trying to delete a group that the app doesn't manage with a post request."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(group.name), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.ManagedGroupDelete.message_not_managed_by_app, str(messages[0]))
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)

    @skip("AnVIL API issue - covered by model fields")
    def test_api_not_admin_of_group(self):
        self.fail("AnVIL API returns 204 instead of 403 when trying to delete a group you are not an admin of.")

    @skip("AnVIL API issue - covered by model fields")
    def test_api_group_does_not_exist(self):
        self.fail("AnVIL API returns 204 instead of 404 when trying to delete a group that doesn't exist.")

    def test_post_does_not_delete_when_protected_fk_to_another_model(self):
        """Group is not deleted when there is another model referencing the group with a protected foreing key."""
        object = factories.ManagedGroupFactory.create(name="test-group")
        app_models.ProtectedManagedGroup.objects.create(group=object)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.name), {"submit": ""}, follow=True)
        self.assertRedirects(response, object.get_absolute_url())
        # A message is added.
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_could_not_delete_group_from_app,
            str(messages[0]),
        )
        # Make sure the group still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        object.refresh_from_db()


class ManagedGroupAutocompleteTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with the correct permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:autocomplete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ManagedGroupAutocomplete.as_view()

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

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_returns_all_objects(self):
        """Queryset returns all objects when there is no query."""
        groups = factories.ManagedGroupFactory.create_batch(10)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 10)
        self.assertEqual(sorted(returned_ids), sorted([group.pk for group in groups]))

    def test_returns_correct_object_match(self):
        """Queryset returns the correct objects when query matches the name."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "test-group"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], group.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "test"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], group.pk)

    def test_returns_correct_object_containing_query(self):
        """Queryset returns the correct objects when the name contains the query."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "grou"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], group.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        group = factories.ManagedGroupFactory.create(name="TEST-GROUP")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "test"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], group.pk)

    def test_returns_groups_not_managed_by_app_by_default(self):
        """Queryset does return groups that are not managed by the app by default."""
        object = factories.ManagedGroupFactory.create(name="test-group", is_managed_by_app=False)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_does_not_return_groups_not_managed_by_app_when_specified(self):
        """Queryset does not return groups that are not managed by the app when specified."""
        factories.ManagedGroupFactory.create(name="test-group", is_managed_by_app=False)
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(),
            {"forward": json.dumps({"only_managed_by_app": True})},
        )
        self.assertEqual(json.loads(response.content.decode("utf-8"))["results"], [])


class ManagedGroupVisualizationTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:visualization", args=args)

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

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            views.ManagedGroupVisualization.as_view()(request)

    def test_view_status_code_with_existing_object_not_managed(self):
        """Returns a successful status code for an existing object pk."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_no_groups(self):
        """Visualization when there are no groups."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("graph", response.context_data)

    def test_one_group(self):
        """Visualization when there is one group."""
        factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("graph", response.context_data)

    def test_two_groups(self):
        """Visualization when there are two groups."""
        factories.ManagedGroupFactory.create(name="g1")
        factories.ManagedGroupFactory.create(name="g2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("graph", response.context_data)

    def test_group_visualization(self):
        factories.ManagedGroupFactory.create()
        grandparent = factories.ManagedGroupFactory.create()
        parent_1 = factories.ManagedGroupFactory.create()
        parent_2 = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent_1)
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent_2)
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent_1,
            child_group=child,
            role=models.GroupGroupMembership.ADMIN,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("graph", response.context_data)


class WorkspaceLandingPageTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with view permission.
        self.view_user = User.objects.create_user(username="test_view", password="view")
        self.view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        # Create a user with staff view permission.
        self.staff_view_user = User.objects.create_user(username="test_staff_view", password="view")
        self.staff_view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        # Create a user with edit permission.
        self.edit_user = User.objects.create_user(username="test_edit", password="test")
        self.edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        super().tearDown()

    def get_url(self):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:landing_page")

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(),
        )

    def test_status_code_with_staff_view_permission(self):
        """Returns successful response code if user has staff_view permission."""
        self.client.force_login(self.staff_view_user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Returns successful response code if user has view permission."""
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_staff_view_permission(self):
        """Links to edit required do not appear in the page when user only has staff_view permission."""
        self.client.force_login(self.staff_view_user)
        response = self.client.get(self.get_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertFalse(response.context_data["show_edit_links"])
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:import",
                kwargs={"workspace_type": "workspace"},
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:new",
                kwargs={"workspace_type": "workspace"},
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:list",
                kwargs={"workspace_type": "workspace"},
            ),
        )

    def test_view_permission(self):
        """Links to edit required do not appear in the page when user only has view permission."""
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertFalse(response.context_data["show_edit_links"])
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:import",
                kwargs={"workspace_type": "workspace"},
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:new",
                kwargs={"workspace_type": "workspace"},
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:list",
                kwargs={"workspace_type": "workspace"},
            ),
        )

    def test_edit_permission(self):
        """Links to edit required appear in the page when user also has edit permission."""
        self.client.force_login(self.edit_user)
        response = self.client.get(self.get_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertTrue(response.context_data["show_edit_links"])
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:import",
                kwargs={"workspace_type": "workspace"},
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:new",
                kwargs={"workspace_type": "workspace"},
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:list",
                kwargs={"workspace_type": "workspace"},
            ),
        )

    def test_one_registered_workspace_in_context(self):
        """One registered workspace in context when only DefaultWorkspaceAdapter is registered"""
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url())
        self.assertIn("registered_workspace_adapters", response.context_data)
        self.assertEqual(len(response.context_data["registered_workspace_adapters"]), 1)

    def test_two_registered_workspaces_in_context(self):
        """Two registered workspaces in context when two workspace adapters are registered"""
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url())
        self.assertIn("registered_workspace_adapters", response.context_data)
        self.assertEqual(len(response.context_data["registered_workspace_adapters"]), 2)


class WorkspaceDetailTest(TestCase):
    """Tests for the WorkspaceDetail view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        super().tearDown()

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceDetail.as_view()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        url = reverse("anvil_consortium_manager:workspaces:detail", args=["foo1", "foo2"])
        response = self.client.get(url)
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + url)

    def test_status_code_with_staff_view_permission(self):
        """Returns successful response code."""
        obj = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        obj = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(user)
        response = self.client.get(obj.get_absolute_url())
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.DefaultWorkspaceDataFactory.create()
        request = self.factory.get(obj.get_absolute_url())
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, billing_project_slug="foo1", workspace_slug="foo2")

    def test_context_workspace_data(self):
        """The view adds the workspace_data object to the context."""
        obj = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        response.context_data
        self.assertIn("workspace_data_object", response.context_data)
        self.assertEqual(response.context_data["workspace_data_object"], obj)

    def test_group_sharing_table(self):
        """The workspace group access table exists."""
        obj = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("group_sharing_table", response.context_data)
        self.assertIsInstance(
            response.context_data["group_sharing_table"],
            tables.WorkspaceGroupSharingStaffTable,
        )

    def test_group_sharing_table_none(self):
        """No groups are shown if the workspace has not been shared with any groups."""
        workspace = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertIn("group_sharing_table", response.context_data)
        self.assertEqual(len(response.context_data["group_sharing_table"].rows), 0)

    def test_group_sharing_table_one(self):
        """One group is shown if the workspace has been shared with one group."""
        workspace = factories.DefaultWorkspaceDataFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace.workspace)
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertIn("group_sharing_table", response.context_data)
        self.assertEqual(len(response.context_data["group_sharing_table"].rows), 1)

    def test_group_sharing_table_two(self):
        """Two groups are shown if the workspace has been shared with two groups."""
        workspace = factories.DefaultWorkspaceDataFactory.create()
        factories.WorkspaceGroupSharingFactory.create(group__name="g1", workspace=workspace.workspace)
        factories.WorkspaceGroupSharingFactory.create(group__name="g2", workspace=workspace.workspace)
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertIn("group_sharing_table", response.context_data)
        self.assertEqual(len(response.context_data["group_sharing_table"].rows), 2)

    def test_group_sharing_table_view_permission(self):
        """Workspace-group sharing table is not present in context when user has view permission only."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        workspace = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertNotIn("group_sharing_table", response.context_data)
        self.assertNotContains(response, "View groups that this workspace is shared with")

    def test_shows_workspace_group_sharing_for_only_that_workspace(self):
        """Only shows groups that this workspace has been shared with."""
        workspace = factories.DefaultWorkspaceDataFactory.create(workspace__name="workspace-1")
        other_workspace = factories.WorkspaceFactory.create(name="workspace-2")
        factories.WorkspaceGroupSharingFactory.create(workspace=other_workspace)
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertIn("group_sharing_table", response.context_data)
        self.assertEqual(len(response.context_data["group_sharing_table"].rows), 0)

    def test_auth_domain_table(self):
        """The workspace auth domain table exists."""
        obj = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("authorization_domain_table", response.context_data)
        self.assertIsInstance(
            response.context_data["authorization_domain_table"],
            tables.ManagedGroupStaffTable,
        )

    def test_auth_domain_table_none(self):
        """No groups are shown if the workspace has no auth domains."""
        workspace = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertIn("authorization_domain_table", response.context_data)
        self.assertEqual(len(response.context_data["authorization_domain_table"].rows), 0)

    def test_auth_domain_table_one(self):
        """One group is shown if the workspace has one auth domain."""
        workspace = factories.DefaultWorkspaceDataFactory.create()
        group = factories.ManagedGroupFactory.create()
        workspace.workspace.authorization_domains.add(group)
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertIn("authorization_domain_table", response.context_data)
        table = response.context_data["authorization_domain_table"]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(group, table.data)

    def test_auth_domain_table_two(self):
        """Two groups are shown if the workspace has two auth domains."""
        workspace = factories.DefaultWorkspaceDataFactory.create()
        group_1 = factories.ManagedGroupFactory.create(name="g1")
        workspace.workspace.authorization_domains.add(group_1)
        group_2 = factories.ManagedGroupFactory.create(name="g2")
        workspace.workspace.authorization_domains.add(group_2)
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertIn("authorization_domain_table", response.context_data)
        table = response.context_data["authorization_domain_table"]
        self.assertEqual(len(table.rows), 2)
        self.assertIn(group_1, table.data)
        self.assertIn(group_2, table.data)

    def test_auth_domain_table_view_permission(self):
        """Auth domain table has correct class when user has view permission only."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        workspace = factories.DefaultWorkspaceDataFactory.create()
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace.workspace)
        self.client.force_login(user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertIn("authorization_domain_table", response.context_data)
        self.assertIsInstance(response.context_data["authorization_domain_table"], tables.ManagedGroupUserTable)

    def test_shows_auth_domains_for_only_that_workspace(self):
        """Only shows auth domains for this workspace."""
        workspace = factories.DefaultWorkspaceDataFactory.create(workspace__name="workspace-1")
        other_workspace = factories.WorkspaceFactory.create(name="workspace-2")
        group = factories.ManagedGroupFactory.create()
        other_workspace.authorization_domains.add(group)
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertIn("authorization_domain_table", response.context_data)
        self.assertEqual(len(response.context_data["authorization_domain_table"].rows), 0)

    def test_staff_edit_permission(self):
        """Links in template when user has staff edit permission."""
        edit_user = User.objects.create_user(username="edit", password="test")
        edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )
        self.client.force_login(edit_user)
        obj = factories.DefaultWorkspaceDataFactory.create()
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertTrue(response.context_data["show_edit_links"])
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:delete",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        # Billing project link
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:billing_projects:detail",
                kwargs={
                    "slug": obj.workspace.billing_project.name,
                },
            ),
        )
        # Action buttons
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:update:internal",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:sharing:new",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:clone",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                    "workspace_type": "workspace",
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:all",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )

    def test_staff_view_permission(self):
        """Links in template when user has staff view permission."""
        view_user = User.objects.create_user(username="view", password="test")
        view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
        )
        self.client.force_login(view_user)
        obj = factories.DefaultWorkspaceDataFactory.create()
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertFalse(response.context_data["show_edit_links"])
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:delete",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        # Billing project link
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:billing_projects:detail",
                kwargs={
                    "slug": obj.workspace.billing_project.name,
                },
            ),
        )
        # Action buttons
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:update:internal",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:sharing:new",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:clone",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                    "workspace_type": "workspace",
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:all",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )

    def test_view_permission(self):
        """Links in template when user has view permission."""
        view_user = User.objects.create_user(username="view", password="test")
        view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME),
        )
        self.client.force_login(view_user)
        obj = factories.DefaultWorkspaceDataFactory.create()
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertFalse(response.context_data["show_edit_links"])
        # Billing project link
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:billing_projects:detail",
                kwargs={
                    "slug": obj.workspace.billing_project.name,
                },
            ),
        )
        # Action buttons
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:delete",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:update:internal",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:sharing:new",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:clone",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                    "workspace_type": "workspace",
                },
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:all",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )

    def test_render_custom_template_name(self):
        """Rendering a correct template when custom template name is specified."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        workspace = TestWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertTemplateUsed(response, "test_workspace_detail.html")

    def test_context_workspace_type_display_name(self):
        """workspace_type_display_name is present in context."""
        workspace = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertIn("workspace_type_display_name", response.context)
        self.assertEqual(
            response.context["workspace_type_display_name"],
            DefaultWorkspaceAdapter().get_name(),
        )

    def test_context_workspace_type_display_name_custom_adapter(self):
        """workspace_type_display_name is present in context with a custom adapter."""
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        workspace = TestWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertTemplateUsed(response, "test_workspace_detail.html")
        self.assertIn("workspace_type_display_name", response.context)
        self.assertEqual(
            response.context["workspace_type_display_name"],
            TestWorkspaceAdapter().get_name(),
        )

    def test_context_workspace_with_extra_context(self):
        """workspace_type_display_name is present in context with a custom adapter."""
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        workspace = TestWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertIn("extra_text", response.context)
        self.assertEqual(response.context["extra_text"], "Extra text")

    def test_is_locked_true(self):
        """An indicator of whether a workspace is locked appears on the page."""
        workspace = factories.DefaultWorkspaceDataFactory.create(workspace__is_locked=True)
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertContains(response, "Locked")

    def test_is_locked_false(self):
        """An indicator of whether a workspace is locked appears on the page."""
        workspace = factories.DefaultWorkspaceDataFactory.create(workspace__is_locked=False)
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertNotContains(response, "Locked")

    def test_edit_permission_is_locked(self):
        """Links appear correctly when the user has edit permission but the workspace is locked."""
        edit_user = User.objects.create_user(username="edit", password="test")
        edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )
        self.client.force_login(edit_user)
        obj = factories.DefaultWorkspaceDataFactory.create(workspace__is_locked=True)
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertTrue(response.context_data["show_edit_links"])
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:delete",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:update:internal",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:sharing:new",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:clone",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                    "workspace_type": "workspace",
                },
            ),
        )

    def test_is_requester_pays_true(self):
        """An indicator of whether a workspace is requester_pays appears on the page."""
        workspace = factories.DefaultWorkspaceDataFactory.create(workspace__is_requester_pays=True)
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertContains(response, "Requester pays")

    def test_is_requester_pays_false(self):
        """An indicator of whether a workspace is requester_pays appears on the page."""
        workspace = factories.DefaultWorkspaceDataFactory.create(workspace__is_requester_pays=False)
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertNotContains(response, "Requester pays")

    def test_clone_links_with_two_registered_workspace_adapters(self):
        """Links to clone into each type of workspace appear when there are two registered workspace types."""
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        edit_user = User.objects.create_user(username="edit", password="test")
        edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )
        self.client.force_login(edit_user)
        obj = factories.DefaultWorkspaceDataFactory.create()
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertTrue(response.context_data["show_edit_links"])
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:clone",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                    "workspace_type": DefaultWorkspaceAdapter().get_type(),
                },
            ),
        )
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:clone",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                    "workspace_type": TestWorkspaceAdapter().get_type(),
                },
            ),
        )

    def test_access_badge_no_linked_account(self):
        obj = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("has_access", response.context)
        self.assertFalse(response.context["has_access"])
        self.assertContains(response, "No access to workspace")

    def test_access_badge_no_access(self):
        factories.AccountFactory.create(user=self.user, verified=True)
        obj = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("has_access", response.context)
        self.assertFalse(response.context["has_access"])
        self.assertContains(response, "No access to workspace")

    def test_access_badge_access(self):
        obj = factories.DefaultWorkspaceDataFactory.create()
        account = factories.AccountFactory.create(user=self.user, verified=True)
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        factories.WorkspaceGroupSharingFactory.create(workspace=obj.workspace, group=group)
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("has_access", response.context)
        self.assertTrue(response.context["has_access"])
        self.assertContains(response, "You have access to this workspace")

    def test_anvil_link_with_access(self):
        """Link to AnVIL appears on the page when the user has access."""
        obj = factories.DefaultWorkspaceDataFactory.create()
        account = factories.AccountFactory.create(user=self.user, verified=True)
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        factories.WorkspaceGroupSharingFactory.create(workspace=obj.workspace, group=group)
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertContains(response, "View on AnVIL")
        self.assertContains(response, obj.workspace.get_anvil_url())

    def test_anvil_link_no_access(self):
        """Link to AnVIL does not appear on the page when the user does not have access."""
        obj = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertNotContains(response, "View on AnVIL")
        self.assertNotContains(response, obj.workspace.get_anvil_url())

    def test_anvil_link_no_access_superuser(self):
        """Link to AnVIL does appears on the page when the user does not have access but is a superuser."""
        superuser = User.objects.create_superuser(username="test-superuser", password="test-superuser")
        obj = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(superuser)
        response = self.client.get(obj.get_absolute_url())
        self.assertContains(response, "View on AnVIL")
        self.assertContains(response, obj.workspace.get_anvil_url())

    def test_dates_present_for_staff_view_permission(self):
        obj = factories.DefaultWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertContains(response, "Date added")
        self.assertContains(response, "Date modified")

    def test_no_dates_for_view_permission(self):
        obj = factories.DefaultWorkspaceDataFactory.create()
        view_user = User.objects.create_user(username="view", password="test")
        view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME),
        )
        self.client.force_login(view_user)
        response = self.client.get(obj.get_absolute_url())
        self.assertNotContains(response, "Date added")
        self.assertNotContains(response, "Date modified")

    def test_template_block_extra_pills(self):
        """The extra_pills template block is shown on the detail page."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        workspace = TestWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(workspace.get_absolute_url())
        self.assertContains(response, """<span class="badge">Extra workspace pill</span>""")


class WorkspaceCreateTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 201

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.workspace_type = DefaultWorkspaceAdapter.type
        self.api_url = self.api_client.rawls_entry_point + "/api/workspaces"

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        super().tearDown()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceCreate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.workspace_type),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, workspace_type=self.workspace_type)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, workspace_type=self.workspace_type)

    def test_get_workspace_type_not_registered(self):
        """Raises 404 with get request if workspace type is not registered with adapter."""
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, workspace_type="foo")

    def test_post_workspace_type_not_registered(self):
        """Raises 404 with post request if workspace type is not registered with adapter."""
        request = self.factory.post(self.get_url("foo"), {})
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, workspace_type="foo")

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertTrue("form" in response.context_data)

    def test_form_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceForm)

    def test_has_formset_in_context(self):
        """Response includes a formset for the workspace_data model."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertTrue("workspace_data_formset" in response.context_data)
        formset = response.context_data["workspace_data_formset"]
        self.assertIsInstance(formset, BaseInlineFormSet)
        self.assertEqual(len(formset.forms), 1)
        self.assertIsInstance(formset.forms[0], forms.DefaultWorkspaceDataForm)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.Workspace.objects.latest("pk")
        self.assertIsInstance(new_object, models.Workspace)
        self.assertEqual(
            new_object.workspace_type,
            DefaultWorkspaceAdapter().get_type(),
        )
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_create_an_object_with_note(self):
        """Posting valid data to the form creates an object."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "note": "test note",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.Workspace.objects.latest("pk")
        self.assertIsInstance(new_object, models.Workspace)
        self.assertEqual(new_object.note, "test note")

    def test_creates_default_workspace_data(self):
        """Posting valid data to the form creates the default workspace data object."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_workspace = models.Workspace.objects.latest("pk")
        # Also creates a workspace data object.
        self.assertEqual(models.DefaultWorkspaceData.objects.count(), 1)
        self.assertIsInstance(new_workspace.defaultworkspacedata, models.DefaultWorkspaceData)

    def test_success_message(self):
        """Response includes a success message if successful."""
        billing_project = factories.BillingProjectFactory.create()
        json_data = {
            "namespace": billing_project.name,
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceCreate.success_message, str(messages[0]))

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        billing_project = factories.BillingProjectFactory.create()
        json_data = {
            "namespace": billing_project.name,
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        new_object = models.Workspace.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())

    def test_cannot_create_duplicate_object(self):
        """Cannot create two workspaces with the same billing project and name."""
        obj = factories.WorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": obj.billing_project.pk,
                "name": obj.name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.Workspace.objects.all(),
            models.Workspace.objects.filter(pk=obj.pk),
        )

    def test_can_create_workspace_with_same_billing_project_different_name(self):
        """Can create a workspace with a different name in the same billing project."""
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(billing_project=billing_project, name="test-name-1")
        json_data = {
            "namespace": billing_project.name,
            "name": "test-name-2",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-name-2",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 2)
        # Make sure you can get the new object.
        models.Workspace.objects.get(billing_project=billing_project, name="test-name-2")

    def test_can_create_workspace_with_same_name_different_billing_project(self):
        """Can create a workspace with the same name in a different billing project."""
        billing_project_1 = factories.BillingProjectFactory.create(name="project-1")
        billing_project_2 = factories.BillingProjectFactory.create(name="project-2")
        workspace_name = "test-name"
        factories.WorkspaceFactory.create(billing_project=billing_project_1, name=workspace_name)
        json_data = {
            "namespace": billing_project_2.name,
            "name": "test-name",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project_2.pk,
                "name": workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 2)
        # Make sure you can get the new object.
        models.Workspace.objects.get(billing_project=billing_project_2, name=workspace_name)

    def test_invalid_input_name(self):
        """Posting invalid data to name field does not create an object."""
        billing_project = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "invalid name",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("slug", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_invalid_input_billing_project(self):
        """Posting invalid data to billing_project field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": 1,
                "name": "test-name",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("valid choice", form.errors["billing_project"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_post_invalid_name_billing_project(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(self.workspace_type), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("required", form.errors["billing_project"][0])
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(self.workspace_type), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("required", form.errors["billing_project"][0])
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_api_error_message(self):
        """Shows a method if an AnVIL API error occurs."""
        billing_project = factories.BillingProjectFactory.create()
        json_data = {
            "namespace": billing_project.name,
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=500,
            match=[responses.matchers.json_params_matcher(json_data)],
            json={"message": "workspace create test error"},
        )
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error: workspace create test error", str(messages[0]))
        # Make sure that no object is created.
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_can_create_a_workspace_with_one_authorization_domain(self):
        """Can create a workspace with one authorization domain."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        auth_domain = factories.ManagedGroupFactory.create()
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [{"membersGroupName": auth_domain.name}],
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.Workspace.objects.latest("pk")
        self.assertIsInstance(new_object, models.Workspace)
        self.assertEqual(len(new_object.authorization_domains.all()), 1)
        self.assertIn(auth_domain, new_object.authorization_domains.all())
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")
        # History is added for the authorization domain.
        self.assertEqual(models.WorkspaceAuthorizationDomain.history.count(), 1)
        self.assertEqual(models.WorkspaceAuthorizationDomain.history.latest().history_type, "+")

    def test_create_workspace_with_two_auth_domains(self):
        """Can create a workspace with two authorization domains."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        auth_domain_1 = factories.ManagedGroupFactory.create(name="auth1")
        auth_domain_2 = factories.ManagedGroupFactory.create(name="auth2")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [
                {"membersGroupName": auth_domain_1.name},
                {"membersGroupName": auth_domain_2.name},
            ],
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain_1.pk, auth_domain_2.pk],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.Workspace.objects.latest("pk")
        self.assertIsInstance(new_object, models.Workspace)
        self.assertEqual(len(new_object.authorization_domains.all()), 2)
        self.assertIn(auth_domain_1, new_object.authorization_domains.all())
        self.assertIn(auth_domain_2, new_object.authorization_domains.all())

    def test_invalid_auth_domain(self):
        """Does not create a workspace when an invalid authorization domain is specified."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [1],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("authorization_domains", form.errors.keys())
        self.assertIn("valid choice", form.errors["authorization_domains"][0])
        # No object was created.
        self.assertEqual(len(models.Workspace.objects.all()), 0)
        # No API calls made.

    def test_one_valid_one_invalid_auth_domain(self):
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        auth_domain = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk, auth_domain.pk + 1],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("authorization_domains", form.errors.keys())
        self.assertIn("valid choice", form.errors["authorization_domains"][0])
        # No object was created.
        self.assertEqual(len(models.Workspace.objects.all()), 0)

    def test_auth_domain_does_not_exist_on_anvil(self):
        """No workspace is displayed if the auth domain group doesn't exist on AnVIL."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        auth_domain = factories.ManagedGroupFactory.create()
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [
                {"membersGroupName": auth_domain.name},
            ],
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=400,
            json={"message": "api error"},
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        # The form is valid but there was an API error.
        form = response.context_data["form"]
        self.assertTrue(form.is_valid())
        # Check messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: api error", str(messages[0]))
        # Did not create any new Workspaces.
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_not_admin_of_auth_domain_on_anvil(self):
        """No workspace is displayed if we are not the admins of the auth domain on AnVIL."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        auth_domain = factories.ManagedGroupFactory.create()
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [
                {"membersGroupName": auth_domain.name},
            ],
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=400,
            json={"message": "api error"},
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        # The form is valid but there was an API error.
        form = response.context_data["form"]
        self.assertTrue(form.is_valid())
        # Check messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: api error", str(messages[0]))
        # Did not create any new Workspaces.
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_adapter_includes_workspace_data_formset(self):
        """Response includes the workspace data formset if specified."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = "test"
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertTrue("workspace_data_formset" in response.context_data)
        formset = response.context_data["workspace_data_formset"]
        self.assertIsInstance(formset, BaseInlineFormSet)
        self.assertEqual(len(formset.forms), 1)
        self.assertIsInstance(formset.forms[0], app_forms.TestWorkspaceDataForm)

    def test_adapter_creates_workspace_data(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = "test"
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-study_name": "test study",
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = models.Workspace.objects.latest("pk")
        # workspace_type is set properly.
        self.assertEqual(
            new_workspace.workspace_type,
            TestWorkspaceAdapter().get_type(),
        )
        # Workspace data is added.
        self.assertEqual(app_models.TestWorkspaceData.objects.count(), 1)
        new_workspace_data = app_models.TestWorkspaceData.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.study_name, "test study")

    def test_adapter_does_not_create_objects_if_workspace_data_form_invalid(self):
        """Posting invalid data to the workspace_data_form form does not create a workspace when using an adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = "test"
        billing_project = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-study_name": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        # Workspace form is valid.
        form = response.context_data["form"]
        self.assertTrue(form.is_valid())
        # workspace_data_form is not valid.
        workspace_data_formset = response.context_data["workspace_data_formset"]
        self.assertEqual(workspace_data_formset.is_valid(), False)
        workspace_data_form = workspace_data_formset.forms[0]
        self.assertEqual(workspace_data_form.is_valid(), False)
        self.assertEqual(len(workspace_data_form.errors), 1)
        self.assertIn("study_name", workspace_data_form.errors)
        self.assertEqual(len(workspace_data_form.errors["study_name"]), 1)
        self.assertIn("required", workspace_data_form.errors["study_name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(app_models.TestWorkspaceData.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_adapter_custom_workspace_form_class(self):
        """No workspace is created if custom workspace form is invalid."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = "test"
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertIsInstance(response.context_data["form"], app_forms.TestWorkspaceForm)

    def test_adapter_does_not_create_object_if_workspace_form_invalid(self):
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = "test"
        billing_project = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-fail",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-study_name": "test study",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("Workspace name cannot be", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_get_workspace_data_with_second_foreign_key_to_workspace(self):
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestForeignKeyWorkspaceAdapter)
        self.workspace_type = "test_fk"
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)

    def test_post_workspace_data_with_second_foreign_key_to_workspace(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestForeignKeyWorkspaceAdapter)
        self.workspace_type = TestForeignKeyWorkspaceAdapter().get_type()
        other_workspace = factories.WorkspaceFactory.create()
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-other_workspace": other_workspace.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = models.Workspace.objects.latest("pk")
        # workspace_type is set properly.
        self.assertEqual(
            new_workspace.workspace_type,
            TestForeignKeyWorkspaceAdapter().get_type(),
        )
        # Workspace data is added.
        self.assertEqual(app_models.TestForeignKeyWorkspaceData.objects.count(), 1)
        new_workspace_data = app_models.TestForeignKeyWorkspaceData.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.other_workspace, other_workspace)

    def test_post_custom_adapter_before_anvil_create(self):
        """The before_anvil_create method is run before a workspace is created."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestBeforeWorkspaceCreateAdapter)
        self.workspace_type = TestBeforeWorkspaceCreateAdapter().get_type()
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace-2",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-test_field": "my field value",
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, "test-workspace-2")

    def test_post_custom_adapter_after_anvil_create(self):
        """The after_anvil_create method is run after a workspace is created."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestAfterWorkspaceCreateAdapter)
        self.workspace_type = TestAfterWorkspaceCreateAdapter().get_type()
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-test_field": "my field value",
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = models.Workspace.objects.latest("pk")
        # The test_field field was modified by the adapter.
        self.assertEqual(new_workspace.testworkspacemethodsdata.test_field, "FOO")


class WorkspaceImportTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the WorkspaceImport view."""

    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.workspace_type = DefaultWorkspaceAdapter().get_type()
        self.workspace_list_url = self.api_client.rawls_entry_point + "/api/workspaces"
        # Object to hold API response for ACL call.
        self.api_json_response_acl = {"acl": {}}
        self.add_api_json_response_acl(self.service_account_email, "OWNER", can_compute=True, can_share=True)

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        super().tearDown()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:import", args=args)

    def get_api_url(self, billing_project_name, workspace_name):
        return self.api_client.rawls_entry_point + "/api/workspaces/" + billing_project_name + "/" + workspace_name

    def get_api_json_response(
        self,
        billing_project,
        workspace,
        authorization_domains=[],
        access="OWNER",
        is_locked=False,
    ):
        """Return a pared down version of the json response from the AnVIL API with only fields we need."""
        json_data = {
            "accessLevel": access,
            "owners": [],
            "workspace": {
                "authorizationDomain": [{"membersGroupName": x} for x in authorization_domains],
                "name": workspace,
                "namespace": billing_project,
                "isLocked": is_locked,
            },
        }
        return json_data

    def get_api_url_acl(self, billing_project_name, workspace_name):
        return (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
            + "/acl"
        )

    def add_api_json_response_acl(self, email, access, can_compute=False, can_share=False):
        """Add a record to the API response for the workspace ACL call."""
        self.api_json_response_acl["acl"][email] = {
            "accessLevel": access,
            "canCompute": can_compute,
            "canShare": False,
            "pending": False,
        }

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceImport.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.workspace_type),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_get_workspace_type_not_registered(self):
        """Raises 404 with get request if workspace type is not registered with adapter."""
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, workspace_type="foo")

    def test_post_workspace_type_not_registered(self):
        """Raises 404 with post request if workspace type is not registered with adapter."""
        request = self.factory.post(self.get_url("foo"), {})
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, workspace_type="foo")

    def test_has_form_in_context(self):
        """Response includes a form."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceImportForm)

    def test_has_formset_in_context(self):
        """Response includes a formset for the workspace_data model."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertTrue("workspace_data_formset" in response.context_data)
        formset = response.context_data["workspace_data_formset"]
        self.assertIsInstance(formset, BaseInlineFormSet)
        self.assertEqual(len(formset.forms), 1)
        self.assertIsInstance(formset.forms[0], forms.DefaultWorkspaceDataForm)

    def test_form_choices_no_available_workspaces(self):
        """Choices are populated correctly with one available workspace."""
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        # Choices are populated correctly.
        workspace_choices = response.context_data["form"].fields["workspace"].choices
        self.assertEqual(len(workspace_choices), 1)
        # The first choice is the empty string.
        self.assertEqual("", workspace_choices[0][0])
        # A message is shown.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceImport.message_no_available_workspaces, str(messages[0]))

    def test_form_choices_one_available_workspace(self):
        """Choices are populated correctly with one available workspace."""
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response("bp-1", "ws-1")],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        # Choices are populated correctly.
        workspace_choices = response.context_data["form"].fields["workspace"].choices
        self.assertEqual(len(workspace_choices), 2)
        # The first choice is the empty string.
        self.assertEqual("", workspace_choices[0][0])
        # Second choice is the workspace.
        self.assertTrue(("bp-1/ws-1", "bp-1/ws-1") in workspace_choices)

    def test_form_choices_two_available_workspaces(self):
        """Choices are populated correctly with two available workspaces."""
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[
                self.get_api_json_response("bp-1", "ws-1"),
                self.get_api_json_response("bp-2", "ws-2"),
            ],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        # Choices are populated correctly.
        workspace_choices = response.context_data["form"].fields["workspace"].choices
        self.assertEqual(len(workspace_choices), 3)
        # The first choice is the empty string.
        self.assertEqual("", workspace_choices[0][0])
        # The next choices are the workspaces.
        self.assertTrue(("bp-1/ws-1", "bp-1/ws-1") in workspace_choices)
        self.assertTrue(("bp-2/ws-2", "bp-2/ws-2") in workspace_choices)

    def test_form_choices_alphabetical_order(self):
        """Choices are populated correctly with two available workspaces."""
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[
                self.get_api_json_response("zzz", "zzz"),
                self.get_api_json_response("aaa", "aaa"),
            ],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        # Choices are populated correctly.
        workspace_choices = response.context_data["form"].fields["workspace"].choices
        self.assertEqual(len(workspace_choices), 3)
        # The first choice is the empty string.
        self.assertEqual("", workspace_choices[0][0])
        # The next choices are the workspaces.
        self.assertEqual(workspace_choices[1], ("aaa/aaa", "aaa/aaa"))
        self.assertEqual(workspace_choices[2], ("zzz/zzz", "zzz/zzz"))

    def test_form_does_not_show_already_imported_workspaces(self):
        """The form does not show workspaces that have already been imported in the choices."""
        billing_project = factories.BillingProjectFactory.create(name="bp")
        factories.WorkspaceFactory.create(billing_project=billing_project, name="ws-imported")
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[
                self.get_api_json_response("bp", "ws-imported", access="OWNER"),
            ],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceImportForm)
        form_choices = response.context_data["form"].fields["workspace"].choices
        # Choices are populated.
        self.assertEqual(len(form_choices), 1)
        self.assertFalse(("bp/ws-imported", "bp/ws-imported") in form_choices)
        # A message is shown.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceImport.message_no_available_workspaces, str(messages[0]))

    def test_form_does_not_show_workspaces_not_owner(self):
        """The form does not show workspaces where we aren't owners in the choices."""
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[
                self.get_api_json_response("bp", "ws-owner", access="OWNER"),
                self.get_api_json_response("bp", "ws-reader", access="READER"),
            ],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceImportForm)
        form_choices = response.context_data["form"].fields["workspace"].choices
        # Choices are populated.
        self.assertEqual(len(form_choices), 2)
        self.assertTrue(("bp/ws-owner", "bp/ws-owner") in form_choices)
        self.assertFalse(("bp/ws-reader", "bp/ws-reader") in form_choices)

    def test_can_import_workspace_and_billing_project_as_user(self):
        """Can import a workspace from AnVIL when the billing project does not exist in Django and we are users."""
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        # Billing project API call.
        billing_project_url = self.api_client.rawls_entry_point + "/api/billing/v2/" + billing_project_name
        self.anvil_response_mock.add(responses.GET, billing_project_url, status=200)
        url = self.get_api_url(billing_project_name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project_name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a billing project.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        new_billing_project = models.BillingProject.objects.latest("pk")
        self.assertEqual(new_billing_project.name, billing_project_name)
        self.assertEqual(new_billing_project.has_app_as_user, True)
        # Created a workspace.
        self.assertEqual(models.Workspace.objects.count(), 1)
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        self.assertEqual(
            new_workspace.workspace_type,
            DefaultWorkspaceAdapter().get_type(),
        )
        # History is added for the workspace.
        self.assertEqual(new_workspace.history.count(), 1)
        self.assertEqual(new_workspace.history.latest().history_type, "+")
        # History is added for the BillingProject.
        self.assertEqual(new_billing_project.history.count(), 1)
        self.assertEqual(new_billing_project.history.latest().history_type, "+")

    def test_can_import_workspace_with_note(self):
        """Sets note when specified when importing a workspace."""
        billing_project_name = "billing-project"
        billing_project = factories.BillingProjectFactory.create(name=billing_project_name)
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        url = self.get_api_url(billing_project_name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project_name + "/" + workspace_name,
                "note": "test note",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a billing project.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        # Created a workspace.
        self.assertEqual(models.Workspace.objects.count(), 1)
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        self.assertEqual(new_workspace.note, "test note")
        self.assertEqual(new_workspace.billing_project, billing_project)

    def test_can_import_locked_workspace(self):
        """Sets note when specified when importing a workspace."""
        billing_project_name = "billing-project"
        billing_project = factories.BillingProjectFactory.create(name=billing_project_name)
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        url = self.get_api_url(billing_project_name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name, is_locked=True),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project_name + "/" + workspace_name,
                "note": "test note",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a billing project.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        # Created a workspace.
        self.assertEqual(models.Workspace.objects.count(), 1)
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        self.assertEqual(new_workspace.is_locked, True)
        self.assertEqual(new_workspace.billing_project, billing_project)

    def test_creates_default_workspace_data_without_custom_adapter(self):
        """The default workspace data object is created if no custom aadpter is used."""
        billing_project = factories.BillingProjectFactory.create()
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_workspace = models.Workspace.objects.latest("pk")
        # Also creates a workspace data object.
        self.assertEqual(models.DefaultWorkspaceData.objects.count(), 1)
        self.assertIsInstance(new_workspace.defaultworkspacedata, models.DefaultWorkspaceData)

    def test_success_message(self):
        """Can import a workspace from AnVIL when the billing project does not exist in Django and we are users."""
        billing_project = factories.BillingProjectFactory.create()
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceImport.success_message, str(messages[0]))

    def test_can_import_workspace_and_billing_project_as_not_user(self):
        """Can import a workspace from AnVIL when the billing project does not exist in Django and we are not users."""
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        # Billing project API call.
        billing_project_url = self.api_client.rawls_entry_point + "/api/billing/v2/" + billing_project_name
        self.anvil_response_mock.add(responses.GET, billing_project_url, status=404, json={"message": "other"})
        url = self.get_api_url(billing_project_name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project_name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a billing project.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        new_billing_project = models.BillingProject.objects.latest("pk")
        self.assertEqual(new_billing_project.name, billing_project_name)
        self.assertEqual(new_billing_project.has_app_as_user, False)
        # Created a workspace.
        self.assertEqual(models.Workspace.objects.count(), 1)
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        # History is added for the workspace.
        self.assertEqual(new_workspace.history.count(), 1)
        self.assertEqual(new_workspace.history.latest().history_type, "+")
        # History is added for the BillingProject.
        self.assertEqual(new_billing_project.history.count(), 1)
        self.assertEqual(new_billing_project.history.latest().history_type, "+")

    def test_can_import_workspace_with_existing_billing_project(self):
        """Can import a workspace from AnVIL when the billing project exists in Django."""
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a workspace.
        self.assertEqual(models.Workspace.objects.count(), 1)
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        # History is added for the workspace.
        self.assertEqual(new_workspace.history.count(), 1)
        self.assertEqual(new_workspace.history.latest().history_type, "+")
        # BillingProject is *not* updated.
        self.assertEqual(billing_project.history.count(), 1)
        self.assertEqual(billing_project.history.latest().history_type, "+")

    def test_can_import_workspace_with_auth_domain_in_app(self):
        """Can import a workspace with an auth domain that is already in the app."""
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        auth_domain = factories.ManagedGroupFactory.create(name="auth-domain")
        # Available workspaces API call.
        workspace_json = self.get_api_json_response(
            billing_project.name,
            workspace_name,
            authorization_domains=[auth_domain.name],
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            # Assume that this is the only workspace we can see on AnVIL.
            json=[workspace_json],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=workspace_json,
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a workspace.
        self.assertEqual(models.Workspace.objects.count(), 1)
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        # History is added for the workspace.
        self.assertEqual(new_workspace.history.count(), 1)
        self.assertEqual(new_workspace.history.latest().history_type, "+")
        # History is added for the authorization domain.
        self.assertEqual(models.WorkspaceAuthorizationDomain.history.count(), 1)
        self.assertEqual(models.WorkspaceAuthorizationDomain.history.latest().history_type, "+")

    def test_can_import_workspace_with_auth_domain_not_in_app(self):
        """Can import a workspace with an auth domain that is not already in the app."""
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        auth_domain_name = "auth-group"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[
                self.get_api_json_response(
                    billing_project.name,
                    workspace_name,
                    authorization_domains=[auth_domain_name],
                )
            ],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(
                billing_project.name,
                workspace_name,
                authorization_domains=[auth_domain_name],
            ),
        )
        # Add Response for the auth domain group.
        group_url = self.api_client.sam_entry_point + "/api/groups/v1"
        self.anvil_response_mock.add(
            responses.GET,
            group_url,
            status=200,
            # Assume we are not members since we didn't create the group ourselves.
            json=[
                {
                    "groupEmail": auth_domain_name + "@firecloud.org",
                    "groupName": auth_domain_name,
                    "role": "Member",
                }
            ],
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a workspace.
        self.assertEqual(models.Workspace.objects.count(), 1)
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        # History is added for the workspace.
        self.assertEqual(new_workspace.history.count(), 1)
        self.assertEqual(new_workspace.history.latest().history_type, "+")
        # An authorization domain group was created.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        group = models.ManagedGroup.objects.latest()
        self.assertEqual(group.name, auth_domain_name)
        # The workspace authorization domain relationship was created.
        auth_domain = models.WorkspaceAuthorizationDomain.objects.latest("pk")
        self.assertEqual(auth_domain.workspace, new_workspace)
        self.assertEqual(auth_domain.group, group)
        self.assertEqual(auth_domain.history.count(), 1)
        self.assertEqual(auth_domain.history.latest().history_type, "+")
        # History is added for the authorization domain.
        self.assertEqual(models.WorkspaceAuthorizationDomain.history.count(), 1)
        self.assertEqual(models.WorkspaceAuthorizationDomain.history.latest().history_type, "+")

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        new_object = models.Workspace.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())

    def test_workspace_already_imported(self):
        """Does not import a workspace that already exists in Django."""
        workspace = factories.WorkspaceFactory.create()
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(workspace.billing_project.name, workspace.name)],
        )
        # Messages need the client.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": workspace.billing_project.name + "/" + workspace.name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        # The form is valid but there was a different error. Is this really what we want?
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("valid", form.errors["workspace"][0])
        # Did not create any new BillingProjects.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        # Did not create eany new Workspaces.
        self.assertEqual(models.Workspace.objects.count(), 1)

    def test_invalid_workspace_name(self):
        """Does not create an object if workspace name is invalid."""
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response("foo", "bar")],
        )
        # No API call.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": "billing-project/workspace name",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("valid", form.errors["workspace"][0])
        # Did not create any objects.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response("foo", "bar")],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_other_anvil_api_error(self):
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=500,
            json={"message": "an error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project_name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        # The form is valid but there was a different error. Is this really what we want?
        self.assertTrue(form.is_valid())
        # Check messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: an error", str(messages[0]))
        # Did not create any objects.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_anvil_api_error_workspace_list_get(self):
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=500,
            json={"message": "an error"},
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        # Check messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceImport.message_error_fetching_workspaces, str(messages[0]))
        # Did not create any objects.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_anvil_api_error_workspace_list_post(self):
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=500,
            json={"message": "an error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": "billing-project/workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        # The form is not valid because workspaces couldn't be fetched.
        self.assertFalse(form.is_valid())
        # Check messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceImport.message_error_fetching_workspaces, str(messages[0]))
        # Did not create any objects.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_adapter_includes_workspace_data_formset(self):
        """Response includes the workspace data formset if specified."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = TestWorkspaceAdapter().get_type()
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertTrue("workspace_data_formset" in response.context_data)
        formset = response.context_data["workspace_data_formset"]
        self.assertIsInstance(formset, BaseInlineFormSet)
        self.assertEqual(len(formset.forms), 1)
        self.assertIsInstance(formset.forms[0], app_forms.TestWorkspaceDataForm)

    def test_adapter_creates_workspace_data(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = TestWorkspaceAdapter().get_type()
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-study_name": "test study",
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(
            new_workspace.workspace_type,
            TestWorkspaceAdapter().get_type(),
        )
        # Workspace data is added.
        self.assertEqual(app_models.TestWorkspaceData.objects.count(), 1)
        new_workspace_data = app_models.TestWorkspaceData.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.study_name, "test study")

    def test_adapter_does_not_create_objects_if_workspace_data_form_invalid(self):
        """Posting invalid data to the workspace_data_form form does not create a workspace when using an adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = TestWorkspaceAdapter().get_type()
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-study_name": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        # Workspace form is valid.
        form = response.context_data["form"]
        self.assertTrue(form.is_valid())
        # workspace_data_form is not valid.
        workspace_data_formset = response.context_data["workspace_data_formset"]
        self.assertEqual(workspace_data_formset.is_valid(), False)
        workspace_data_form = workspace_data_formset.forms[0]
        self.assertEqual(workspace_data_form.is_valid(), False)
        self.assertEqual(len(workspace_data_form.errors), 1)
        self.assertIn("study_name", workspace_data_form.errors)
        self.assertEqual(len(workspace_data_form.errors["study_name"]), 1)
        self.assertIn("required", workspace_data_form.errors["study_name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(app_models.TestWorkspaceData.objects.count(), 0)

    def test_imports_group_sharing(self):
        """Imports workspace group sharing when the group exists in the app."""
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        group = factories.ManagedGroupFactory.create()
        self.add_api_json_response_acl(group.email, "READER", can_compute=False, can_share=False)
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a workspace.
        self.assertEqual(models.Workspace.objects.count(), 1)
        new_workspace = models.Workspace.objects.latest("pk")
        # Created a workspace gropu sharing object.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertEqual(object.workspace, new_workspace)
        self.assertEqual(object.group, group)
        self.assertEqual(object.access, models.WorkspaceGroupSharing.READER)
        self.assertFalse(object.can_compute)

    def test_api_error_acl_call(self):
        """Shows a message when there is an API error with the ACL call."""
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=500,
            json={"message": "group api"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                "note": "test note",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        # The form is valid...
        self.assertTrue(form.is_valid())
        # Check messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "AnVIL API Error: group api")
        # Did not create any objects.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_get_workspace_data_with_second_foreign_key_to_workspace(self):
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestForeignKeyWorkspaceAdapter)
        self.workspace_type = TestForeignKeyWorkspaceAdapter().get_type()
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)

    def test_post_workspace_data_with_second_foreign_key_to_workspace(self):
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestForeignKeyWorkspaceAdapter)
        self.workspace_type = TestForeignKeyWorkspaceAdapter().get_type()
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        other_workspace = factories.WorkspaceFactory.create()
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-other_workspace": other_workspace.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(
            new_workspace.workspace_type,
            TestForeignKeyWorkspaceAdapter().get_type(),
        )
        # Workspace data is added.
        self.assertEqual(app_models.TestForeignKeyWorkspaceData.objects.count(), 1)
        new_workspace_data = app_models.TestForeignKeyWorkspaceData.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.other_workspace, other_workspace)

    def test_post_custom_adapter_after_anvil_import(self):
        """The after_anvil_create method is run after a workspace is imported."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestAfterWorkspaceImportAdapter)
        self.workspace_type = TestAfterWorkspaceImportAdapter().get_type()
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        # Available workspaces API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.workspace_list_url,
            match=[
                responses.matchers.query_param_matcher({"fields": "workspace.namespace,workspace.name,accessLevel"})
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-test_field": "my field value",
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = models.Workspace.objects.latest("pk")
        # The test_field field was modified by the adapter.
        self.assertEqual(new_workspace.testworkspacemethodsdata.test_field, "imported!")


class WorkspaceCloneTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the WorkspaceClone view."""

    api_success_code = 201

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.workspace_to_clone = factories.WorkspaceFactory.create()
        self.api_url = self.api_client.rawls_entry_point + "/api/workspaces/{}/{}/clone".format(
            self.workspace_to_clone.billing_project.name,
            self.workspace_to_clone.name,
        )
        self.workspace_type = DefaultWorkspaceAdapter.type

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        super().tearDown()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:clone", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceClone.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        response = self.client.get(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            )
        )
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            )
        )
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug=self.workspace_to_clone.billing_project.name,
                workspace_slug=self.workspace_to_clone.name,
                workspace_type=self.workspace_type,
            )

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar", self.workspace_type))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            )
        )
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug=self.workspace_to_clone.billing_project.name,
                workspace_slug=self.workspace_to_clone.name,
                workspace_type=self.workspace_type,
            )

    def test_get_workspace_type_not_registered(self):
        """Raises 404 with get request if workspace type is not registered with adapter."""
        request = self.factory.get(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                "foo",
            )
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.workspace_to_clone.billing_project.name,
                workspace_slug=self.workspace_to_clone.name,
                workspace_type="foo",
            )

    def test_post_workspace_type_not_registered(self):
        """Raises 404 with post request if workspace type is not registered with adapter."""
        request = self.factory.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                "foo",
            ),
            {},
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.workspace_to_clone.billing_project.name,
                workspace_slug=self.workspace_to_clone.name,
                workspace_type="foo",
            )

    def test_get_workspace_not_found(self):
        """Raises a 404 error when workspace does not exist."""
        request = self.factory.get(self.get_url("foo", "bar", self.workspace_type))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="foo",
                workspace_slug="bar",
                workspace_type=self.workspace_type,
            )

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            )
        )
        self.assertTrue("form" in response.context_data)
        # self.assertIsInstance(response.context_data["form"], (forms.WorkspaceForm, forms.WorkspaceCloneFormMixin))
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceForm)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceCloneFormMixin)

    def test_has_formset_in_context(self):
        """Response includes a formset for the workspace_data model."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            )
        )
        self.assertTrue("workspace_data_formset" in response.context_data)
        formset = response.context_data["workspace_data_formset"]
        self.assertIsInstance(formset, BaseInlineFormSet)
        self.assertEqual(len(formset.forms), 1)
        self.assertIsInstance(formset.forms[0], forms.DefaultWorkspaceDataForm)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.Workspace.objects.latest("pk")
        self.assertIsInstance(new_object, models.Workspace)
        self.assertEqual(
            new_object.workspace_type,
            DefaultWorkspaceAdapter().get_type(),
        )
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_create_object_with_auth_domains(self):
        """Posting valid data to the form creates an object."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.workspace_to_clone.authorization_domains.add(auth_domain)
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [{"membersGroupName": auth_domain.name}],
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.Workspace.objects.latest("pk")
        self.assertIsInstance(new_object, models.Workspace)
        # Has an auth domain.
        self.assertEqual(new_object.authorization_domains.count(), 1)
        self.assertIn(auth_domain, new_object.authorization_domains.all())
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_add_an_auth_domains(self):
        """Posting valid data to the form creates an object."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.workspace_to_clone.authorization_domains.add(auth_domain)
        new_auth_domain = factories.ManagedGroupFactory.create()
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [
                {"membersGroupName": auth_domain.name},
                {"membersGroupName": new_auth_domain.name},
            ],
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk, new_auth_domain.pk],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.Workspace.objects.latest("pk")
        self.assertIsInstance(new_object, models.Workspace)
        # Has an auth domain.
        self.assertEqual(new_object.authorization_domains.count(), 2)
        self.assertIn(auth_domain, new_object.authorization_domains.all())
        self.assertIn(new_auth_domain, new_object.authorization_domains.all())

    def test_creates_default_workspace_data(self):
        """Posting valid data to the form creates the default workspace data object."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_workspace = models.Workspace.objects.latest("pk")
        # Also creates a workspace data object.
        self.assertEqual(models.DefaultWorkspaceData.objects.count(), 1)
        self.assertIsInstance(new_workspace.defaultworkspacedata, models.DefaultWorkspaceData)

    def test_success_message(self):
        """Response includes a success message if successful."""
        billing_project = factories.BillingProjectFactory.create()
        json_data = {
            "namespace": billing_project.name,
            "name": "test-workspace",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceCreate.success_message, str(messages[0]))

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        billing_project = factories.BillingProjectFactory.create()
        json_data = {
            "namespace": billing_project.name,
            "name": "test-workspace",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        new_object = models.Workspace.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())

    def test_cannot_create_duplicate_object(self):
        """Cannot create two workspaces with the same billing project and name."""
        obj = factories.WorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": obj.billing_project.pk,
                "name": obj.name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertEqual(models.Workspace.objects.count(), 2)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())
        self.assertIn(obj, models.Workspace.objects.all())

    def test_can_create_workspace_with_same_billing_project_different_name(self):
        """Can create a workspace with a different name in the same billing project."""
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(billing_project=billing_project, name="test-name-1")
        json_data = {
            "namespace": billing_project.name,
            "name": "test-name-2",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-name-2",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 3)
        # Make sure you can get the new object.
        models.Workspace.objects.get(billing_project=billing_project, name="test-name-2")

    def test_can_create_workspace_with_same_name_different_billing_project(self):
        """Can create a workspace with the same name in a different billing project."""
        billing_project_1 = factories.BillingProjectFactory.create(name="project-1")
        billing_project_2 = factories.BillingProjectFactory.create(name="project-2")
        workspace_name = "test-name"
        factories.WorkspaceFactory.create(billing_project=billing_project_1, name=workspace_name)
        json_data = {
            "namespace": billing_project_2.name,
            "name": "test-name",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project_2.pk,
                "name": workspace_name,
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 3)
        # Make sure you can get the new object.
        models.Workspace.objects.get(billing_project=billing_project_2, name=workspace_name)

    def test_invalid_input_name(self):
        """Posting invalid data to name field does not create an object."""
        billing_project = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "invalid name",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("slug", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())
        self.assertEqual(len(responses.calls), 0)

    def test_invalid_input_billing_project(self):
        """Posting invalid data to billing_project field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": 100,
                "name": "test-name",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("valid choice", form.errors["billing_project"][0])
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())
        self.assertEqual(len(responses.calls), 0)

    def test_post_invalid_name_billing_project(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("required", form.errors["billing_project"][0])
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())
        self.assertEqual(len(responses.calls), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("required", form.errors["billing_project"][0])
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())

    def test_api_error_message(self):
        """Shows a method if an AnVIL API error occurs."""
        billing_project = factories.BillingProjectFactory.create()
        json_data = {
            "namespace": billing_project.name,
            "name": "test-workspace",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=500,
            match=[responses.matchers.json_params_matcher(json_data)],
            json={"message": "workspace create test error"},
        )
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error: workspace create test error", str(messages[0]))
        # Make sure that no object is created.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())

    def test_invalid_auth_domain(self):
        """Does not create a workspace when an invalid authorization domain is specified."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [1],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("authorization_domains", form.errors.keys())
        self.assertIn("valid choice", form.errors["authorization_domains"][0])
        # No object was created.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())

    def test_one_valid_one_invalid_auth_domain(self):
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        auth_domain = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk, auth_domain.pk + 1],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("authorization_domains", form.errors.keys())
        self.assertIn("valid choice", form.errors["authorization_domains"][0])
        # No object was created.
        self.assertEqual(len(models.Workspace.objects.all()), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())

    def test_auth_domain_does_not_exist_on_anvil(self):
        """No workspace is displayed if the auth domain group doesn't exist on AnVIL."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        auth_domain = factories.ManagedGroupFactory.create()
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [
                {"membersGroupName": auth_domain.name},
            ],
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=400,
            json={"message": "api error"},
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        # The form is valid but there was an API error.
        form = response.context_data["form"]
        self.assertTrue(form.is_valid())
        # Check messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: api error", str(messages[0]))
        # Did not create any new Workspaces.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())

    def test_not_admin_of_auth_domain_on_anvil(self):
        """No workspace is displayed if we are not the admins of the auth domain on AnVIL."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        auth_domain = factories.ManagedGroupFactory.create()
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [
                {"membersGroupName": auth_domain.name},
            ],
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=400,
            json={"message": "api error"},
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk],
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        # The form is valid but there was an API error.
        form = response.context_data["form"]
        self.assertTrue(form.is_valid())
        # Check messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: api error", str(messages[0]))
        # Did not create any new Workspaces.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())

    def test_not_user_of_billing_project(self):
        """Posting a billing project where we are not users does not create an object."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project", has_app_as_user=False)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("must have has_app_as_user set to True", form.errors["billing_project"][0])
        # No workspace was created.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())

    def test_adapter_includes_workspace_data_formset(self):
        """Response includes the workspace data formset if specified."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = "test"
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            )
        )
        self.assertTrue("workspace_data_formset" in response.context_data)
        formset = response.context_data["workspace_data_formset"]
        self.assertIsInstance(formset, BaseInlineFormSet)
        self.assertEqual(len(formset.forms), 1)
        self.assertIsInstance(formset.forms[0], app_forms.TestWorkspaceDataForm)

    def test_adapter_creates_workspace_data(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = "test"
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-study_name": "test study",
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = models.Workspace.objects.latest("pk")
        # workspace_type is set properly.
        self.assertEqual(
            new_workspace.workspace_type,
            TestWorkspaceAdapter().get_type(),
        )
        # Workspace data is added.
        self.assertEqual(app_models.TestWorkspaceData.objects.count(), 1)
        new_workspace_data = app_models.TestWorkspaceData.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.study_name, "test study")

    def test_adapter_does_not_create_objects_if_workspace_data_form_invalid(self):
        """Posting invalid data to the workspace_data_form form does not create a workspace when using an adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = "test"
        billing_project = factories.BillingProjectFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-study_name": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        # Workspace form is valid.
        form = response.context_data["form"]
        self.assertTrue(form.is_valid())
        # workspace_data_form is not valid.
        workspace_data_formset = response.context_data["workspace_data_formset"]
        self.assertEqual(workspace_data_formset.is_valid(), False)
        workspace_data_form = workspace_data_formset.forms[0]
        self.assertEqual(workspace_data_form.is_valid(), False)
        self.assertEqual(len(workspace_data_form.errors), 1)
        self.assertIn("study_name", workspace_data_form.errors)
        self.assertEqual(len(workspace_data_form.errors["study_name"]), 1)
        self.assertIn("required", workspace_data_form.errors["study_name"][0])
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())
        self.assertEqual(app_models.TestWorkspaceData.objects.count(), 0)

    def test_adapter_custom_workspace_form_class(self):
        """Form uses the custom workspace form as a superclass."""
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = "test"
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            )
        )
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], app_forms.TestWorkspaceForm)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceCloneFormMixin)

    def test_adapter_custom_workspace_form_with_error_in_workspace_form(self):
        """Form uses the custom workspace form as a superclass."""
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        billing_project = factories.BillingProjectFactory.create()
        self.workspace_type = "test"
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-fail",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-study_name": "test study",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("Workspace name cannot be", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 1)  # the workspace to clone
        self.assertEqual(app_models.TestWorkspaceData.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_workspace_to_clone_does_not_exist_on_anvil(self):
        """Shows a method if an AnVIL API 404 error occurs."""
        billing_project = factories.BillingProjectFactory.create()
        json_data = {
            "namespace": billing_project.name,
            "name": "test-workspace",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=404,
            match=[responses.matchers.json_params_matcher(json_data)],
            json={"message": "workspace create test error"},
        )
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error: workspace create test error", str(messages[0]))
        # Make sure that no object is created.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace_to_clone, models.Workspace.objects.all())

    def test_get_workspace_data_with_second_foreign_key_to_workspace(self):
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestForeignKeyWorkspaceAdapter)
        self.workspace_type = "test_fk"
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
        )
        self.assertEqual(response.status_code, 200)

    def test_post_workspace_data_with_second_foreign_key_to_workspace(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestForeignKeyWorkspaceAdapter)
        self.workspace_type = TestForeignKeyWorkspaceAdapter().get_type()
        other_workspace = factories.WorkspaceFactory.create()
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-other_workspace": other_workspace.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = models.Workspace.objects.latest("pk")
        # workspace_type is set properly.
        self.assertEqual(
            new_workspace.workspace_type,
            TestForeignKeyWorkspaceAdapter().get_type(),
        )
        # Workspace data is added.
        self.assertEqual(app_models.TestForeignKeyWorkspaceData.objects.count(), 1)
        new_workspace_data = app_models.TestForeignKeyWorkspaceData.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.other_workspace, other_workspace)

    def test_post_custom_adapter_before_anvil_create(self):
        """The before_anvil_create method is run before a workspace is created."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestBeforeWorkspaceCreateAdapter)
        self.workspace_type = TestBeforeWorkspaceCreateAdapter().get_type()
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace-2",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-test_field": "my field value",
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, "test-workspace-2")

    def test_post_custom_adapter_after_anvil_create(self):
        """The after_anvil_create method is run after a workspace is created."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestAfterWorkspaceCreateAdapter)
        self.workspace_type = TestAfterWorkspaceCreateAdapter().get_type()
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "copyFilesWithPrefix": "notebooks",
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace_to_clone.billing_project.name,
                self.workspace_to_clone.name,
                self.workspace_type,
            ),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-test_field": "my field value",
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = models.Workspace.objects.latest("pk")
        # The test_field field was modified by the adapter.
        self.assertEqual(new_workspace.testworkspacemethodsdata.test_field, "FOO")


class WorkspaceUpdateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.workspace_data = factories.DefaultWorkspaceDataFactory.create()
        self.workspace = self.workspace_data.workspace

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        super().tearDown()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:update:internal", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceUpdate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project, self.workspace.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, billing_project_slug="foo", workspace_slug="bar")

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, billing_project_slug="foo", workspace_slug="bar")

    def test_object_does_not_exist(self):
        """Raises Http404 if object does not exist."""
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, billing_project_slug="foo", workspace_slug="bar")

    def test_context_workspace_data(self):
        """The view adds the workspace_data object to the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        response.context_data
        self.assertIn("workspace_data_object", response.context_data)
        self.assertEqual(response.context_data["workspace_data_object"], self.workspace_data)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("form", response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceForm)

    def test_form_fields(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        form = response.context_data.get("form")
        self.assertEqual(len(form.fields), 2)  # is_requester_pays and is_locked
        self.assertIn("note", form.fields)

    def test_has_formset_in_context(self):
        """Response includes a formset for the workspace_data model."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertTrue("workspace_data_formset" in response.context_data)
        formset = response.context_data["workspace_data_formset"]
        self.assertIsInstance(formset, BaseInlineFormSet)
        self.assertEqual(len(formset.forms), 1)
        self.assertIsInstance(formset.forms[0], forms.DefaultWorkspaceDataForm)

    def test_can_modify_note(self):
        """Can set the note when creating a billing project."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "note": "new note",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 1,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-id": self.workspace_data.pk,
                "workspacedata-0-workspace": self.workspace.pk,
                "workspacedata-0-study_name": "updated name",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.workspace_data.refresh_from_db()
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.note, "new note")

    def test_success_message(self):
        """Response includes a success message if successful."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "note": "new note",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 1,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-id": self.workspace_data.pk,
                "workspacedata-0-workspace": self.workspace.pk,
                "workspacedata-0-study_name": "updated name",
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceUpdate.success_message, str(messages[0]))

    def test_redirects_to_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "note": "new note",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 1,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-id": self.workspace_data.pk,
                "workspacedata-0-workspace": self.workspace.pk,
                "workspacedata-0-study_name": "updated name",
            },
        )
        self.assertRedirects(response, self.workspace.get_absolute_url())

    def test_can_update_workspace_data(self):
        """Can update workspace data when updating the workspace."""
        # Note that we need to use the test adapter for this.
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        workspace = factories.WorkspaceFactory(workspace_type=TestWorkspaceAdapter().get_type())
        workspace_data = app_models.TestWorkspaceData.objects.create(workspace=workspace, study_name="original name")
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(workspace.billing_project.name, workspace.name),
            {
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 1,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-id": workspace_data.pk,
                "workspacedata-0-workspace": workspace.pk,
                "workspacedata-0-study_name": "updated name",
            },
        )
        self.assertEqual(response.status_code, 302)
        workspace_data.refresh_from_db()
        self.assertEqual(workspace_data.study_name, "updated name")

    def test_custom_adapter_workspace_data(self):
        # Note that we need to use the test adapter for this.
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        workspace = factories.WorkspaceFactory(workspace_type=TestWorkspaceAdapter().get_type())
        app_models.TestWorkspaceData.objects.create(workspace=workspace, study_name="original name")
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(workspace.billing_project.name, workspace.name))
        self.assertTrue("workspace_data_formset" in response.context_data)
        formset = response.context_data["workspace_data_formset"]
        self.assertIsInstance(formset, BaseInlineFormSet)
        self.assertEqual(len(formset.forms), 1)
        self.assertIsInstance(formset.forms[0], app_forms.TestWorkspaceDataForm)

    def test_no_updates_if_invalid_workspace_data_form(self):
        """Nothing is updated if workspace_data_form is invalid."""
        # Note that we need to use the test adapter for this.
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        workspace = factories.WorkspaceFactory(
            workspace_type=TestWorkspaceAdapter().get_type(),
            note="original note",
        )
        workspace_data = app_models.TestWorkspaceData.objects.create(workspace=workspace, study_name="original name")
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(workspace.billing_project.name, workspace.name),
            {
                "note": "updated note",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-id": workspace_data.pk,
                "workspacedata-0-workspace": workspace.pk,
                "workspacedata-0-study_name": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        workspace.refresh_from_db()
        workspace_data.refresh_from_db()
        self.assertEqual(workspace.note, "original note")
        self.assertEqual(workspace_data.study_name, "original name")

    def test_custom_adapter_workspace_form(self):
        """Workspace form is subclass of the custom adapter form."""
        # Note that we need to use the test adapter for this.
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        workspace = factories.WorkspaceFactory(workspace_type=TestWorkspaceAdapter().get_type())
        app_models.TestWorkspaceData.objects.create(workspace=workspace, study_name="original name")
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(workspace.billing_project.name, workspace.name))
        self.assertTrue("form" in response.context_data)
        form = response.context_data["form"]
        self.assertIsInstance(form, TestWorkspaceAdapter().get_workspace_form_class())
        self.assertEqual(len(form.fields), 2)  # is_requester_pays and is_locked
        self.assertIn("note", form.fields)

    def test_get_workspace_data_with_second_foreign_key_to_workspace(self):
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestForeignKeyWorkspaceAdapter)
        other_workspace = factories.WorkspaceFactory.create()
        workspace = factories.WorkspaceFactory(workspace_type=TestForeignKeyWorkspaceAdapter().get_type())
        app_models.TestForeignKeyWorkspaceData.objects.create(workspace=workspace, other_workspace=other_workspace)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(workspace.billing_project.name, workspace.name))
        self.assertEqual(response.status_code, 200)

    def test_post_workspace_data_with_second_foreign_key_to_workspace(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.register(TestForeignKeyWorkspaceAdapter)
        other_workspace = factories.WorkspaceFactory.create()
        workspace = factories.WorkspaceFactory(workspace_type=TestForeignKeyWorkspaceAdapter().get_type())
        app_models.TestForeignKeyWorkspaceData.objects.create(workspace=workspace, other_workspace=other_workspace)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "note": "Foo",
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 1,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-id": self.workspace_data.pk,
                "workspacedata-0-other_workspace": other_workspace,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.workspace_data.refresh_from_db()
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.note, "Foo")


class WorkspaceUpdateRequesterPaysTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the WorkspaceUpdateRequesterPays view."""

    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        workspace_data = factories.DefaultWorkspaceDataFactory.create()
        self.workspace = workspace_data.workspace
        self.api_url = self.api_client.rawls_entry_point + "/api/workspaces/v2/{}/{}/settings".format(
            self.workspace.billing_project.name, self.workspace.name
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:update:requester_pays", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceUpdateRequesterPays.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_staff_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceRequesterPaysForm)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="foo",
                workspace_slug="bar",
            )

    def test_view_with_invalid_billing_project(self):
        """Returns a 404 when the billing project doesn't exist."""
        request = self.factory.get(self.get_url("foo", self.workspace.name))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="foo",
                workspace_slug=self.workspace.name,
            )

    def test_view_with_invalid_workspace(self):
        """Returns a 404 when the workspace name doesn't exist."""
        request = self.factory.get(self.get_url(self.workspace.billing_project.name, "foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug="foo",
            )

    def test_can_update_requester_pays_false_to_true(self):
        """Can update is_requester_pays through the view."""
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url,
            status=self.api_success_code,
            json={
                "failures": {},
                "successes": [{"config": {"enabled": True}, "settingType": "GcpBucketRequesterPays"}],
            },
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "is_requester_pays": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.workspace.refresh_from_db()
        self.assertTrue(self.workspace.is_requester_pays)
        # History is added.
        self.assertEqual(self.workspace.history.count(), 2)
        self.assertEqual(self.workspace.history.latest().history_type, "~")

    def test_can_update_requester_pays_true_to_false(self):
        """Can update is_requester_pays through the view."""
        self.workspace.is_requester_pays = True
        self.workspace.save()
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url,
            status=self.api_success_code,
            json={
                "failures": {},
                "successes": [{"config": {"enabled": False}, "settingType": "GcpBucketRequesterPays"}],
            },
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "is_requester_pays": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.workspace.refresh_from_db()
        self.assertFalse(self.workspace.is_requester_pays)
        # History is added.
        self.assertEqual(self.workspace.history.count(), 3)  # 3 because we modified the object above.
        self.assertEqual(self.workspace.history.latest().history_type, "~")

    def test_can_update_requester_pays_false_to_false(self):
        """Can update is_requester_pays through the view."""
        # No API calls should be made because nothing is changing.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "is_requester_pays": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.workspace.refresh_from_db()
        self.assertFalse(self.workspace.is_requester_pays)

    def test_can_update_requester_pays_true_to_true(self):
        """Can update is_requester_pays through the view."""
        self.workspace.is_requester_pays = True
        self.workspace.save()
        # No API calls should be made because nothing is changing.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "is_requester_pays": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.workspace.refresh_from_db()
        self.assertTrue(self.workspace.is_requester_pays)

    def test_redirects_to_object_detail(self):
        """After successfully updating the object, view redirects to the object's detail page."""
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url,
            status=self.api_success_code,
            json={
                "failures": {},
                "successes": [{"config": {"enabled": True}, "settingType": "GcpBucketRequesterPays"}],
            },
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "is_requester_pays": True,
            },
        )
        self.assertRedirects(response, self.workspace.get_absolute_url())

    def test_success_message(self):
        """Response includes a success message if successful."""
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url,
            status=self.api_success_code,
            json={
                "failures": {},
                "successes": [{"config": {"enabled": True}, "settingType": "GcpBucketRequesterPays"}],
            },
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "is_requester_pays": True,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceUpdateRequesterPays.success_message, str(messages[0]))

    def test_api_error_message(self):
        """Shows a method if an AnVIL API error occurs."""
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url,
            status=500,
            json={"message": "workspace update requester pays test error"},
        )
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "is_requester_pays": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error: workspace update requester pays test error", str(messages[0]))
        # Make sure that no object is created.
        self.workspace.refresh_from_db()
        self.assertFalse(self.workspace.is_requester_pays)


class WorkspaceListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.staff_view_user = User.objects.create_user(username="test-staff-view", password="test")
        self.staff_view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        # Create a user with view permission
        self.view_user = User.objects.create_user(username="test-view", password="test")
        self.view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        self.workspace_type = DefaultWorkspaceAdapter().get_type()

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        super().tearDown()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:list_all", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(),
        )

    def test_status_code_with_staff_view_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.staff_view_user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Returns successful response code if user has view permission."""
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_without_view_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class_staff_view(self):
        """Context has correct table class when user has staff view permission."""
        self.client.force_login(self.staff_view_user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.WorkspaceStaffTable)

    def test_view_has_correct_table_class_view(self):
        """Context has correct table class when user has view permission."""
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.WorkspaceUserTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.WorkspaceFactory()
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.WorkspaceFactory.create(name="w1")
        factories.WorkspaceFactory.create(name="w2")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_only_shows_workspaces_of_any_type(self):
        """The table includes all workspaces regardless of type."""
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        test_workspace = factories.WorkspaceFactory(workspace_type=TestWorkspaceAdapter().get_type())
        default_workspace = factories.WorkspaceFactory(workspace_type=DefaultWorkspaceAdapter().get_type())
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)
        self.assertIn(test_workspace, response.context_data["table"].data)
        self.assertIn(default_workspace, response.context_data["table"].data)

    def test_context_workspace_type_display_name(self):
        """Context contains workspace_type_display_name and is set properly."""
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("workspace_type_display_name", response.context_data)
        self.assertEqual(response.context_data["workspace_type_display_name"], "All workspace")

    def test_view_with_filter_return_no_object(self):
        factories.WorkspaceFactory.create(name="workspace1")
        factories.WorkspaceFactory.create(name="workspace2")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(), {"name__icontains": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_returns_one_object_exact(self):
        instance = factories.WorkspaceFactory.create(name="workspace1")
        factories.WorkspaceFactory.create(name="workspace2")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(), {"name__icontains": "workspace1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_case_insensitive(self):
        instance = factories.WorkspaceFactory.create(name="workspace1")
        factories.WorkspaceFactory.create(name="workspace2")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(), {"name__icontains": "Workspace1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_case_contains(self):
        instance = factories.WorkspaceFactory.create(name="workspace1")
        factories.WorkspaceFactory.create(name="workspace2")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(), {"name__icontains": "orkspace1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_mutiple_objects(self):
        factories.WorkspaceFactory.create(name="workspace1")
        factories.WorkspaceFactory.create(name="wOrkspace1")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(), {"name__icontains": "Workspace"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class WorkspaceListByTypeTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with staff view permission.
        self.staff_view_user = User.objects.create_user(username="test-staff-view", password="test")
        self.staff_view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        # Create a user with view permission
        self.view_user = User.objects.create_user(username="test-view", password="test")
        self.view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        self.workspace_type = DefaultWorkspaceAdapter().get_type()

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        super().tearDown()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceListByType.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.workspace_type),
        )

    def test_status_code_with_staff_view_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.staff_view_user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, workspace_type=self.workspace_type)

    def test_get_workspace_type_not_registered(self):
        """Raises 404 with get request if workspace type is not registered with adapter."""
        request = self.factory.get(self.get_url("foo"))
        request.user = self.view_user
        with self.assertRaises(Http404):
            self.get_view()(request, workspace_type="foo")

    def test_view_has_correct_table_class_staff_view(self):
        self.client.force_login(self.staff_view_user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.WorkspaceStaffTable)

    def test_view_has_correct_table_class_view(self):
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.WorkspaceUserTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.WorkspaceFactory()
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.WorkspaceFactory.create(name="w1")
        factories.WorkspaceFactory.create(name="w2")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_adapter_table_class_staff_view(self):
        """Displays the correct table if specified in the adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = TestWorkspaceAdapter().get_type()
        self.client.force_login(self.staff_view_user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], app_tables.TestWorkspaceDataStaffTable)

    def test_adapter_table_class_view(self):
        """Displays the correct table if specified in the adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = TestWorkspaceAdapter().get_type()
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], app_tables.TestWorkspaceDataUserTable)

    def test_only_shows_workspaces_with_correct_type(self):
        """Only workspaces with the same workspace_type are shown in the table."""
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        factories.WorkspaceFactory(workspace_type=TestWorkspaceAdapter().get_type())
        default_type = DefaultWorkspaceAdapter().get_type()
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(default_type))
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_return_no_object(self):
        factories.WorkspaceFactory.create(name="workspace1")
        factories.WorkspaceFactory.create(name="workspace2")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type), {"name__icontains": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_returns_one_object_exact(self):
        instance = factories.WorkspaceFactory.create(name="workspace1")
        factories.WorkspaceFactory.create(name="workspace2")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type), {"name__icontains": "workspace1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_case_insensitive(self):
        instance = factories.WorkspaceFactory.create(name="workspace1")
        factories.WorkspaceFactory.create(name="workspace2")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type), {"name__icontains": "Workspace1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_one_object_case_contains(self):
        instance = factories.WorkspaceFactory.create(name="workspace1")
        factories.WorkspaceFactory.create(name="workspace2")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type), {"name__icontains": "orkspace1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_workspace_type(self):
        instance = factories.WorkspaceFactory.create(name="workspace1")
        factories.WorkspaceFactory.create(name="workspace2", workspace_type=TestWorkspaceAdapter().get_type())
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type), {"name__icontains": "workspace"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_returns_mutiple_objects(self):
        factories.WorkspaceFactory.create(name="workspace1")
        factories.WorkspaceFactory.create(name="wOrkspace1")
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type), {"name__icontains": "Workspace"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_default_adapter_use_default_workspace_list_template(self):
        default_type = DefaultWorkspaceAdapter().get_type()
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(default_type))
        self.assertTemplateUsed(response, "anvil_consortium_manager/workspace_list.html")

    def test_view_with_custom_adapter_use_custom_workspace_list_template(self):
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = TestWorkspaceAdapter().get_type()
        self.client.force_login(self.view_user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertTemplateUsed(response, "test_workspace_list.html")


class WorkspaceDeleteTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 202

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        super().tearDown()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:delete", args=args)

    def get_api_url(self, billing_project_name, workspace_name):
        return self.api_client.rawls_entry_point + "/api/workspaces/" + billing_project_name + "/" + workspace_name

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceDelete.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        url = self.get_url("foo1", "foo2")
        response = self.client.get(url)
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + url)

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.WorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.billing_project.name, obj.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo1", "foo2"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=1)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo1", "foo2"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=1)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url("foo1", "foo2"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, pk=1)

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        object = factories.WorkspaceFactory.create(billing_project=billing_project, name="test-workspace")
        api_url = self.get_api_url(object.billing_project.name, object.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.billing_project.name, object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 0)
        # History is added.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        object = factories.WorkspaceFactory.create(billing_project=billing_project, name="test-workspace")
        api_url = self.get_api_url(object.billing_project.name, object.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.billing_project.name, object.name),
            {"submit": ""},
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceDelete.success_message, str(messages[0]))

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.WorkspaceFactory.create()
        other_object = factories.WorkspaceFactory.create()
        api_url = self.get_api_url(object.billing_project.name, object.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.billing_project.name, object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertQuerySetEqual(
            models.Workspace.objects.all(),
            models.Workspace.objects.filter(pk=other_object.pk),
        )

    def test_can_delete_workspace_with_auth_domain(self):
        """A workspace can be deleted if it has an auth domain, and the auth domain group is not deleted."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        object = factories.WorkspaceFactory.create(billing_project=billing_project, name="test-workspace")
        auth_domain = factories.ManagedGroupFactory.create(name="test-group")
        wad = models.WorkspaceAuthorizationDomain.objects.create(workspace=object, group=auth_domain)
        # object.authorization_domains.add(auth_domain)
        api_url = self.get_api_url(object.billing_project.name, object.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.billing_project.name, object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.WorkspaceAuthorizationDomain.objects.count(), 0)
        # The auth domain group still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        models.ManagedGroup.objects.get(pk=auth_domain.pk)
        # History is added for workspace.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "-")
        # History is added for auth domain.
        self.assertEqual(wad.history.count(), 2)
        self.assertEqual(wad.history.latest().history_type, "-")

    def test_can_delete_workspace_that_has_been_shared_with_group(self):
        """A workspace can be deleted if it has been shared with a group, and the group is not deleted."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        object = factories.WorkspaceFactory.create(billing_project=billing_project, name="test-workspace")
        group = factories.ManagedGroupFactory.create(name="test-group")
        factories.WorkspaceGroupSharingFactory.create(workspace=object, group=group)
        api_url = self.get_api_url(object.billing_project.name, object.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.billing_project.name, object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)
        # The group still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        models.ManagedGroup.objects.get(pk=group.pk)
        # History is added for workspace.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "-")
        # History is added for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.history.count(), 2)
        self.assertEqual(models.WorkspaceGroupSharing.history.latest().history_type, "-")

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.WorkspaceFactory.create()
        # Need to use the client instead of RequestFactory to check redirection url.
        api_url = self.get_api_url(object.billing_project.name, object.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.billing_project.name, object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:list",
                args=[DefaultWorkspaceAdapter().get_type()],
            ),
        )

    def test_adapter_success_url(self):
        """Redirects to the expected page."""
        # Register a new adapter.
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        object = factories.WorkspaceFactory.create(workspace_type=TestWorkspaceAdapter().get_type())
        # Need to use the client instead of RequestFactory to check redirection url.
        api_url = self.get_api_url(object.billing_project.name, object.name)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.billing_project.name, object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:list",
                args=[TestWorkspaceAdapter().get_type()],
            ),
        )

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.WorkspaceFactory.create()
        api_url = self.get_api_url(object.billing_project.name, object.name)
        self.anvil_response_mock.add(
            responses.DELETE,
            api_url,
            status=500,
            json={"message": "workspace delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.billing_project.name, object.name), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error: workspace delete test error", str(messages[0]))
        # Make sure that the object still exists.
        self.assertEqual(models.Workspace.objects.count(), 1)

    def test_post_does_not_delete_when_protected_fk_to_another_model(self):
        """Workspace is not deleted when there is a protected foreign key reference to the workspace."""
        object = factories.DefaultWorkspaceDataFactory.create()
        app_models.ProtectedWorkspace.objects.create(workspace=object.workspace)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.workspace.billing_project.name, object.workspace.name),
            {"submit": ""},
            follow=True,
        )
        self.assertRedirects(response, object.get_absolute_url())
        # A message is added.
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceDelete.message_could_not_delete_workspace_from_app,
            str(messages[0]),
        )
        # Make sure the group still exists.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertEqual(models.DefaultWorkspaceData.objects.count(), 1)
        object.refresh_from_db()

    def test_post_does_not_delete_when_workspace_data_has_protected_fk_to_another_model(
        self,
    ):
        """Workspace is not deleted when there is a protected foreign key reference to the workspace data."""
        workspace_data = factories.DefaultWorkspaceDataFactory()
        object = workspace_data.workspace
        app_models.ProtectedWorkspaceData.objects.create(workspace_data=workspace_data)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.billing_project.name, object.name),
            {"submit": ""},
            follow=True,
        )
        self.assertRedirects(response, object.get_absolute_url())
        # A message is added.
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceDelete.message_could_not_delete_workspace_from_app,
            str(messages[0]),
        )
        # Make sure the group still exists.
        self.assertEqual(models.Workspace.objects.count(), 1)
        object.refresh_from_db()

    def test_get_is_locked(self):
        """View redirects with a get request if the workspace is locked."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        object = factories.DefaultWorkspaceDataFactory.create(
            workspace__billing_project=billing_project,
            workspace__name="test-workspace",
            workspace__is_locked=True,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(object.workspace.billing_project.name, object.workspace.name),
            follow=True,
        )
        # Make sure the workspace still exists.
        self.assertIn(object.workspace, models.Workspace.objects.all())
        self.assertIn(object, models.DefaultWorkspaceData.objects.all())
        # Redirects to detail page.
        self.assertRedirects(response, object.get_absolute_url())
        # With a message.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceDelete.message_workspace_locked, str(messages[0]))

    def test_post_is_locked(self):
        """View redirects with a post request if the workspace is locked."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        object = factories.DefaultWorkspaceDataFactory.create(
            workspace__billing_project=billing_project,
            workspace__name="test-workspace",
            workspace__is_locked=True,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.workspace.billing_project.name, object.workspace.name),
            {"submit": ""},
            follow=True,
        )
        # Make sure the workspace still exists.
        self.assertIn(object.workspace, models.Workspace.objects.all())
        self.assertIn(object, models.DefaultWorkspaceData.objects.all())
        # Redirects to detail page.
        self.assertRedirects(response, object.get_absolute_url())
        # With a message.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceDelete.message_workspace_locked, str(messages[0]))


class WorkspaceAutocompleteTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with the correct permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:autocomplete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceAutocomplete.as_view()

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

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_returns_all_objects(self):
        """Queryset returns all objects when there is no query."""
        groups = factories.WorkspaceFactory.create_batch(10)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 10)
        self.assertEqual(sorted(returned_ids), sorted([group.pk for group in groups]))

    def test_returns_correct_object_match(self):
        """Queryset returns the correct objects when query matches the name."""
        workspace = factories.WorkspaceFactory.create(name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "test-workspace"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        workspace = factories.WorkspaceFactory.create(name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "test"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_containing_query(self):
        """Queryset returns the correct objects when the name contains the query."""
        workspace = factories.WorkspaceFactory.create(name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "work"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        workspace = factories.WorkspaceFactory.create(name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "TEST-WORKSPACE"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)


class WorkspaceAutocompleteByTypeTest(TestCase):
    """Tests for the WorkspaceAutocompleteByType view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with the correct permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.default_workspace_type = DefaultWorkspaceAdapter().get_type()
        workspace_adapter_registry.register(TestWorkspaceAdapter)

    def tearDown(self):
        workspace_adapter_registry.unregister(TestWorkspaceAdapter)

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:autocomplete_by_type", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceAutocompleteByType.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.default_workspace_type))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.default_workspace_type),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.default_workspace_type))
        self.assertEqual(response.status_code, 200)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(self.default_workspace_type))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.default_workspace_type))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, workspace_type=self.default_workspace_type)

    def test_404_with_unregistered_workspace_type(self):
        """Raises 404 with get request if workspace type is not registered with adapter."""
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, workspace_type="foo")

    def test_returns_all_objects(self):
        """Queryset returns all objects when there is no query."""
        workspaces = factories.DefaultWorkspaceDataFactory.create_batch(10)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.default_workspace_type))
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 10)
        self.assertEqual(sorted(returned_ids), sorted([workspace.pk for workspace in workspaces]))

    def test_returns_correct_object_match(self):
        """Queryset returns the correct objects when query matches the name."""
        workspace = factories.DefaultWorkspaceDataFactory.create(workspace__name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.default_workspace_type), {"q": "test-workspace"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        workspace = factories.DefaultWorkspaceDataFactory.create(workspace__name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.default_workspace_type), {"q": "test"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_containing_query(self):
        """Queryset returns the correct objects when the name contains the query."""
        workspace = factories.DefaultWorkspaceDataFactory.create(workspace__name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.default_workspace_type), {"q": "work"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        workspace = factories.DefaultWorkspaceDataFactory.create(workspace__name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.default_workspace_type), {"q": "TEST-WORKSPACE"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_only_specified_workspace_type(self):
        """Queryset returns only objects with the specified workspace type."""
        workspace = factories.DefaultWorkspaceDataFactory.create()
        other_workspace = TestWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(workspace.workspace.workspace_type))
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)
        response = self.client.get(self.get_url(other_workspace.workspace.workspace_type))
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], other_workspace.pk)

    def test_custom_autocomplete_method(self):
        # Workspace that will match the custom autocomplete filtering.
        workspace_1 = TestWorkspaceDataFactory.create(workspace__name="TEST")
        # Workspace that should not match the custom autocomplete filtering.
        TestWorkspaceDataFactory.create(workspace__name="TEST-WORKSPACE")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(workspace_1.workspace.workspace_type), {"q": "TEST"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace_1.pk)

    def test_custom_autocomplete_with_forwarded_value(self):
        # Workspace that will match the custom autocomplete filtering.
        workspace = TestWorkspaceDataFactory.create()
        # Workspace that should not match the custom autocomplete filtering.
        TestWorkspaceDataFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(workspace.workspace.workspace_type),
            {"forward": json.dumps({"billing_project": workspace.workspace.billing_project.pk})},
        )
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)


class GroupGroupMembershipDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:member_groups:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("parent", "child"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("parent", "child"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.GroupGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.parent_group.name, obj.child_group.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("parent", "child"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, parent_group_slug="parent", child_group_slug="child")

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        factories.GroupGroupMembershipFactory.create()
        request = self.factory.get(self.get_url("parent", "child"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, parent_group_slug="parent", child_group_slug="child")

    def test_edit_permission(self):
        """Links to delete url appears if the user has edit permission."""
        edit_user = User.objects.create_user(username="edit", password="test")
        edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )
        self.client.force_login(edit_user)
        obj = factories.GroupGroupMembershipFactory.create()
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertTrue(response.context_data["show_edit_links"])
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:managed_groups:member_groups:delete",
                kwargs={
                    "parent_group_slug": obj.parent_group.name,
                    "child_group_slug": obj.child_group.name,
                },
            ),
        )

    def test_view_permission(self):
        """Links to delete url appears if the user has edit permission."""
        view_user = User.objects.create_user(username="view", password="test")
        view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
        )
        self.client.force_login(view_user)
        obj = factories.GroupGroupMembershipFactory.create()
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertFalse(response.context_data["show_edit_links"])
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:managed_groups:member_groups:delete",
                kwargs={
                    "parent_group_slug": obj.parent_group.name,
                    "child_group_slug": obj.child_group.name,
                },
            ),
        )

    def test_detail_page_links(self):
        """Links to other urls appear correctly."""
        self.client.force_login(self.user)
        obj = factories.GroupGroupMembershipFactory.create()
        response = self.client.get(obj.get_absolute_url())
        html = """<a href="{url}">{text}</a>""".format(
            url=obj.parent_group.get_absolute_url(), text=str(obj.parent_group)
        )
        self.assertContains(response, html)
        html = """<a href="{url}">{text}</a>""".format(
            url=obj.child_group.get_absolute_url(), text=str(obj.child_group)
        )
        self.assertContains(response, html)


class GroupGroupMembershipCreateTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:group_group_membership:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipCreate.as_view()

    def get_api_url(self, group_name, role, email):
        url = self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/" + role + "/" + email
        return url

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

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.GroupGroupMembershipForm)

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        parent_group = factories.ManagedGroupFactory.create(name="group-1")
        child_group = factories.ManagedGroupFactory.create(name="group-2")
        api_url = self.get_api_url(parent_group.name, "member", child_group.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupGroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupGroupMembership)
        self.assertEqual(new_object.role, models.GroupGroupMembership.MEMBER)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_success_message(self):
        """Response includes a success message if successful."""
        parent_group = factories.ManagedGroupFactory.create(name="group-1")
        child_group = factories.ManagedGroupFactory.create(name="group-2")
        api_url = self.get_api_url(parent_group.name, "member", child_group.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupGroupMembershipCreate.success_message, str(messages[0]))

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        parent_group = factories.ManagedGroupFactory.create(name="group-1")
        child_group = factories.ManagedGroupFactory.create(name="group-2")
        api_url = self.get_api_url(parent_group.name, "admin", child_group.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupGroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupGroupMembership)
        self.assertEqual(new_object.role, models.GroupGroupMembership.ADMIN)

    def test_redirects_to_list(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        parent_group = factories.ManagedGroupFactory.create(name="group-1")
        child_group = factories.ManagedGroupFactory.create(name="group-2")
        api_url = self.get_api_url(parent_group.name, "member", child_group.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertRedirects(response, reverse("anvil_consortium_manager:group_group_membership:list"))

    def test_cannot_create_duplicate_object_with_same_role(self):
        """Cannot create a second GroupGroupMembership object for the same parent and child with the same role."""
        obj = factories.GroupGroupMembershipFactory.create(role=models.GroupGroupMembership.MEMBER)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": obj.parent_group.pk,
                "child_group": obj.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.GroupGroupMembership.objects.all(),
            models.GroupGroupMembership.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_with_different_role(self):
        """Cannot create a second GroupGroupMembership object for the same parent and child with a different role."""
        obj = factories.GroupGroupMembershipFactory.create(role=models.GroupGroupMembership.MEMBER)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": obj.parent_group.pk,
                "child_group": obj.child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.GroupGroupMembership.objects.all(),
            models.GroupGroupMembership.objects.filter(pk=obj.pk),
        )
        self.assertEqual(
            models.GroupGroupMembership.objects.first().role,
            models.GroupGroupMembership.MEMBER,
        )

    def test_can_add_two_groups_to_one_parent(self):
        group_1 = factories.ManagedGroupFactory.create(name="test-group-1")
        group_2 = factories.ManagedGroupFactory.create(name="test-group-2")
        parent = factories.ManagedGroupFactory.create(name="parent-group")
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=group_1)
        api_url = self.get_api_url(parent.name, "member", group_2.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent.pk,
                "child_group": group_2.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)

    def test_can_add_a_child_group_to_two_parents(self):
        group_1 = factories.ManagedGroupFactory.create(name="test-group-1")
        group_2 = factories.ManagedGroupFactory.create(name="test-group-2")
        child = factories.ManagedGroupFactory.create(name="child_1-group")
        factories.GroupGroupMembershipFactory.create(parent_group=group_1, child_group=child)
        api_url = self.get_api_url(group_2.name, "member", child.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": group_2.pk,
                "child_group": child.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)

    def test_invalid_input_child(self):
        """Posting invalid data to child_group field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": group.pk,
                "child_group": group.pk + 1,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("valid choice", form.errors["child_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_invalid_input_parent(self):
        """Posting invalid data to parent group field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": group.pk + 1,
                "child_group": group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("valid choice", form.errors["parent_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_invalid_input_role(self):
        """Posting invalid data to group field does not create an object."""
        parent_group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": "foo",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("valid choice", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("required", form.errors["parent_group"][0])
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("required", form.errors["child_group"][0])
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_parent_group(self):
        """Posting blank data to the parent_group field does not create an object."""
        child_group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {"child_group": child_group.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("required", form.errors["parent_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_child_group(self):
        """Posting blank data to the child_group field does not create an object."""
        parent_group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {"parent_group": parent_group.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("required", form.errors["child_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_role(self):
        """Posting blank data to the role field does not create an object."""
        parent_group = factories.ManagedGroupFactory.create(name="parent")
        child_group = factories.ManagedGroupFactory.create(name="child")
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {"parent_group": parent_group.pk, "child_group": child_group.pk},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_a_group_to_itself_member(self):
        """Cannot create a GroupGroupMembership object where the parent and child are the same group."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": group.pk,
                "child_group": group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("add a group to itself", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_a_group_to_itself_admin(self):
        """Cannot create a GroupGroupMembership object where the parent and child are the same group."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": group.pk,
                "child_group": group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("add a group to itself", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_circular_relationship(self):
        """Cannot create a GroupGroupMembership object that makes a cirular relationship."""
        grandparent = factories.ManagedGroupFactory.create()
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": child.pk,
                "child_group": grandparent.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("circular", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)

    def test_cannot_add_child_group_if_parent_not_managed_by_app(self):
        """Cannot add a child group to a parent group if the parent group is not managed by the app."""
        parent_group = factories.ManagedGroupFactory.create(name="group-1", is_managed_by_app=False)
        child_group = factories.ManagedGroupFactory.create(name="group-2")
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("valid choice", form.errors["parent_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        parent_group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        api_url = self.get_api_url(parent_group.name, "member", child_group.email)
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=500,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_no_permission_for_parent_group(self):
        parent_group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        api_url = self.get_api_url(parent_group.name, "member", child_group.email)
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=403,
            json={"message": "error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_child_group_exists_parent_group_does_not_exist(self):
        parent_group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        api_url = self.get_api_url(parent_group.name, "member", child_group.email)
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=404,
            json={"message": "error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_child_group_does_not_exist_parent_group_does_not_exist(self):
        parent_group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        api_url = self.get_api_url(parent_group.name, "member", child_group.email)
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=404,
            json={"message": "error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_child_group_does_not_exist_parent_group_exists(self):
        parent_group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        api_url = self.get_api_url(parent_group.name, "member", child_group.email)
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=400,
            json={"message": "error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)


class GroupGroupMembershipCreateByParentTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.parent_group = factories.ManagedGroupFactory.create()
        self.child_group = factories.ManagedGroupFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:member_groups:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipCreateByParent.as_view()

    def get_api_url(self, role):
        url = (
            self.api_client.sam_entry_point
            + "/api/groups/v1/"
            + self.parent_group.name
            + "/"
            + role
            + "/"
            + self.child_group.email
        )
        return url

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.parent_group.name))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.parent_group.name),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.parent_group.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(self.parent_group.name))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, parent_group_slug=self.parent_group.name)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.parent_group.name))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, parent_group_slug=self.parent_group.name)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.parent_group.name))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.GroupGroupMembershipForm)

    def test_form_hidden_input(self):
        """The proper inputs are hidden in the form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.parent_group.name))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"].fields["parent_group"].widget, HiddenInput)

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupGroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupGroupMembership)
        self.assertEqual(new_object.role, models.GroupGroupMembership.MEMBER)
        self.assertEqual(new_object.parent_group, self.parent_group)
        self.assertEqual(new_object.child_group, self.child_group)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_success_message(self):
        """Response includes a success message if successful."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupGroupMembershipCreateByParent.success_message, str(messages[0]))

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("admin")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupGroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupGroupMembership)
        self.assertEqual(new_object.role, models.GroupGroupMembership.ADMIN)

    def test_redirects_to_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertRedirects(
            response,
            models.GroupGroupMembership.objects.latest("pk").get_absolute_url(),
        )

    def test_cannot_create_duplicate_object(self):
        """Cannot create a second GroupGroupMembership object for the same parent and child with the same role."""
        obj = factories.GroupGroupMembershipFactory.create(role=models.GroupGroupMembership.MEMBER)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.parent_group.name),
            {
                "parent_group": obj.parent_group.pk,
                "child_group": obj.child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.GroupGroupMembership.objects.all(),
            models.GroupGroupMembership.objects.filter(pk=obj.pk),
        )

    def test_invalid_input_child(self):
        """Posting invalid data to child_group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": 100,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("valid choice", form.errors["child_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_get_parent_group_not_found(self):
        """Raises 404 if parent group in URL does not exist when posting data."""
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, parent_group_slug="foo")
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_parent_group_not_found(self):
        """Raises 404 if parent group in URL does not exist when posting data."""
        request = self.factory.post(
            self.get_url("foo"),
            {
                "parent_group": self.parent_group.pk + 1,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, parent_group_slug="foo")
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_invalid_input_role(self):
        """Posting invalid data to group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": "foo",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("valid choice", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(self.parent_group.name), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("required", form.errors["parent_group"][0])
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("required", form.errors["child_group"][0])
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_parent_group(self):
        """Posting blank data to the parent_group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {"child_group": self.child_group.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("required", form.errors["parent_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_child_group(self):
        """Posting blank data to the child_group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {"parent_group": self.parent_group.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("required", form.errors["child_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_role(self):
        """Posting blank data to the role field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {"parent_group": self.parent_group.pk, "child_group": self.child_group.pk},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cannot_add_group_to_itself(self):
        """Cannot add a group to itself.."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.parent_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("itself", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_circular_relationship(self):
        """Cannot create a GroupGroupMembership object that makes a cirular relationship."""
        grandparent = factories.ManagedGroupFactory.create()
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(child.name),
            {
                "parent_group": child.pk,
                "child_group": grandparent.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("circular", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)

    def test_get_cannot_add_child_group_if_parent_not_managed_by_app(self):
        """Cannot add a child group to a parent group if the parent group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(group.name),
            follow=True,
        )
        self.assertRedirects(response, group.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipCreateByParentChild.message_not_managed_by_app,
            str(messages[0]),
        )
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_cannot_add_child_group_if_parent_not_managed_by_app(self):
        """Cannot add a child group to a parent group if the parent group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(group.name),
            {
                "parent_group": group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
            follow=True,
        )
        self.assertRedirects(response, group.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipCreateByParentChild.message_not_managed_by_app,
            str(messages[0]),
        )
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_500(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=500,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_400(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=400,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_403(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=403,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_404(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=404,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)


class GroupGroupMembershipCreateByChildTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.parent_group = factories.ManagedGroupFactory.create()
        self.child_group = factories.ManagedGroupFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:add_to_group", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipCreateByChild.as_view()

    def get_api_url(self, role):
        url = (
            self.api_client.sam_entry_point
            + "/api/groups/v1/"
            + self.parent_group.name
            + "/"
            + role
            + "/"
            + self.child_group.email
        )
        return url

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.child_group.name))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.child_group.name),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.child_group.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(self.child_group.name))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, group_slug=self.child_group.name)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.child_group.name))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, group_slug=self.child_group.name)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.child_group.name))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.GroupGroupMembershipForm)

    def test_form_hidden_input(self):
        """The proper inputs are hidden in the form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.child_group.name))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"].fields["child_group"].widget, HiddenInput)

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupGroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupGroupMembership)
        self.assertEqual(new_object.role, models.GroupGroupMembership.MEMBER)
        self.assertEqual(new_object.parent_group, self.parent_group)
        self.assertEqual(new_object.child_group, self.child_group)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_success_message(self):
        """Response includes a success message if successful."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupGroupMembershipCreateByParent.success_message, str(messages[0]))

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("admin")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupGroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupGroupMembership)
        self.assertEqual(new_object.role, models.GroupGroupMembership.ADMIN)

    def test_redirects_to_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertRedirects(
            response,
            models.GroupGroupMembership.objects.latest("pk").get_absolute_url(),
        )

    def test_cannot_create_duplicate_object(self):
        """Cannot create a second GroupGroupMembership object for the same parent and child with the same role."""
        obj = factories.GroupGroupMembershipFactory.create(role=models.GroupGroupMembership.MEMBER)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.child_group.name),
            {
                "parent_group": obj.parent_group.pk,
                "child_group": obj.child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.GroupGroupMembership.objects.all(),
            models.GroupGroupMembership.objects.filter(pk=obj.pk),
        )

    def test_invalid_input_parent(self):
        """Posting invalid data to parent_group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {
                "parent_group": 100,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("valid choice", form.errors["parent_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_get_child_group_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, group_slug="foo")
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_child_group_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.post(
            self.get_url("foo"),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk + 1,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, group_slug="foo")
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_invalid_input_role(self):
        """Posting invalid data to group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": "foo",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("valid choice", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(self.child_group.name), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("required", form.errors["parent_group"][0])
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("required", form.errors["child_group"][0])
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_parent_group(self):
        """Posting blank data to the parent_group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {"child_group": self.child_group.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("required", form.errors["parent_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_child_group(self):
        """Posting blank data to the child_group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {"parent_group": self.parent_group.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("required", form.errors["child_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_role(self):
        """Posting blank data to the role field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {"parent_group": self.parent_group.pk, "child_group": self.child_group.pk},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cannot_add_group_to_itself(self):
        """Cannot add a group to itself.."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {
                "parent_group": self.child_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("itself", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_circular_relationship(self):
        """Cannot create a GroupGroupMembership object that makes a cirular relationship."""
        grandparent = factories.ManagedGroupFactory.create()
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(grandparent.name),
            {
                "parent_group": child.pk,
                "child_group": grandparent.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("circular", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)

    def test_api_error_500(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=500,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_400(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=400,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_403(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=403,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_404(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=404,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)


class GroupGroupMembershipCreateByParentChildTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.parent_group = factories.ManagedGroupFactory.create()
        self.child_group = factories.ManagedGroupFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:managed_groups:member_groups:new_by_child",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipCreateByParentChild.as_view()

    def get_api_url(self, role):
        url = (
            self.api_client.sam_entry_point
            + "/api/groups/v1/"
            + self.parent_group.name
            + "/"
            + role
            + "/"
            + self.child_group.email
        )
        return url

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.parent_group.name, self.child_group.name))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.parent_group.name, self.child_group.name),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.parent_group.name, self.child_group.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(self.parent_group.name, self.child_group.name))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                parent_group_slug=self.parent_group.name,
                child_group_slug=self.child_group.name,
            )

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.parent_group.name, self.child_group.name))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                parent_group_slug=self.parent_group.name,
                child_group_slug=self.child_group.name,
            )

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.parent_group.name, self.child_group.name))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.GroupGroupMembershipForm)

    def test_form_hidden_input(self):
        """The proper inputs are hidden in the form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.parent_group.name, self.child_group.name))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"].fields["child_group"].widget, HiddenInput)
        self.assertIsInstance(response.context_data["form"].fields["parent_group"].widget, HiddenInput)

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupGroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupGroupMembership)
        self.assertEqual(new_object.role, models.GroupGroupMembership.MEMBER)
        self.assertEqual(new_object.parent_group, self.parent_group)
        self.assertEqual(new_object.child_group, self.child_group)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_success_message(self):
        """Response includes a success message if successful."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipCreateByParentChild.success_message,
            str(messages[0]),
        )

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("admin")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupGroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupGroupMembership)
        self.assertEqual(new_object.role, models.GroupGroupMembership.ADMIN)

    def test_redirects_to_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertRedirects(
            response,
            models.GroupGroupMembership.objects.latest("pk").get_absolute_url(),
        )

    def test_get_duplicate_object_redirect_cannot_create_duplicate_object(self):
        """Cannot create a second GroupGroupMembership object for the same parent and child with the same role."""
        obj = factories.GroupGroupMembershipFactory.create(role=models.GroupGroupMembership.MEMBER)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.parent_group.name, obj.child_group.name), follow=True)
        self.assertRedirects(response, obj.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipCreateByParentChild.message_already_exists,
            str(messages[0]),
        )

    def test_post_duplicate_object_redirect_cannot_create_duplicate_object(self):
        """Cannot create a second GroupGroupMembership object for the same parent and child with the same role."""
        obj = factories.GroupGroupMembershipFactory.create(role=models.GroupGroupMembership.MEMBER)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.parent_group.name, obj.child_group.name),
            {
                "parent_group": obj.parent_group.pk,
                "child_group": obj.child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
            follow=True,
        )
        self.assertRedirects(response, obj.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipCreateByParentChild.message_already_exists,
            str(messages[0]),
        )

    def test_get_parent_group_not_found(self):
        """Raises 404 if parent group in URL does not exist when posting data."""
        request = self.factory.get(self.get_url("foo", self.child_group.name))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, parent_group_slug="foo", child_group_slug=self.child_group.name)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_parent_group_not_found(self):
        """Raises 404 if parent group in URL does not exist when posting data."""
        request = self.factory.post(
            self.get_url("foo", self.child_group.name),
            {
                "parent_group": self.parent_group.pk + 1,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, parent_group_slug="foo", child_group_slug=self.child_group.name)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_get_child_group_not_found(self):
        """Raises 404 if child group in URL does not exist when posting data."""
        request = self.factory.get(self.get_url(self.parent_group.name, "foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                parent_group_slug=self.parent_group.name,
                child_group_slug="foo",
            )
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_child_group_not_found(self):
        """Raises 404 if parent group in URL does not exist when posting data."""
        request = self.factory.post(
            self.get_url(self.parent_group.name, "foo"),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk + 1,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                parent_group_slug=self.parent_group.name,
                child_group_slug="foo",
            )
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_invalid_input_role(self):
        """Posting invalid data to group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": "foo",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("valid choice", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(self.parent_group.name, self.child_group.name), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("required", form.errors["parent_group"][0])
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("required", form.errors["child_group"][0])
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_parent_group(self):
        """Posting blank data to the parent_group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {"child_group": self.child_group.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("required", form.errors["parent_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_child_group(self):
        """Posting blank data to the child_group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {"parent_group": self.parent_group.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("required", form.errors["child_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_role(self):
        """Posting blank data to the role field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {"parent_group": self.parent_group.pk, "child_group": self.child_group.pk},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_a_group_to_itself_member(self):
        """Cannot create a GroupGroupMembership object where the parent and child are the same group."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(group.name, group.name),
            {
                "parent_group": group.pk,
                "child_group": group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
            follow=True,
        )
        self.assertRedirects(response, group.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipCreateByParentChild.message_cannot_add_group_to_itself,
            str(messages[0]),
        )
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_a_group_to_itself_admin(self):
        """Cannot create a GroupGroupMembership object where the parent and child are the same group."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(group.name, group.name),
            {
                "parent_group": group.pk,
                "child_group": group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
            follow=True,
        )
        self.assertRedirects(response, group.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipCreateByParentChild.message_cannot_add_group_to_itself,
            str(messages[0]),
        )
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_circular_relationship(self):
        """Cannot create a GroupGroupMembership object that makes a cirular relationship."""
        grandparent = factories.ManagedGroupFactory.create()
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=grandparent, child_group=parent)
        factories.GroupGroupMembershipFactory.create(parent_group=parent, child_group=child)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(child.name, grandparent.name),
            {
                "parent_group": child.pk,
                "child_group": grandparent.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
            follow=True,
        )
        self.assertRedirects(response, child.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipCreateByParentChild.message_circular_relationship,
            str(messages[0]),
        )
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)

    def test_get_cannot_add_child_group_if_parent_not_managed_by_app(self):
        """Cannot add a child group to a parent group if the parent group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(group.name, self.child_group.name),
            follow=True,
        )
        self.assertRedirects(response, group.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipCreateByParentChild.message_not_managed_by_app,
            str(messages[0]),
        )
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_cannot_add_child_group_if_parent_not_managed_by_app(self):
        """Cannot add a child group to a parent group if the parent group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(group.name, self.child_group.name),
            {
                "parent_group": group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
            follow=True,
        )
        self.assertRedirects(response, group.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipCreateByParentChild.message_not_managed_by_app,
            str(messages[0]),
        )
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_500(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=500,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_400(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=400,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_403(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=403,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_404(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=404,
            json={"message": "group group membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.parent_group.name, self.child_group.name),
            {
                "parent_group": self.parent_group.pk,
                "child_group": self.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)


class GroupGroupMembershipListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:group_group_membership:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipList.as_view()

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

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.GroupGroupMembershipStaffTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.GroupGroupMembershipFactory()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.GroupGroupMembershipFactory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class GroupGroupMembershipDeleteTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:member_groups:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipDelete.as_view()

    def get_api_url(self, group_name, role, email):
        url = self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/" + role + "/" + email
        return url

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("parent", "child"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("parent", "child"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.GroupGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.parent_group.name, obj.child_group.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("parent", "child"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, parent_group_slug="parent", child_group_slug="child")

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("parent", "child"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, parent_group_slug="parent", child_group_slug="child")

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url("parent", "child"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, parent_group_slug="parent", child_group_slug="child")

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        obj = factories.GroupGroupMembershipFactory.create(role=models.GroupGroupMembership.MEMBER)
        api_url = self.get_api_url(obj.parent_group.name, obj.role.lower(), obj.child_group.email)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)
        # History is added.
        self.assertEqual(obj.history.count(), 2)
        self.assertEqual(obj.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        obj = factories.GroupGroupMembershipFactory.create(role=models.GroupGroupMembership.MEMBER)
        api_url = self.get_api_url(obj.parent_group.name, obj.role.lower(), obj.child_group.email)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.parent_group.name, obj.child_group.name),
            {"submit": ""},
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupGroupMembershipDelete.success_message, str(messages[0]))

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        obj = factories.GroupGroupMembershipFactory.create()
        other_object = factories.GroupGroupMembershipFactory.create()
        api_url = self.get_api_url(obj.parent_group.name, obj.role.lower(), obj.child_group.email)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        self.assertQuerySetEqual(
            models.GroupGroupMembership.objects.all(),
            models.GroupGroupMembership.objects.filter(pk=other_object.pk),
        )

    def test_success_url(self):
        """Redirects to the expected page."""
        obj = factories.GroupGroupMembershipFactory.create()
        parent_group = obj.parent_group
        api_url = self.get_api_url(obj.parent_group.name, obj.role.lower(), obj.child_group.email)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        # Need to use the client instead of RequestFactory to check redirection url.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, parent_group.get_absolute_url())

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        obj = factories.GroupGroupMembershipFactory.create()
        api_url = self.get_api_url(obj.parent_group.name, obj.role.lower(), obj.child_group.email)
        self.anvil_response_mock.add(
            responses.DELETE,
            api_url,
            status=500,
            json={"message": "group group membership delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership delete test error",
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)

    def test_get_redirect_parent_group_not_managed_by_app(self):
        """Redirect get when trying to delete GroupGroupMembership when a parent group is not managed by the app."""
        parent_group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        child_group = factories.ManagedGroupFactory.create()
        obj = factories.GroupGroupMembershipFactory.create(parent_group=parent_group, child_group=child_group)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.parent_group.name, obj.child_group.name), follow=True)
        self.assertRedirects(response, obj.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipDelete.message_parent_group_not_managed_by_app,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)

    def test_post_redirect_parent_group_not_managed_by_app(self):
        """Redirect post when trying to delete GroupGroupMembership when a parent group is not managed by the app."""
        parent_group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        child_group = factories.ManagedGroupFactory.create()
        obj = factories.GroupGroupMembershipFactory.create(parent_group=parent_group, child_group=child_group)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.parent_group.name, obj.child_group.name), follow=True)
        self.assertRedirects(response, obj.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipDelete.message_parent_group_not_managed_by_app,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)

    def test_api_error_400(self):
        obj = factories.GroupGroupMembershipFactory.create()
        api_url = self.get_api_url(obj.parent_group.name, obj.role.lower(), obj.child_group.email)
        self.anvil_response_mock.add(
            responses.DELETE,
            api_url,
            status=400,
            json={"message": "group group membership delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership delete test error",
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)

    def test_api_error_403(self):
        obj = factories.GroupGroupMembershipFactory.create()
        api_url = self.get_api_url(obj.parent_group.name, obj.role.lower(), obj.child_group.email)
        self.anvil_response_mock.add(
            responses.DELETE,
            api_url,
            status=403,
            json={"message": "group group membership delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership delete test error",
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)

    def test_api_error_404(self):
        obj = factories.GroupGroupMembershipFactory.create()
        api_url = self.get_api_url(obj.parent_group.name, obj.role.lower(), obj.child_group.email)
        self.anvil_response_mock.add(
            responses.DELETE,
            api_url,
            status=404,
            json={"message": "group group membership delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership delete test error",
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)

    def test_api_error_500(self):
        obj = factories.GroupGroupMembershipFactory.create()
        api_url = self.get_api_url(obj.parent_group.name, obj.role.lower(), obj.child_group.email)
        self.anvil_response_mock.add(
            responses.DELETE,
            api_url,
            status=500,
            json={"message": "group group membership delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership delete test error",
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)


class GroupAccountMembershipDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:member_accounts:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        uuid = uuid4()
        response = self.client.get(self.get_url("foo1", uuid))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo1", uuid),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.GroupAccountMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertEqual(response.status_code, 200)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", uuid4()))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        uuid = uuid4()
        request = self.factory.get(self.get_url("foo1", uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, group_slug="foo1", account_uuid=uuid)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        uuid = uuid4()
        request = self.factory.get(self.get_url("foo1", uuid))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, group_slug="foo1", account_uuid=uuid)

    def test_edit_permission(self):
        """Links to delete url appears if the user has edit permission."""
        edit_user = User.objects.create_user(username="edit", password="test")
        edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )
        self.client.force_login(edit_user)
        obj = factories.GroupAccountMembershipFactory.create()
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertTrue(response.context_data["show_edit_links"])
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:managed_groups:member_accounts:delete",
                kwargs={
                    "group_slug": obj.group.name,
                    "account_uuid": obj.account.uuid,
                },
            ),
        )

    def test_view_permission(self):
        """Links to delete url appears if the user has edit permission."""
        view_user = User.objects.create_user(username="view", password="test")
        view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
        )
        self.client.force_login(view_user)
        obj = factories.GroupAccountMembershipFactory.create()
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertFalse(response.context_data["show_edit_links"])
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:managed_groups:member_accounts:delete",
                kwargs={
                    "group_slug": obj.group.name,
                    "account_uuid": obj.account.uuid,
                },
            ),
        )

    def test_detail_page_links(self):
        """Links to other object detail pages appear correctly."""
        self.client.force_login(self.user)
        obj = factories.GroupAccountMembershipFactory.create()
        response = self.client.get(obj.get_absolute_url())
        html = """<a href="{url}">{text}</a>""".format(url=obj.group.get_absolute_url(), text=str(obj.group))
        self.assertContains(response, html)
        html = """<a href="{url}">{text}</a>""".format(url=obj.account.get_absolute_url(), text=str(obj.account))
        self.assertContains(response, html)


class GroupAccountMembershipCreateTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:group_account_membership:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipCreate.as_view()

    def get_api_url(self, group_name, role, email):
        url = self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/" + role + "/" + email
        return url

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

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.GroupAccountMembershipForm)

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        account = factories.AccountFactory.create(email="email@example.com")
        api_url = self.get_api_url(group.name, "member", account.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupAccountMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupAccountMembership)
        self.assertEqual(new_object.role, models.GroupAccountMembership.MEMBER)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_success_message(self):
        """Response includes a success message if successful."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        account = factories.AccountFactory.create(email="email@example.com")
        api_url = self.get_api_url(group.name, "member", account.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupAccountMembershipCreate.success_message, str(messages[0]))

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        account = factories.AccountFactory.create(email="email@example.com")
        api_url = self.get_api_url(group.name, "admin", account.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupAccountMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupAccountMembership)
        self.assertEqual(new_object.role, models.GroupAccountMembership.ADMIN)

    def test_redirects_to_list(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(group.name, "member", account.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertRedirects(response, reverse("anvil_consortium_manager:group_account_membership:list"))

    def test_cannot_create_duplicate_object_with_same_role(self):
        """Cannot create a second GroupAccountMembership object for the same account and group with the same role."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        obj = factories.GroupAccountMembershipFactory(
            group=group, account=account, role=models.GroupAccountMembership.MEMBER
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.GroupAccountMembership.objects.all(),
            models.GroupAccountMembership.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_with_different_role(self):
        """Cannot create a second GroupAccountMembership object for the same account and group with a different role."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        obj = factories.GroupAccountMembershipFactory(
            group=group, account=account, role=models.GroupAccountMembership.MEMBER
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.GroupAccountMembership.objects.all(),
            models.GroupAccountMembership.objects.filter(pk=obj.pk),
        )

    def test_can_add_two_groups_for_one_account(self):
        group_1 = factories.ManagedGroupFactory.create(name="test-group-1")
        group_2 = factories.ManagedGroupFactory.create(name="test-group-2")
        account = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group_1, account=account)
        api_url = self.get_api_url(group_2.name, "member", account.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group_2.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)

    def test_can_add_two_accounts_to_one_group(self):
        group = factories.ManagedGroupFactory.create()
        account_1 = factories.AccountFactory.create(email="test_1@example.com")
        account_2 = factories.AccountFactory.create(email="test_2@example.com")
        factories.GroupAccountMembershipFactory.create(group=group, account=account_1)
        api_url = self.get_api_url(group.name, "member", account_2.email)
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account_2.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)

    def test_invalid_input_account(self):
        """Posting invalid data to account field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": 1,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("account", form.errors.keys())
        self.assertIn("valid choice", form.errors["account"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_invalid_input_group(self):
        """Posting invalid data to group field does not create an object."""
        account = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": 1,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_invalid_input_role(self):
        """Posting invalid data to group field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {"group": group.pk, "account": account.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("valid choice", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("account", form.errors.keys())
        self.assertIn("required", form.errors["account"][0])
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_group(self):
        """Posting blank data to the group field does not create an object."""
        account = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {"account": account.pk, "role": models.GroupAccountMembership.MEMBER},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_account(self):
        """Posting blank data to the account field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {"group": group.pk, "role": models.GroupAccountMembership.MEMBER},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("account", form.errors.keys())
        self.assertIn("required", form.errors["account"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_role(self):
        """Posting blank data to the role field does not create an object."""
        account = factories.AccountFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"group": group.pk, "account": account.pk})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_cannot_add_account_if_group_not_managed_by_app(self):
        """Cannot add an account to a group if the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        account = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(group.name, "member", account.email)
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=500,
            json={"message": "other error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: other error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_cannot_add_inactive_account_to_group(self):
        """Cannot add an inactive account to a group."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create(status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("account", form.errors.keys())
        self.assertIn("valid choice", form.errors["account"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_queryset_shows_active_users_only(self):
        """Form queryset only shows active accounts."""
        active_account = factories.AccountFactory.create()
        inactive_account = factories.AccountFactory.create(status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("form" in response.context_data)
        form = response.context_data["form"]
        self.assertIn(active_account, form.fields["account"].queryset)
        self.assertNotIn(inactive_account, form.fields["account"].queryset)

    def test_api_no_permission_for_group(self):
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(group.name, "member", account.email)
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=403,
            json={"message": "other error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: other error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_user_exists_group_does_not_exist(self):
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(group.name, "member", account.email)
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: other error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_user_does_not_exist_group_does_not_exist(self):
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(group.name, "member", account.email)
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: other error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_user_does_not_exist_group_exists(self):
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(group.name, "member", account.email)
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=400,
            json={"message": "other error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: other error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)


class GroupAccountMembershipCreateByGroupTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.account = factories.AccountFactory.create()
        self.group = factories.ManagedGroupFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:member_accounts:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipCreateByGroup.as_view()

    def get_api_url(self, role):
        url = (
            self.api_client.sam_entry_point
            + "/api/groups/v1/"
            + self.group.name
            + "/"
            + role
            + "/"
            + self.account.email
        )
        return url

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.group.name))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.group.name),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(self.group.name))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, group_slug=self.group.name)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.group.name))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, group_slug=self.group.name)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.GroupAccountMembershipForm)

    def test_context_group(self):
        """Context contains the group."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertTrue("group" in response.context_data)
        self.assertEqual(response.context_data["group"], self.group)

    def test_form_hidden_input(self):
        """The proper inputs are hidden in the form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"].fields["group"].widget, HiddenInput)

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupAccountMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupAccountMembership)
        self.assertEqual(new_object.role, models.GroupAccountMembership.MEMBER)
        self.assertEqual(new_object.group, self.group)
        self.assertEqual(new_object.account, self.account)

    def test_success_message(self):
        """Response includes a success message if successful."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupAccountMembershipCreate.success_message, str(messages[0]))

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("admin")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupAccountMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupAccountMembership)
        self.assertEqual(new_object.role, models.GroupAccountMembership.ADMIN)
        self.assertEqual(new_object.group, self.group)
        self.assertEqual(new_object.account, self.account)

    def test_success_redirect(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        obj = models.GroupAccountMembership.objects.latest("pk")
        self.assertRedirects(response, obj.get_absolute_url())

    def test_cannot_create_duplicate_object_with_different_role(self):
        """Cannot create a second GroupAccountMembership object for the same account and group with a different role."""
        obj = factories.GroupAccountMembershipFactory(
            group=self.group,
            account=self.account,
            role=models.GroupAccountMembership.MEMBER,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.GroupAccountMembership.objects.all(),
            models.GroupAccountMembership.objects.filter(pk=obj.pk),
        )
        obj.refresh_from_db()
        self.assertEqual(obj.role, models.GroupAccountMembership.MEMBER)

    def test_get_group_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, group_slug="foo")
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_group_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.post(
            self.get_url(
                "foo",
            ),
            {
                "group": self.group.pk + 1,
                "account": self.account,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                group_slug="foo",
            )
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_invalid_account(self):
        """Form is not valid if the account does not exist."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "account": self.account.pk + 1,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("account", form.errors)
        self.assertEqual(len(form.errors["account"]), 1)
        self.assertIn("valid choice", form.errors["account"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_invalid_input_role(self):
        """Posting invalid data to group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {"group": self.group.pk, "account": self.account.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("valid choice", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(self.group.name), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("account", form.errors.keys())
        self.assertIn("required", form.errors["account"][0])
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_group(self):
        """Posting blank data to the group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {"account": self.account.pk, "role": models.GroupAccountMembership.MEMBER},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_account(self):
        """Posting blank data to the account field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {"group": self.group.pk, "role": models.GroupAccountMembership.MEMBER},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("account", form.errors.keys())
        self.assertIn("required", form.errors["account"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_role(self):
        """Posting blank data to the role field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {"group": self.group.pk, "account": self.account.pk},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_get_redirect_group_not_managed_by_app(self):
        """Cannot add an account to a group if the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Shows a message.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            views.GroupAccountMembershipCreateByGroup.message_not_managed_by_app,
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_redirect_group_not_managed_by_app(self):
        """Cannot add an account to a group if the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(group.name),
            {
                "group": group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
            follow=True,
        )
        self.assertRedirects(response, group.get_absolute_url())
        # Shows a message.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            views.GroupAccountMembershipCreateByGroup.message_not_managed_by_app,
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_500(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=500,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_400(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=400,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_403(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=403,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_404(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=404,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_cannot_add_inactive_account_to_group(self):
        """Cannot add an inactive account to a group."""
        account = factories.AccountFactory.create(status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "account": account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("account", form.errors.keys())
        self.assertIn("valid choice", form.errors["account"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)


class GroupAccountMembershipCreateByAccountTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.account = factories.AccountFactory.create()
        self.group = factories.ManagedGroupFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:add_to_group", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipCreateByAccount.as_view()

    def get_api_url(self, role):
        url = (
            self.api_client.sam_entry_point
            + "/api/groups/v1/"
            + self.group.name
            + "/"
            + role
            + "/"
            + self.account.email
        )
        return url

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.account.uuid))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.account.uuid),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url(self.account.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=self.account.uuid)
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(self.account.uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=self.account.uuid)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(uuid4()))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.account.uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=self.account.uuid)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.account.uuid))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.GroupAccountMembershipForm)

    def test_context_account(self):
        """Context contains the account."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.account.uuid))
        self.assertTrue("account" in response.context_data)
        self.assertEqual(response.context_data["account"], self.account)

    def test_form_hidden_input(self):
        """The proper inputs are hidden in the form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.account.uuid))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"].fields["account"].widget, HiddenInput)

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupAccountMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupAccountMembership)
        self.assertEqual(new_object.role, models.GroupAccountMembership.MEMBER)
        self.assertEqual(new_object.group, self.group)
        self.assertEqual(new_object.account, self.account)

    def test_success_message(self):
        """Response includes a success message if successful."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupAccountMembershipCreate.success_message, str(messages[0]))

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("admin")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupAccountMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupAccountMembership)
        self.assertEqual(new_object.role, models.GroupAccountMembership.ADMIN)
        self.assertEqual(new_object.group, self.group)
        self.assertEqual(new_object.account, self.account)

    def test_success_redirect(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        obj = models.GroupAccountMembership.objects.latest("pk")
        self.assertRedirects(response, obj.get_absolute_url())

    def test_cannot_create_duplicate_object_with_different_role(self):
        """Cannot create a second GroupAccountMembership object for the same account and group with a different role."""
        obj = factories.GroupAccountMembershipFactory(
            group=self.group,
            account=self.account,
            role=models.GroupAccountMembership.MEMBER,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.GroupAccountMembership.objects.all(),
            models.GroupAccountMembership.objects.filter(pk=obj.pk),
        )
        obj.refresh_from_db()
        self.assertEqual(obj.role, models.GroupAccountMembership.MEMBER)

    def test_get_account_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, uuid=uuid)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_account_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        uuid = uuid4()
        request = self.factory.post(
            self.get_url(
                uuid,
            ),
            {
                "group": self.group.pk,
                "account": self.account.pk + 1,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                uuid=uuid,
            )
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_group_not_found(self):
        """Form is not valid if the group does not exist."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": self.group.pk + 1,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("group", form.errors)
        self.assertEqual(len(form.errors["group"]), 1)
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_group_not_managed_by_app(self):
        """Form is not valid if the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("group", form.errors)
        self.assertEqual(len(form.errors["group"]), 1)
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_invalid_input_role(self):
        """Posting invalid data to role field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {"group": self.group.pk, "account": self.account.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("valid choice", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(self.account.uuid), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("account", form.errors.keys())
        self.assertIn("required", form.errors["account"][0])
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_group(self):
        """Posting blank data to the group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {"account": self.account.pk, "role": models.GroupAccountMembership.MEMBER},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_account(self):
        """Posting blank data to the account field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {"group": self.group.pk, "role": models.GroupAccountMembership.MEMBER},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("account", form.errors.keys())
        self.assertIn("required", form.errors["account"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_role(self):
        """Posting blank data to the role field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {"group": self.group.pk, "account": self.account.pk},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_500(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=500,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_400(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=400,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_403(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=403,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_404(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=404,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_cannot_add_inactive_account_to_group(self):
        """Cannot add an inactive account to a group."""
        account = factories.AccountFactory.create(status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.account.uuid),
            {
                "group": self.group.pk,
                "account": account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("account", form.errors.keys())
        self.assertIn("valid choice", form.errors["account"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)


class GroupAccountMembershipCreateByGroupAccountTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.account = factories.AccountFactory.create()
        self.group = factories.ManagedGroupFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:managed_groups:member_accounts:new_by_account",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipCreateByGroupAccount.as_view()

    def get_api_url(self, role):
        url = (
            self.api_client.sam_entry_point
            + "/api/groups/v1/"
            + self.group.name
            + "/"
            + role
            + "/"
            + self.account.email
        )
        return url

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.group.name, self.account.uuid))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.group.name, self.account.uuid),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name, self.account.uuid))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(self.group.name, self.account.uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, group_slug=self.group.name, account_uuid=self.account.uuid)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", uuid4()))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.group.name, self.account.uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, group_slug=self.group.name, account_slug=self.account.uuid)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name, self.account.uuid))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.GroupAccountMembershipForm)

    def test_context_group(self):
        """Context contains the group."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name, self.account.uuid))
        self.assertTrue("group" in response.context_data)
        self.assertEqual(response.context_data["group"], self.group)

    def test_context_account(self):
        """Context contains the account."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name, self.account.uuid))
        self.assertTrue("account" in response.context_data)
        self.assertEqual(response.context_data["account"], self.account)

    def test_form_hidden_input(self):
        """The proper inputs are hidden in the form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name, self.account.uuid))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"].fields["account"].widget, HiddenInput)
        self.assertIsInstance(response.context_data["form"].fields["group"].widget, HiddenInput)

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupAccountMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupAccountMembership)
        self.assertEqual(new_object.role, models.GroupAccountMembership.MEMBER)
        self.assertEqual(new_object.group, self.group)
        self.assertEqual(new_object.account, self.account)

    def test_success_message(self):
        """Response includes a success message if successful."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupAccountMembershipCreate.success_message, str(messages[0]))

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        api_url = self.get_api_url("admin")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupAccountMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupAccountMembership)
        self.assertEqual(new_object.role, models.GroupAccountMembership.ADMIN)
        self.assertEqual(new_object.group, self.group)
        self.assertEqual(new_object.account, self.account)

    def test_success_redirect(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(responses.PUT, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        obj = models.GroupAccountMembership.objects.latest("pk")
        self.assertRedirects(response, obj.get_absolute_url())

    def test_get_duplicate_object(self):
        """Redirects to detail view if object already exists."""
        obj = factories.GroupAccountMembershipFactory.create(
            group=self.group,
            account=self.account,
            role=models.GroupAccountMembership.MEMBER,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(self.group.name, self.account.uuid),
            follow=True,
        )
        self.assertRedirects(response, obj.get_absolute_url())
        # No new object was created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        # A message exists.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupAccountMembershipCreateByGroupAccount.message_already_exists,
            str(messages[0]),
        )

    def test_post_duplicate_object(self):
        """Cannot create a second object for the same account and group with a different role."""
        obj = factories.GroupAccountMembershipFactory.create(
            group=self.group,
            account=self.account,
            role=models.GroupAccountMembership.MEMBER,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
            follow=True,
        )
        self.assertRedirects(response, obj.get_absolute_url())
        # No new object was created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        obj.refresh_from_db()
        self.assertEqual(obj.role, models.GroupAccountMembership.MEMBER)
        # A message exists.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupAccountMembershipCreateByGroupAccount.message_already_exists,
            str(messages[0]),
        )

    def test_get_group_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.get(self.get_url("foo", self.account.uuid))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, group_slug="foo", account_uuid=self.account.uuid)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_group_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.post(
            self.get_url(
                "foo",
                self.account.uuid,
            ),
            {
                "group": self.group.pk + 1,
                "account": self.account,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                group_slug="foo",
                account_uuid=self.account.uuid,
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_get_account_not_found(self):
        """Raises 404 if account in URL does not exist."""
        uuid = uuid4()
        request = self.factory.get(self.get_url(self.group.name, uuid))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, group_slug=self.group.name, account_uuid=uuid)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_account_not_found(self):
        """Raises 404 if account in URL does not exist when posting data."""
        uuid = uuid4()
        request = self.factory.post(
            self.get_url(
                self.group.name,
                uuid,
            ),
            {
                "group": self.group.pk,
                "account": uuid,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                group_slug=self.group.name,
                account_uuid=uuid,
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_input_role(self):
        """Posting invalid data to group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {"group": self.group.pk, "account": self.account.pk, "role": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("valid choice", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(self.group.name, self.account.uuid), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("account", form.errors.keys())
        self.assertIn("required", form.errors["account"][0])
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_group(self):
        """Posting blank data to the group field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {"account": self.account.pk, "role": models.GroupAccountMembership.MEMBER},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_account(self):
        """Posting blank data to the account field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {"group": self.group.pk, "role": models.GroupAccountMembership.MEMBER},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("account", form.errors.keys())
        self.assertIn("required", form.errors["account"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_role(self):
        """Posting blank data to the role field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {"group": self.group.pk, "account": self.account.pk},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_cannot_add_account_if_group_not_managed_by_app(self):
        """Cannot add an account to a group if the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {
                "group": group.pk,
                "account": self.account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_500(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=500,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_400(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=400,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_403(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=403,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_api_error_404(self):
        """Shows a message if an AnVIL API error occurs."""
        api_url = self.get_api_url("member")
        self.anvil_response_mock.add(
            responses.PUT,
            api_url,
            status=404,
            json={"message": "group account membership create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, self.account.uuid),
            {
                "group": self.group.pk,
                "account": self.account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_cannot_add_inactive_account_to_group(self):
        """Cannot add an inactive account to a group."""
        account = factories.AccountFactory.create(status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name, account.uuid),
            {
                "group": self.group.pk,
                "account": account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("account", form.errors.keys())
        self.assertIn("valid choice", form.errors["account"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)


class GroupAccountMembershipListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:group_account_membership:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipList.as_view()

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

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.GroupAccountMembershipStaffTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.GroupAccountMembershipFactory()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.GroupAccountMembershipFactory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class GroupAccountMembershipActiveListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:group_account_membership:list_active", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipActiveList.as_view()

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

    def test_view_has_correct_table_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.GroupAccountMembershipStaffTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.GroupAccountMembershipFactory()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.GroupAccountMembershipFactory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_does_not_show_inactive_accounts(self):
        """Inactive accounts are not shown."""
        factories.GroupAccountMembershipFactory.create_batch(2, account__status=models.Account.INACTIVE_STATUS)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)


class GroupAccountMembershipInactiveListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:group_account_membership:list_inactive", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipInactiveList.as_view()

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

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.GroupAccountMembershipStaffTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        membership = factories.GroupAccountMembershipFactory()
        membership.account.status = models.Account.INACTIVE_STATUS
        membership.account.save()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        memberships = factories.GroupAccountMembershipFactory.create_batch(2)
        memberships[0].account.status = models.Account.INACTIVE_STATUS
        memberships[0].account.save()
        memberships[1].account.status = models.Account.INACTIVE_STATUS
        memberships[1].account.save()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_does_not_show_active_accounts(self):
        """Active accounts are not shown."""
        factories.GroupAccountMembershipFactory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)


class GroupAccountMembershipDeleteTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:member_accounts:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipDelete.as_view()

    def get_api_url(self, group_name, role, email):
        url = self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/" + role + "/" + email
        return url

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        uuid = uuid4()
        response = self.client.get(self.get_url("foo", uuid))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", uuid),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.GroupAccountMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.group.name, obj.account.uuid))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        uuid = uuid4()
        request = self.factory.get(self.get_url("foo", uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, group_slug="foo", account_uuid=uuid)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", uuid4()))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        uuid = uuid4()
        request = self.factory.get(self.get_url("foo", uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, group_slug="foo", account_uuid=uuid)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        uuid = uuid4()
        request = self.factory.get(self.get_url("foo", uuid))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, group_slug="foo", account_uuid=uuid)

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        object = factories.GroupAccountMembershipFactory.create()
        api_url = self.get_api_url(object.group.name, object.role.lower(), object.account.email)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.group.name, object.account.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)
        # History is added.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        object = factories.GroupAccountMembershipFactory.create()
        api_url = self.get_api_url(object.group.name, object.role.lower(), object.account.email)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.group.name, object.account.uuid),
            {"submit": ""},
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupAccountMembershipDelete.success_message, str(messages[0]))

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.GroupAccountMembershipFactory.create()
        other_object = factories.GroupAccountMembershipFactory.create()
        api_url = self.get_api_url(object.group.name, object.role.lower(), object.account.email)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.group.name, object.account.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        self.assertQuerySetEqual(
            models.GroupAccountMembership.objects.all(),
            models.GroupAccountMembership.objects.filter(pk=other_object.pk),
        )

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.GroupAccountMembershipFactory.create()
        group = object.group
        api_url = self.get_api_url(object.group.name, object.role.lower(), object.account.email)
        self.anvil_response_mock.add(responses.DELETE, api_url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.group.name, object.account.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, group.get_absolute_url())

    def test_get_redirect_group_not_managed_by_app(self):
        """Redirect get when trying to delete GroupAccountMembership when the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        account = factories.AccountFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(group=group, account=account)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(membership.group.name, membership.account.uuid), follow=True)
        self.assertRedirects(response, membership.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupAccountMembershipDelete.message_group_not_managed_by_app,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)

    def test_post_redirect_group_not_managed_by_app(self):
        """Redirect post when trying to delete GroupAccountMembership when the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        account = factories.AccountFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(group=group, account=account)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(membership.group.name, membership.account.uuid), follow=True)
        self.assertRedirects(response, membership.get_absolute_url())
        # Check for messages.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupAccountMembershipDelete.message_group_not_managed_by_app,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)

    def test_api_error_500(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.GroupAccountMembershipFactory.create()
        api_url = self.get_api_url(object.group.name, object.role.lower(), object.account.email)
        self.anvil_response_mock.add(
            responses.DELETE,
            api_url,
            status=500,
            json={"message": "group account membership delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.group.name, object.account.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership delete test error",
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)

    def test_api_error_400(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.GroupAccountMembershipFactory.create()
        api_url = self.get_api_url(object.group.name, object.role.lower(), object.account.email)
        self.anvil_response_mock.add(
            responses.DELETE,
            api_url,
            status=400,
            json={"message": "group account membership delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.group.name, object.account.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership delete test error",
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)

    def test_api_error_403(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.GroupAccountMembershipFactory.create()
        api_url = self.get_api_url(object.group.name, object.role.lower(), object.account.email)
        self.anvil_response_mock.add(
            responses.DELETE,
            api_url,
            status=403,
            json={"message": "group account membership delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.group.name, object.account.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership delete test error",
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)

    def test_api_error_404(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.GroupAccountMembershipFactory.create()
        api_url = self.get_api_url(object.group.name, object.role.lower(), object.account.email)
        self.anvil_response_mock.add(
            responses.DELETE,
            api_url,
            status=404,
            json={"message": "group account membership delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.group.name, object.account.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership delete test error",
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)


class WorkspaceGroupSharingDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:sharing:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupSharingDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("billing_project", "workspace", "group"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("billing_project", "workspace", "group"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.WorkspaceGroupSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertEqual(response.status_code, 200)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar", "tmp"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("billing_project", "workspace", "group"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug="billing_project",
                workspace_slug="workspace",
                group_slug="group",
            )

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        factories.WorkspaceGroupSharingFactory.create()
        request = self.factory.get(self.get_url("billing_project", "workspace", "group"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="billing_project",
                workspace_slug="workspace",
                group_slug="group",
            )

    def test_edit_permission(self):
        """Links to delete url appears if the user has edit permission."""
        edit_user = User.objects.create_user(username="edit", password="test")
        edit_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME),
        )
        self.client.force_login(edit_user)
        obj = factories.WorkspaceGroupSharingFactory.create()
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertTrue(response.context_data["show_edit_links"])
        self.assertContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:sharing:delete",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                    "group_slug": obj.group.name,
                },
            ),
        )

    def test_view_permission(self):
        """Links to delete url appears if the user has edit permission."""
        view_user = User.objects.create_user(username="view", password="test")
        view_user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME),
        )
        self.client.force_login(view_user)
        obj = factories.WorkspaceGroupSharingFactory.create()
        response = self.client.get(obj.get_absolute_url())
        self.assertIn("show_edit_links", response.context_data)
        self.assertFalse(response.context_data["show_edit_links"])
        self.assertNotContains(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:sharing:delete",
                kwargs={
                    "billing_project_slug": obj.workspace.billing_project.name,
                    "workspace_slug": obj.workspace.name,
                    "group_slug": obj.group.name,
                },
            ),
        )


class WorkspaceGroupSharingCreateTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspace_group_sharing:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupSharingCreate.as_view()

    def get_api_url(self, billing_project_name, workspace_name):
        url = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
            + "/acl?inviteUsersNotFound=false"
        )
        return url

    def get_api_json_response(self, invites_sent=[], users_not_found=[], users_updated=[]):
        return {
            "invitesSent": invites_sent,
            "usersNotFound": users_not_found,
            "usersUpdated": users_updated,
        }

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

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceGroupSharingForm)

    def test_can_create_an_object_reader(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url("test-billing-project", "test-workspace")
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.READER)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_create_a_writer_with_can_compute(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        api_url = self.get_api_url("test-billing-project", "test-workspace")
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.WRITER)
        self.assertEqual(new_object.can_compute, True)

    def test_success_message(self):
        """Response includes a success message if successful."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url("test-billing-project", "test-workspace")
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceGroupSharingCreate.success_message, str(messages[0]))

    def test_can_create_an_object_writer(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.WRITER)
        self.assertEqual(new_object.can_compute, False)

    def test_can_create_an_object_owner(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.OWNER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.OWNER)

    def test_redirects_to_list(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertRedirects(response, reverse("anvil_consortium_manager:workspace_group_sharing:list"))

    def test_cannot_create_duplicate_object_with_same_access(self):
        """Cannot create a second object for the same workspace and group with the same access level."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupSharingFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupSharing.READER,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.WorkspaceGroupSharing.objects.all(),
            models.WorkspaceGroupSharing.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_with_different_access(self):
        """Cannot create a second object for the same workspace and group with a different access level."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupSharingFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupSharing.READER,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.WorkspaceGroupSharing.objects.all(),
            models.WorkspaceGroupSharing.objects.filter(pk=obj.pk),
        )

    def test_can_have_two_workspaces_for_one_group(self):
        group_1 = factories.ManagedGroupFactory.create(name="test-group-1")
        group_2 = factories.ManagedGroupFactory.create(name="test-group-2")
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceGroupSharingFactory.create(group=group_1, workspace=workspace)
        json_data = [
            {
                "email": group_2.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group_2.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 2)

    def test_can_have_two_groups_for_one_workspace(self):
        group = factories.ManagedGroupFactory.create()
        workspace_1 = factories.WorkspaceFactory.create(name="test-workspace-1")
        workspace_2 = factories.WorkspaceFactory.create(name="test-workspace-2")
        factories.WorkspaceGroupSharingFactory.create(group=group, workspace=workspace_1)
        json_data = [
            {
                "email": group.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace_2.billing_project.name, workspace_2.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace_2.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 2)

    def test_invalid_input_group(self):
        """Posting invalid data to group field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": 1,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_input_workspace(self):
        """Posting invalid data to workspace field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": 1,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("valid choice", form.errors["workspace"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_input_access(self):
        """Posting invalid data to access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": "foo",
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("valid choice", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_reader_with_can_compute(self):
        """Posting invalid data to access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("cannot be granted compute", form.non_field_errors()[0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_blank_data_group(self):
        """Posting blank data to the group field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_blank_data_workspace(self):
        """Posting blank data to the workspace field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_blank_data_access(self):
        """Posting blank data to the access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_blank_data_can_compute(self):
        """Posting blank data to the can_compute field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": workspace.pk,
                "group": group.pk,
                "access": models.WorkspaceGroupSharing.READER,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertEqual(new_object.can_compute, False)
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)

    def test_invalid_anvil_group_does_not_exist(self):
        """No object is saved if the group doesn't exist on AnVIL but does exist in the app."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project__name="test-billing-project"
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_not_found=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        # The form is valid, but there was a different error.
        self.assertTrue(form.is_valid())
        self.assertEqual(response.status_code, 200)
        # Check for the correct message.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            views.WorkspaceGroupSharingCreate.message_group_not_found,
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=500,
            json={"message": "workspace group access create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: workspace group access create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    @skip("AnVIL API issue")
    def test_api_sharing_workspace_that_doesnt_exist_with_group_that_doesnt_exist(
        self,
    ):
        self.fail(
            "Sharing a workspace that doesn't exist with a group that doesn't exist returns a successful code."  # noqa
        )


class WorkspaceGroupSharingCreateByWorkspaceTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.workspace = factories.WorkspaceFactory.create()
        self.group = factories.ManagedGroupFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:sharing:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupSharingCreateByWorkspace.as_view()

    def get_api_url(self, billing_project_name, workspace_name):
        url = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
            + "/acl?inviteUsersNotFound=false"
        )
        return url

    def get_api_json_response(self, invites_sent=[], users_not_found=[], users_updated=[]):
        return {
            "invitesSent": invites_sent,
            "usersNotFound": users_not_found,
            "usersUpdated": users_updated,
        }

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            )
        )
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            )
        )
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug=self.workspace.name,
            )

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            )
        )
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug=self.workspace.name,
            )

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            )
        )
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceGroupSharingForm)

    def test_context_workspace(self):
        """Context contains the workspace."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            )
        )
        self.assertTrue("workspace" in response.context_data)
        self.assertEqual(response.context_data["workspace"], self.workspace)

    def test_form_hidden_input(self):
        """The proper inputs are hidden in the form."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            )
        )
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceGroupSharingForm)
        self.assertIsInstance(response.context_data["form"].fields["workspace"].widget, HiddenInput)

    def test_can_create_an_object_reader(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.READER)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_create_a_writer_with_can_compute(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.WRITER)
        self.assertEqual(new_object.can_compute, True)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_success_message(self):
        """Response includes a success message if successful."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceGroupSharingCreateByWorkspaceGroup.success_message,
            str(messages[0]),
        )

    def test_can_create_an_object_writer(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.WRITER)
        self.assertEqual(new_object.can_compute, False)

    def test_can_create_an_object_owner(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.OWNER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.OWNER)

    def test_success_redirect(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertRedirects(
            response,
            models.WorkspaceGroupSharing.objects.latest("pk").get_absolute_url(),
        )

    def test_cannot_create_duplicate_object_with_same_access(self):
        """Cannot create a second object for the same workspace and group with the same access level."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupSharingFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupSharing.READER,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.WorkspaceGroupSharing.objects.all(),
            models.WorkspaceGroupSharing.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_with_different_access(self):
        """Cannot create a second object for the same workspace and group with a different access level."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupSharingFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupSharing.READER,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.WorkspaceGroupSharing.objects.all(),
            models.WorkspaceGroupSharing.objects.filter(pk=obj.pk),
        )

    def test_group_not_found(self):
        """Form error if group does not exist."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name),
            {
                "group": self.group.pk + 1,
                "workspace": self.workspace.pk,
                "access": models.WorkspaceGroupSharing.OWNER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors)
        self.assertEqual(len(form.errors["group"]), 1)
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_get_billing_project_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.get(self.get_url("foo", self.workspace.name))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="foo",
                workspace_slug=self.workspace.name,
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_billing_project_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.post(
            self.get_url("foo", self.workspace.name),
            {
                "group": self.group.pk,
                "workspace": self.workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug="foo",
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_get_workspace_not_found(self):
        """Raises 404 if workspace in URL does not exist when posting data."""
        # Create a workspace with the same name but different billing project.
        factories.WorkspaceFactory.create(name="foo")
        request = self.factory.get(self.get_url(self.workspace.billing_project.name, "foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug="foo",
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_workspace_not_found(self):
        """Raises 404 if workspace in URL does not exist when posting data."""
        # Create a workspace with the same name but different billing project.
        factories.WorkspaceFactory.create(name="foo")
        request = self.factory.post(
            self.get_url(self.workspace.billing_project.name, "foo"),
            {
                "group": self.group.pk,
                "workspace": self.workspace.pk + 1,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug="foo",
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_input_access(self):
        """Posting invalid data to access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": "foo",
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("valid choice", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_reader_with_can_compute(self):
        """Posting invalid data to access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("cannot be granted compute", form.non_field_errors()[0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_blank_data_access(self):
        """Posting blank data to the access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_anvil_group_does_not_exist(self):
        """No object is saved if the group doesn't exist on AnVIL but does exist in the app."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project__name="test-billing-project"
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_not_found=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        # The form is valid, but there was a different error.
        self.assertTrue(form.is_valid())
        self.assertEqual(response.status_code, 200)
        # Check for the correct message.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            views.WorkspaceGroupSharingCreate.message_group_not_found,
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=500,
            json={"message": "workspace group access create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: workspace group access create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    @skip("AnVIL API issue")
    def test_api_sharing_workspace_that_doesnt_exist_with_group_that_doesnt_exist(
        self,
    ):
        self.fail(
            "Sharing a workspace that doesn't exist with a group that doesn't exist returns a successful code."  # noqa
        )


class WorkspaceGroupSharingCreateByGroupTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.workspace = factories.WorkspaceFactory.create()
        self.group = factories.ManagedGroupFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:sharing:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupSharingCreateByGroup.as_view()

    def get_api_url(self, billing_project_name, workspace_name):
        url = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
            + "/acl?inviteUsersNotFound=false"
        )
        return url

    def get_api_json_response(self, invites_sent=[], users_not_found=[], users_updated=[]):
        return {
            "invitesSent": invites_sent,
            "usersNotFound": users_not_found,
            "usersUpdated": users_updated,
        }

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(
            self.get_url(
                self.group.name,
            )
        )
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url(
                self.group.name,
            ),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.group.name,
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(
            self.get_url(
                self.group.name,
            )
        )
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                group_slug=self.group.name,
            )

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(
            self.get_url(
                self.group.name,
            )
        )
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                group_slug=self.group.name,
            )

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.group.name,
            )
        )
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceGroupSharingForm)

    def test_context_group(self):
        """Context contains the group."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.group.name,
            )
        )
        self.assertTrue("group" in response.context_data)
        self.assertEqual(response.context_data["group"], self.group)

    def test_form_hidden_input(self):
        """The proper inputs are hidden in the form."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.group.name,
            )
        )
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceGroupSharingForm)
        self.assertIsInstance(response.context_data["form"].fields["group"].widget, HiddenInput)

    def test_can_create_an_object_reader(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.READER)
        self.assertEqual(new_object.workspace, workspace)
        self.assertEqual(new_object.group, group)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_create_a_writer_with_can_compute(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(group.name),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.WRITER)
        self.assertEqual(new_object.can_compute, True)

    def test_success_message(self):
        """Response includes a success message if successful."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(group.name),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceGroupSharingCreateByWorkspaceGroup.success_message,
            str(messages[0]),
        )

    def test_can_create_an_object_writer(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.WRITER)
        self.assertEqual(new_object.can_compute, False)

    def test_can_create_an_object_owner(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.OWNER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.OWNER)

    def test_success_redirect(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertRedirects(
            response,
            models.WorkspaceGroupSharing.objects.latest("pk").get_absolute_url(),
        )

    def test_cannot_create_duplicate_object_with_same_access(self):
        """Cannot create a second object for the same workspace and group with the same access level."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupSharingFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupSharing.READER,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.group.name),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.WorkspaceGroupSharing.objects.all(),
            models.WorkspaceGroupSharing.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_with_different_access(self):
        """Cannot create a second object for the same workspace and group with a different access level."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupSharingFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupSharing.READER,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.group.name),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.WorkspaceGroupSharing.objects.all(),
            models.WorkspaceGroupSharing.objects.filter(pk=obj.pk),
        )

    def test_workspace_not_found(self):
        """Form error if workspace does not exist."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.group.name),
            {
                "group": self.group.pk,
                "workspace": self.workspace.pk + 1,
                "access": models.WorkspaceGroupSharing.OWNER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("valid choice", form.errors["workspace"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_get_group_not_found(self):
        """Raises 404 if group in URL does not exist with get request."""
        # Create a workspace with the same name but different billing project.
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                group_slug="foo",
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_group_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        # Create a workspace with the same name but different billing project.
        request = self.factory.post(
            self.get_url("foo"),
            {
                "group": self.group.pk,
                "workspace": self.workspace.pk + 1,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                group_slug="foo",
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_input_access(self):
        """Posting invalid data to access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": "foo",
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("valid choice", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_reader_with_can_compute(self):
        """Posting invalid data to access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("cannot be granted compute", form.non_field_errors()[0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.group.name,
            ),
            {},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_blank_data_access(self):
        """Posting blank data to the access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_anvil_group_does_not_exist(self):
        """No object is saved if the group doesn't exist on AnVIL but does exist in the app."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project__name="test-billing-project"
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_not_found=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        # The form is valid, but there was a different error.
        self.assertTrue(form.is_valid())
        self.assertEqual(response.status_code, 200)
        # Check for the correct message.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            views.WorkspaceGroupSharingCreate.message_group_not_found,
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=500,
            json={"message": "workspace group access create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: workspace group access create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    @skip("AnVIL API issue")
    def test_api_sharing_workspace_that_doesnt_exist_with_group_that_doesnt_exist(
        self,
    ):
        self.fail(
            "Sharing a workspace that doesn't exist with a group that doesn't exist returns a successful code."  # noqa
        )


class WorkspaceGroupSharingCreateByWorkspaceGroupTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.workspace = factories.WorkspaceFactory.create()
        self.group = factories.ManagedGroupFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:sharing:new_by_group", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupSharingCreateByWorkspaceGroup.as_view()

    def get_api_url(self, billing_project_name, workspace_name):
        url = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
            + "/acl?inviteUsersNotFound=false"
        )
        return url

    def get_api_json_response(self, invites_sent=[], users_not_found=[], users_updated=[]):
        return {
            "invitesSent": invites_sent,
            "usersNotFound": users_not_found,
            "usersUpdated": users_updated,
        }

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            )
        )
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            )
        )
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug=self.workspace.name,
                group_slug=self.group.name,
            )

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar", "tmp"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            )
        )
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug=self.workspace.name,
                group_slug=self.group.name,
            )

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            )
        )
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceGroupSharingForm)

    def test_context_group(self):
        """Context contains the group."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            )
        )
        self.assertTrue("group" in response.context_data)
        self.assertEqual(response.context_data["group"], self.group)

    def test_context_workspace(self):
        """Context contains the workspace."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            )
        )
        self.assertTrue("workspace" in response.context_data)
        self.assertEqual(response.context_data["workspace"], self.workspace)

    def test_form_hidden_input(self):
        """The proper inputs are hidden in the form."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            )
        )
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceGroupSharingForm)
        self.assertIsInstance(response.context_data["form"].fields["workspace"].widget, HiddenInput)
        self.assertIsInstance(response.context_data["form"].fields["group"].widget, HiddenInput)

    def test_can_create_an_object_reader(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.READER)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_create_a_writer_with_can_compute(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.WRITER)
        self.assertEqual(new_object.can_compute, True)

    def test_success_message(self):
        """Response includes a success message if successful."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceGroupSharingCreateByWorkspaceGroup.success_message,
            str(messages[0]),
        )

    def test_can_create_an_object_writer(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.WRITER)
        self.assertEqual(new_object.can_compute, False)

    def test_can_create_an_object_owner(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.OWNER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupSharing)
        self.assertEqual(new_object.access, models.WorkspaceGroupSharing.OWNER)

    def test_success_redirect(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertRedirects(
            response,
            models.WorkspaceGroupSharing.objects.latest("pk").get_absolute_url(),
        )

    def test_get_duplicate_object(self):
        """Redirects to detail view if object already exists."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupSharingFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupSharing.READER,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            follow=True,
        )
        self.assertRedirects(response, obj.get_absolute_url())
        # No new object was created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        # A message exists.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceGroupSharingCreateByWorkspaceGroup.message_already_exists,
            str(messages[0]),
        )

    def test_post_duplicate_object(self):
        """Cannot create a second object for the same workspace and group with the same access level."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupSharingFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupSharing.READER,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
            follow=True,
        )
        self.assertRedirects(response, obj.get_absolute_url())
        # No new object was created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        # A message exists.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceGroupSharingCreateByWorkspaceGroup.message_already_exists,
            str(messages[0]),
        )

    def test_get_group_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.get(self.get_url(self.workspace.billing_project.name, self.workspace.name, "foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug=self.workspace.name,
                group_slug="foo",
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_group_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name, "foo"),
            {
                "group": self.group.pk + 1,
                "workspace": self.workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug=self.workspace.name,
                group_slug="foo",
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_get_billing_project_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.get(self.get_url("foo", self.workspace.name, self.group.name))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="foo",
                workspace_slug=self.workspace.name,
                group_slug=self.group,
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_billing_project_not_found(self):
        """Raises 404 if group in URL does not exist when posting data."""
        request = self.factory.post(
            self.get_url("foo", self.workspace.name, self.group.name),
            {
                "group": self.group.pk,
                "workspace": self.workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="foo",
                workspace_slug=self.workspace.name,
                group_slug=self.group,
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_get_workspace_not_found(self):
        """Raises 404 if workspace in URL does not exist when posting data."""
        # Create a workspace with the same name but different billing project.
        factories.WorkspaceFactory.create(name="foo")
        request = self.factory.get(self.get_url(self.workspace.billing_project.name, "foo", self.group.name))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug="foo",
                group_slug=self.group.name,
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_workspace_not_found(self):
        """Raises 404 if workspace in URL does not exist when posting data."""
        # Create a workspace with the same name but different billing project.
        factories.WorkspaceFactory.create(name="foo")
        request = self.factory.post(
            self.get_url(self.workspace.billing_project.name, "foo", self.group.name),
            {
                "group": self.group.pk,
                "workspace": self.workspace.pk + 1,
                "access": models.WorkspaceGroupSharing.WRITER,
                "can_compute": False,
            },
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.billing_project.name,
                workspace_slug="foo",
                group_slug=self.group.name,
            )
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_input_access(self):
        """Posting invalid data to access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": "foo",
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("valid choice", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_reader_with_can_compute(self):
        """Posting invalid data to access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("cannot be granted compute", form.non_field_errors()[0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_blank_data_access(self):
        """Posting blank data to the access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_invalid_anvil_group_does_not_exist(self):
        """No object is saved if the group doesn't exist on AnVIL but does exist in the app."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project__name="test-billing-project"
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_not_found=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        # The form is valid, but there was a different error.
        self.assertTrue(form.is_valid())
        self.assertEqual(response.status_code, 200)
        # Check for the correct message.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            views.WorkspaceGroupSharingCreate.message_group_not_found,
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=500,
            json={"message": "workspace group access create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                self.workspace.billing_project.name,
                self.workspace.name,
                self.group.name,
            ),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupSharing.READER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: workspace group access create test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    @skip("AnVIL API issue")
    def test_api_sharing_workspace_that_doesnt_exist_with_group_that_doesnt_exist(
        self,
    ):
        self.fail(
            "Sharing a workspace that doesn't exist with a group that doesn't exist returns a successful code."  # noqa
        )


class WorkspaceGroupSharingUpdateTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:sharing:update", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupSharingUpdate.as_view()

    def get_api_url(self, billing_project_name, workspace_name):
        url = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
            + "/acl?inviteUsersNotFound=false"
        )
        return url

    def get_api_json_response(self, invites_sent=[], users_not_found=[], users_updated=[]):
        return {
            "invitesSent": invites_sent,
            "usersNotFound": users_not_found,
            "usersUpdated": users_updated,
        }

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("billing_project", "workspace", "group"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("billing_project", "workspace", "group"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.WorkspaceGroupSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("billing_project", "workspace", "group"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug="billing_project",
                workspace_slug="workspace",
                group_slug="group",
            )

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar", "tmp"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("billing_project", "workspace", "group"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug="billing_project",
                workspace_slug="workspace",
                group_slug="group",
            )

    def test_has_form_in_context(self):
        """Response includes a form."""
        obj = factories.WorkspaceGroupSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name))
        self.assertTrue("form" in response.context_data)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url("billing_project", "workspace", "group"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="billing_project",
                workspace_slug="workspace",
                group_slug="group",
            )

    def test_can_update_role(self):
        """Can update the role through the view."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        obj = factories.WorkspaceGroupSharingFactory.create(
            group=group, workspace=workspace, access=models.WorkspaceGroupSharing.READER
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {
                "access": models.WorkspaceGroupSharing.WRITER,
            },
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupSharing.WRITER)
        # History is added.
        self.assertEqual(obj.history.count(), 2)
        self.assertEqual(obj.history.latest().history_type, "~")

    def test_can_update_can_compute(self):
        """Can update the can_compute field."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        obj = factories.WorkspaceGroupSharingFactory.create(
            group=group, workspace=workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {"access": models.WorkspaceGroupSharing.WRITER, "can_compute": True},
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupSharing.WRITER)
        self.assertEqual(obj.can_compute, True)

    def test_invalid_reader_can_compute(self):
        """The form is not valid when trying to update a READER's can_compute value to True."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        obj = factories.WorkspaceGroupSharingFactory.create(
            group=group, workspace=workspace, access=models.WorkspaceGroupSharing.READER
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {"access": models.WorkspaceGroupSharing.READER, "can_compute": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("cannot be granted compute", form.non_field_errors()[0])
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupSharing.READER)
        self.assertEqual(obj.can_compute, False)
        # History is not added.
        self.assertEqual(obj.history.count(), 1)

    def test_success_message(self):
        """Response includes a success message if successful."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        obj = factories.WorkspaceGroupSharingFactory.create(
            group=group, workspace=workspace, access=models.WorkspaceGroupSharing.READER
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {
                "access": models.WorkspaceGroupSharing.WRITER,
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceGroupSharingUpdate.success_message, str(messages[0]))

    def test_redirects_to_detail(self):
        """After successfully updating an object, view redirects to the model's get_absolute_url."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        obj = factories.WorkspaceGroupSharingFactory(access=models.WorkspaceGroupSharing.READER)
        json_data = [
            {
                "email": obj.group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {
                "access": models.WorkspaceGroupSharing.WRITER,
            },
        )
        self.assertRedirects(response, obj.get_absolute_url())

    def test_post_blank_data_access(self):
        """Posting blank data to the access field does not update the object."""
        obj = factories.WorkspaceGroupSharingFactory.create(access=models.WorkspaceGroupSharing.READER)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {"access": ""},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupSharing.READER)

    def test_post_blank_data_can_compute(self):
        """Posting blank data to the can_compute field updates the object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project__name="test-billing-project"
        )
        obj = factories.WorkspaceGroupSharingFactory.create(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupSharing.OWNER,
            can_compute=True,
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {"access": models.WorkspaceGroupSharing.WRITER},
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupSharing.WRITER)
        self.assertEqual(obj.can_compute, False)

    def test_post_invalid_data_access(self):
        """Posting invalid data to the access field does not update the object."""
        obj = factories.WorkspaceGroupSharingFactory.create(access=models.WorkspaceGroupSharing.READER)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {"access": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("valid choice", form.errors["access"][0])
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupSharing.READER)

    def test_post_group_pk(self):
        """Posting a group pk has no effect."""
        original_group = factories.ManagedGroupFactory.create()
        obj = factories.WorkspaceGroupSharingFactory(group=original_group, access=models.WorkspaceGroupSharing.READER)
        new_group = factories.ManagedGroupFactory.create()
        json_data = [
            {
                "email": obj.group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {
                "group": new_group.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
            },
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.group, original_group)

    def test_post_workspace_pk(self):
        """Posting a workspace pk has no effect."""
        original_workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupSharingFactory(
            workspace=original_workspace, access=models.WorkspaceGroupSharing.READER
        )
        new_workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": obj.group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {
                "workspace": new_workspace.pk,
                "access": models.WorkspaceGroupSharing.WRITER,
            },
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.workspace, original_workspace)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        obj = factories.WorkspaceGroupSharingFactory.create(access=models.WorkspaceGroupSharing.READER)
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=500,
            json={"message": "workspace group access update test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {
                "access": models.WorkspaceGroupSharing.WRITER,
            },
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: workspace group access update test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupSharing.READER)

    @skip("AnVIL API issue")
    def test_api_updating_access_to_workspace_that_doesnt_exist_for_group_that_doesnt_exist(
        self,
    ):
        self.fail(
            "Updating access from workspace that doesn't exist for a group that doesn't exist returns a successful code."  # noqa
        )


class WorkspaceGroupSharingListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspace_group_sharing:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupSharingList.as_view()

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

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.WorkspaceGroupSharingStaffTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.WorkspaceGroupSharingFactory()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.WorkspaceGroupSharingFactory.create(workspace__name="w1")
        factories.WorkspaceGroupSharingFactory.create(workspace__name="w2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class WorkspaceGroupSharingDeleteTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:sharing:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupSharingDelete.as_view()

    def get_api_url(self, billing_project_name, workspace_name):
        url = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
            + "/acl?inviteUsersNotFound=false"
        )
        return url

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("billing_project", "workspace", "group"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("billing_project", "workspace", "group"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.WorkspaceGroupSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("billing_project", "workspace", "group"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug="billing_project",
                workspace_slug="workspace",
                group_slug="group",
            )

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar", "tmp"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("billing_project", "workspace", "group"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug="billing_project",
                workspace_slug="workspace",
                group_slug="group",
            )

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url("billing_project", "workspace", "group"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="billing_project",
                workspace_slug="workspace",
                group_slug="group",
            )

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        obj = factories.WorkspaceGroupSharingFactory.create(group=group, workspace=workspace)
        json_data = [
            {
                "email": obj.group.email,
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)
        # History is added.
        self.assertEqual(obj.history.count(), 2)
        self.assertEqual(obj.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        obj = factories.WorkspaceGroupSharingFactory.create(group=group, workspace=workspace)
        json_data = [
            {
                "email": obj.group.email,
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {"submit": ""},
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceGroupSharingDelete.success_message, str(messages[0]))

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        obj = factories.WorkspaceGroupSharingFactory.create()
        other_object = factories.WorkspaceGroupSharingFactory.create()
        json_data = [
            {
                "email": obj.group.email,
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        self.assertQuerySetEqual(
            models.WorkspaceGroupSharing.objects.all(),
            models.WorkspaceGroupSharing.objects.filter(pk=other_object.pk),
        )

    def test_delete_with_can_compute(self):
        """Can delete a record with can_compute=True."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(name="test-workspace", billing_project=billing_project)
        obj = factories.WorkspaceGroupSharingFactory.create(
            group=group,
            workspace=workspace,
            can_compute=True,
        )
        json_data = [
            {
                "email": obj.group.email,
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": True,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_success_url(self):
        """Redirects to the expected page."""
        obj = factories.WorkspaceGroupSharingFactory.create()
        json_data = [
            {
                "email": obj.group.email,
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        # Need to use the client instead of RequestFactory to check redirection url.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("anvil_consortium_manager:workspace_group_sharing:list"))

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        obj = factories.WorkspaceGroupSharingFactory.create()
        api_url = self.get_api_url(obj.workspace.billing_project.name, obj.workspace.name)
        self.anvil_response_mock.add(
            responses.PATCH,
            api_url,
            status=500,
            json={"message": "workspace group access delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.group.name),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: workspace group access delete test error",
            str(messages[0]),
        )
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)

    @skip("AnVIL API issue")
    def test_api_removing_access_to_workspace_that_doesnt_exist_for_group_that_doesnt_exist(
        self,
    ):
        self.fail(
            "Removing access from workspace that doesn't exist for a group that doesn't exist returns a successful code."  # noqa
        )
