import json
from unittest import skip
from uuid import uuid4

import responses
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.core.exceptions import PermissionDenied
from django.forms import BaseInlineFormSet
from django.http.response import Http404
from django.shortcuts import resolve_url
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .. import forms, models, tables, views
from ..adapter import (
    AdapterAlreadyRegisteredError,
    AdapterNotRegisteredError,
    DefaultWorkspaceAdapter,
    workspace_adapter_registry,
)
from . import factories
from .adapter_app import forms as app_forms
from .adapter_app import models as app_models
from .adapter_app import tables as app_tables
from .adapter_app.adapters import TestWorkspaceAdapter
from .utils import AnVILAPIMockTestMixin


class IndexTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with view permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)


class AnVILStatusTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with view permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        url_me = self.entry_point + "/me?userDetailsOnly=true"
        responses.add(responses.GET, url_me, status=200, json=self.get_json_me_data())
        url_status = self.entry_point + "/status"
        responses.add(
            responses.GET, url_status, status=200, json=self.get_json_status_data()
        )
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_context_data_anvil_status_ok(self):
        """Context data contains anvil_status."""
        url_me = self.entry_point + "/me?userDetailsOnly=true"
        responses.add(responses.GET, url_me, status=200, json=self.get_json_me_data())
        url_status = self.entry_point + "/status"
        responses.add(
            responses.GET, url_status, status=200, json=self.get_json_status_data()
        )
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("anvil_status", response.context_data)
        self.assertEqual(response.context_data["anvil_status"], {"ok": True})
        self.assertIn("anvil_systems_status", response.context_data)
        responses.assert_call_count(url_me, 1)
        responses.assert_call_count(url_status, 1)

    def test_context_data_anvil_status_not_ok(self):
        """Context data contains anvil_status."""
        url_me = self.entry_point + "/me?userDetailsOnly=true"
        responses.add(responses.GET, url_me, status=200, json=self.get_json_me_data())
        url_status = self.entry_point + "/status"
        responses.add(
            responses.GET,
            url_status,
            status=200,
            json=self.get_json_status_data(status_ok=False),
        )
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("anvil_status", response.context_data)
        self.assertEqual(response.context_data["anvil_status"], {"ok": False})
        self.assertIn("anvil_systems_status", response.context_data)
        responses.assert_call_count(url_me, 1)
        responses.assert_call_count(url_status, 1)

    def test_context_data_status_api_error(self):
        """Page still loads if there is an AnVIL API error in the status call."""
        url_me = self.entry_point + "/me?userDetailsOnly=true"
        responses.add(responses.GET, url_me, status=200, json=self.get_json_me_data())
        # Error in status API
        url_status = self.entry_point + "/status"
        responses.add(responses.GET, url_status, status=499)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: error checking API status", str(messages[0]))
        responses.assert_call_count(url_me, 1)
        responses.assert_call_count(url_status, 1)

    def test_context_data_status_me_error(self):
        """Page still loads if there is an AnVIL API error in the me call."""
        url_me = self.entry_point + "/me?userDetailsOnly=true"
        responses.add(responses.GET, url_me, status=499)
        url_status = self.entry_point + "/status"
        responses.add(
            responses.GET,
            url_status,
            status=200,
            json=self.get_json_status_data(status_ok=False),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: error checking API user", str(messages[0]))
        responses.assert_call_count(url_me, 1)
        responses.assert_call_count(url_status, 1)

    def test_context_data_both_api_error(self):
        """Page still loads if there is an AnVIL API error in both the status and me call."""
        url_me = self.entry_point + "/me?userDetailsOnly=true"
        responses.add(responses.GET, url_me, status=499)
        # Error in status API
        url_status = self.entry_point + "/status"
        responses.add(responses.GET, url_status, status=499)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 2)
        self.assertEqual("AnVIL API Error: error checking API status", str(messages[0]))
        self.assertEqual("AnVIL API Error: error checking API user", str(messages[1]))
        responses.assert_call_count(url_me, 1)
        responses.assert_call_count(url_status, 1)


class BillingProjectImportTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_api_url(self, billing_project_name):
        """Get the AnVIL API url that is called by the anvil_exists method."""
        return self.entry_point + "/api/billing/v2/" + billing_project_name

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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(
            response.context_data["form"], forms.BillingProjectImportForm
        )

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        billing_project_name = "test-billing"
        url = self.get_api_url(billing_project_name)
        responses.add(responses.GET, url, status=200, json=self.get_api_json_response())
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

    def test_success_message(self):
        """Response includes a success message if successful."""
        billing_project_name = "test-billing"
        url = self.get_api_url(billing_project_name)
        responses.add(responses.GET, url, status=200, json=self.get_api_json_response())
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(), {"name": billing_project_name}, follow=True
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.BillingProjectImport.success_msg, str(messages[0]))

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        billing_project_name = "test-billing"
        url = self.get_api_url(billing_project_name)
        responses.add(responses.GET, url, status=200, json=self.get_api_json_response())
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": billing_project_name})
        new_object = models.BillingProject.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())

    def test_cannot_create_duplicate_object(self):
        """Cannot create two billing projects with the same name."""
        obj = factories.BillingProjectFactory.create()
        request = self.factory.post(self.get_url(), {"name": obj.name})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("already exists", form.errors["name"][0])
        self.assertQuerysetEqual(
            models.BillingProject.objects.all(),
            models.BillingProject.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_case_insensitive(self):
        """Cannot create two billing projects with the same name."""
        obj = factories.BillingProjectFactory.create(name="project")
        # No API calls should be made.
        request = self.factory.post(self.get_url(), {"name": "PROJECT"})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("already exists", form.errors["name"][0])
        self.assertQuerysetEqual(
            models.BillingProject.objects.all(),
            models.BillingProject.objects.filter(pk=obj.pk),
        )

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        request = self.factory.post(self.get_url(), {"name": ""})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        request.user = self.user
        response = self.get_view()(request)
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
        responses.add(responses.GET, url, status=404, json={"message": "other"})
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
        responses.add(
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


class BillingProjectDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo")
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.BillingProjectFactory.create()
        request = self.factory.get(self.get_url(obj.name))
        request.user = self.user
        response = self.get_view()(request, slug=obj.name)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url("foo"))
        request.user = user_no_perms
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
        request = self.factory.get(self.get_url(obj.name))
        request.user = self.user
        response = self.get_view()(request, slug=obj.name)
        self.assertIn("workspace_table", response.context_data)
        self.assertIsInstance(
            response.context_data["workspace_table"], tables.WorkspaceTable
        )

    def test_workspace_table_none(self):
        """No workspaces are shown if the billing project does not have any workspaces."""
        billing_project = factories.BillingProjectFactory.create()
        request = self.factory.get(self.get_url(billing_project.name))
        request.user = self.user
        response = self.get_view()(request, slug=billing_project.name)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)

    def test_workspace_table_one(self):
        """One workspace is shown if the group have access to one workspace."""
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(billing_project=billing_project)
        request = self.factory.get(self.get_url(billing_project.name))
        request.user = self.user
        response = self.get_view()(request, slug=billing_project.name)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 1)

    def test_workspace_table_two(self):
        """Two workspaces are shown if the group have access to two workspaces."""
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create_batch(2, billing_project=billing_project)
        request = self.factory.get(self.get_url(billing_project.name))
        request.user = self.user
        response = self.get_view()(request, slug=billing_project.name)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 2)

    def test_shows_workspace_for_only_this_group(self):
        """Only shows workspcaes that this group has access to."""
        billing_project = factories.BillingProjectFactory.create()
        other_billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(billing_project=other_billing_project)
        request = self.factory.get(self.get_url(billing_project.name))
        request.user = self.user
        response = self.get_view()(request, slug=billing_project.name)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)


class BillingProjectListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_template_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.BillingProjectTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.BillingProjectFactory()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.BillingProjectFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:billing_projects:autocomplete", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectAutocomplete.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_returns_all_objects(self):
        """Queryset returns all objects when there is no query."""
        objects = factories.BillingProjectFactory.create_batch(10)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 10)
        self.assertEqual(
            sorted(returned_ids), sorted([object.pk for object in objects])
        )

    def test_returns_correct_object_match(self):
        """Queryset returns the correct objects when query matches the name."""
        object = factories.BillingProjectFactory.create(name="test-bp")
        request = self.factory.get(self.get_url(), {"q": "test-bp"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        object = factories.BillingProjectFactory.create(name="test-bp")
        request = self.factory.get(self.get_url(), {"q": "test"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_returns_correct_object_containing_query(self):
        """Queryset returns the correct objects when the name contains the query."""
        object = factories.BillingProjectFactory.create(name="test-bp")
        request = self.factory.get(self.get_url(), {"q": "bp"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        object = factories.BillingProjectFactory.create(name="TEST-BP")
        request = self.factory.get(self.get_url(), {"q": "test-bp"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_does_not_return_groups_not_managed_by_app(self):
        """Queryset does not return groups that are not managed by the app."""
        factories.BillingProjectFactory.create(name="test-bp", has_app_as_user=False)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(json.loads(response.content.decode("utf-8"))["results"], [])


class AccountDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(uuid)
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        request = self.factory.get(self.get_url(obj.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=obj.uuid)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        uuid = uuid4()
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url(uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_context_active_account(self):
        """An is_inactive flag is included in the context."""
        active_account = factories.AccountFactory.create()
        request = self.factory.get(self.get_url(active_account.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=active_account.uuid)
        context = response.context_data
        self.assertIn("is_inactive", context)
        self.assertFalse(context["is_inactive"])
        self.assertIn("show_deactivate_button", context)
        self.assertTrue(context["show_deactivate_button"])
        self.assertIn("show_reactivate_button", context)
        self.assertFalse(context["show_reactivate_button"])

    def test_context_inactive_account(self):
        """An is_inactive flag is included in the context."""
        active_account = factories.AccountFactory.create(
            status=models.Account.INACTIVE_STATUS
        )
        request = self.factory.get(self.get_url(active_account.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=active_account.uuid)
        context = response.context_data
        self.assertIn("is_inactive", context)
        self.assertTrue(context["is_inactive"])
        self.assertIn("show_deactivate_button", context)
        self.assertFalse(context["show_deactivate_button"])
        self.assertIn("show_reactivate_button", context)
        self.assertTrue(context["show_reactivate_button"])

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
        request = self.factory.get(self.get_url(obj.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=obj.uuid)
        self.assertIn("group_table", response.context_data)
        self.assertIsInstance(
            response.context_data["group_table"], tables.GroupAccountMembershipTable
        )

    def test_group_account_membership_none(self):
        """No groups are shown if the account is not part of any groups."""
        account = factories.AccountFactory.create()
        request = self.factory.get(self.get_url(account.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=account.uuid)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)

    def test_group_account_membership_one(self):
        """One group is shown if the account is part of one group."""
        account = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create(account=account)
        request = self.factory.get(self.get_url(account.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=account.uuid)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 1)

    def test_group_account_membership_two(self):
        """Two groups are shown if the account is part of two groups."""
        account = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create_batch(2, account=account)
        request = self.factory.get(self.get_url(account.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=account.uuid)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 2)

    def test_shows_group_account_membership_for_only_that_user(self):
        """Only shows groups that this research is part of."""
        account = factories.AccountFactory.create(email="email_1@example.com")
        other_account = factories.AccountFactory.create(email="email_2@example.com")
        factories.GroupAccountMembershipFactory.create(account=other_account)
        request = self.factory.get(self.get_url(account.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=account.uuid)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)


class AccountImportTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_api_url(self, email):
        """Get the AnVIL API url that is called by the anvil_exists method."""
        return self.entry_point + "/api/proxyGroup/" + email

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:import", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountImport.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.AccountImportForm)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        email = "test@example.com"
        responses.add(responses.GET, self.get_api_url(email), status=200)
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

    def test_success_message(self):
        """Response includes a success message if successful."""
        email = "test@example.com"
        responses.add(responses.GET, self.get_api_url(email), status=200)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"email": email}, follow=True)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountImport.success_msg, str(messages[0]))

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        email = "test@example.com"
        responses.add(responses.GET, self.get_api_url(email), status=200)
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
        request = self.factory.post(self.get_url(), {"email": obj.email})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("already exists", form.errors["email"][0])
        self.assertQuerysetEqual(
            models.Account.objects.all(),
            models.Account.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_case_insensitive(self):
        """Cannot import two accounts with the same email, regardless of case."""
        obj = factories.AccountFactory.create(email="foo@example.com")
        # No API calls should be made.
        request = self.factory.post(self.get_url(), {"email": "FOO@example.com"})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("already exists", form.errors["email"][0])
        self.assertQuerysetEqual(
            models.Account.objects.all(),
            models.Account.objects.filter(pk=obj.pk),
        )

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        request = self.factory.post(self.get_url(), {"email": "1"})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("valid email", form.errors["email"][0])
        self.assertEqual(models.Account.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("required", form.errors["email"][0])
        self.assertEqual(models.Account.objects.count(), 0)

    def test_can_create_service_account(self):
        """Can create a service account."""
        email = "test@example.com"
        responses.add(responses.GET, self.get_api_url(email), status=200)
        # Need a client because messages are added.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(), {"email": email, "is_service_account": True}
        )
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
        responses.add(
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
        self.assertEqual(
            str(messages[0]), views.AccountImport.message_account_does_not_exist
        )
        # No accounts were created.
        self.assertEqual(models.Account.objects.count(), 0)

    def test_api_error(self):
        """Does not create a new Account if the API returns some other error."""
        email = "test@example.com"
        responses.add(
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


class AccountListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.AccountTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.AccountFactory()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.AccountFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_service_account(self):
        factories.AccountFactory.create(is_service_account=True)
        factories.AccountFactory.create(is_service_account=False)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_active_and_inactive_accounts(self):
        """Includes both active and inactive accounts."""
        active_object = factories.AccountFactory.create()
        inactive_object = factories.AccountFactory.create()
        inactive_object.deactivate()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)
        self.assertIn(active_object, response.context_data["table"].data)
        self.assertIn(inactive_object, response.context_data["table"].data)


class AccountActiveListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountActiveList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.AccountTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.AccountFactory()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.AccountFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_service_account(self):
        factories.AccountFactory.create(is_service_account=True)
        factories.AccountFactory.create(is_service_account=False)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_active_and_inactive_accounts(self):
        """Includes both active and inactive accounts."""
        active_object = factories.AccountFactory.create()
        inactive_object = factories.AccountFactory.create()
        inactive_object.deactivate()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(active_object, response.context_data["table"].data)
        self.assertNotIn(inactive_object, response.context_data["table"].data)


class AccountInactiveListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountInactiveList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.AccountTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.AccountFactory(status=models.Account.INACTIVE_STATUS)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.AccountFactory.create_batch(2, status=models.Account.INACTIVE_STATUS)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_service_account(self):
        factories.AccountFactory.create(
            status=models.Account.INACTIVE_STATUS, is_service_account=True
        )
        factories.AccountFactory.create(
            status=models.Account.INACTIVE_STATUS, is_service_account=False
        )
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_active_and_inactive_accounts(self):
        """Includes both active and inactive accounts."""
        active_object = factories.AccountFactory.create()
        inactive_object = factories.AccountFactory.create()
        inactive_object.deactivate()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertNotIn(active_object, response.context_data["table"].data)
        self.assertIn(inactive_object, response.context_data["table"].data)


class AccountDeleteTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountDelete.as_view()

    def get_api_remove_from_group_url(self, group_name, account_email):
        return (
            self.entry_point + "/api/groups/" + group_name + "/MEMBER/" + account_email
        )

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        uuid = uuid4()
        # Need a client for redirects.
        response = self.client.get(self.get_url(uuid))
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(uuid)
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        request = self.factory.get(self.get_url(obj.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=obj.uuid)
        self.assertEqual(response.status_code, 200)

    def test_template_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=uuid)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
        response = self.client.post(
            self.get_url(object.uuid), {"submit": ""}, follow=True
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountDelete.success_msg, str(messages[0]))

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
        self.assertQuerysetEqual(
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
        self.assertRedirects(
            response, reverse("anvil_consortium_manager:accounts:list")
        )

    def test_removes_account_from_one_group(self):
        """Deleting an account from the app also removes it from one group."""
        object = factories.AccountFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(account=object)
        group = membership.group
        remove_from_group_url = self.get_api_remove_from_group_url(
            group.name, object.email
        )
        responses.add(responses.DELETE, remove_from_group_url, status=204)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 0)
        # Also removes the user from groups.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)
        responses.assert_call_count(remove_from_group_url, 1)

    def test_removes_account_from_all_groups(self):
        """Deleting an account from the app also removes it from all groups that it is in."""
        object = factories.AccountFactory.create()
        memberships = factories.GroupAccountMembershipFactory.create_batch(
            2, account=object
        )
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(
            group_1.name, object.email
        )
        responses.add(responses.DELETE, remove_from_group_url_1, status=204)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(
            group_2.name, object.email
        )
        responses.add(responses.DELETE, remove_from_group_url_2, status=204)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 0)
        # Also removes the user from groups.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)
        responses.assert_call_count(remove_from_group_url_1, 1)
        responses.assert_call_count(remove_from_group_url_2, 1)

    def test_api_error_when_removing_account_from_groups(self):
        """Message when an API error occurred when removing a user from a group."""
        object = factories.AccountFactory.create()
        memberships = factories.GroupAccountMembershipFactory.create_batch(
            2, account=object
        )
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(
            group_1.name, object.email
        )
        responses.add(responses.DELETE, remove_from_group_url_1, status=204)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(
            group_2.name, object.email
        )
        responses.add(
            responses.DELETE,
            remove_from_group_url_2,
            status=409,
            json={"message": "test error"},
        )
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.uuid), {"submit": ""}, follow=True
        )
        self.assertRedirects(response, object.get_absolute_url())
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.AccountDelete.message_error_removing_from_groups.format("test error"),
            str(messages[0]),
        )
        # The Account is not deleted.
        self.assertEqual(models.Account.objects.count(), 1)
        models.Account.objects.get(pk=object.pk)
        # Does not remove the user from any groups.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        models.GroupAccountMembership.objects.get(pk=memberships[0].pk)
        models.GroupAccountMembership.objects.get(pk=memberships[1].pk)
        # The API was called.
        responses.assert_call_count(remove_from_group_url_1, 1)
        responses.assert_call_count(remove_from_group_url_2, 1)


class AccountDeactivateTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:deactivate", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountDeactivate.as_view()

    def get_api_remove_from_group_url(self, group_name, account_email):
        return (
            self.entry_point + "/api/groups/" + group_name + "/MEMBER/" + account_email
        )

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        uuid = uuid4()
        response = self.client.get(self.get_url(uuid))
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(uuid)
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        request = self.factory.get(self.get_url(obj.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=obj.uuid)
        self.assertEqual(response.status_code, 200)

    def test_template_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.uuid))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, uuid=uuid)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=uuid)

    def test_get_context_data(self):
        """Context data is correct."""
        object = factories.AccountFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(account=object)
        request = self.factory.get(self.get_url(object.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=object.uuid)
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
        response = self.client.post(
            self.get_url(object.uuid), {"submit": ""}, follow=True
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountDeactivate.success_msg, str(messages[0]))

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
        remove_from_group_url = self.get_api_remove_from_group_url(
            group.name, object.email
        )
        responses.add(responses.DELETE, remove_from_group_url, status=204)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        # Memberships are *not* deleted from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        responses.assert_call_count(remove_from_group_url, 1)
        # History for group-account membership is *not* added.
        self.assertEqual(models.GroupAccountMembership.history.count(), 1)

    def test_removes_account_from_all_groups(self):
        """Deactivating an account from the app also removes it from all groups that it is in."""
        object = factories.AccountFactory.create()
        memberships = factories.GroupAccountMembershipFactory.create_batch(
            2, account=object
        )
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(
            group_1.name, object.email
        )
        responses.add(responses.DELETE, remove_from_group_url_1, status=204)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(
            group_2.name, object.email
        )
        responses.add(responses.DELETE, remove_from_group_url_2, status=204)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        # Status was updated.
        object.refresh_from_db()
        self.assertEqual(object.status, object.INACTIVE_STATUS)
        # Memberships are *not* deleted from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        responses.assert_call_count(remove_from_group_url_1, 1)
        responses.assert_call_count(remove_from_group_url_2, 1)

    def test_api_error_when_removing_account_from_groups(self):
        """Message when an API error occurred when removing a user from a group."""
        object = factories.AccountFactory.create()
        memberships = factories.GroupAccountMembershipFactory.create_batch(
            2, account=object
        )
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(
            group_1.name, object.email
        )
        responses.add(responses.DELETE, remove_from_group_url_1, status=204)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(
            group_2.name, object.email
        )
        responses.add(
            responses.DELETE,
            remove_from_group_url_2,
            status=409,
            json={"message": "test error"},
        )
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.uuid), {"submit": ""}, follow=True
        )
        self.assertRedirects(response, object.get_absolute_url())
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.AccountDeactivate.message_error_removing_from_groups.format(
                "test error"
            ),
            str(messages[0]),
        )
        # The Account is not marked as inactive.
        object.refresh_from_db()
        self.assertEqual(object.status, object.ACTIVE_STATUS)
        # Does not remove the user from any groups.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        models.GroupAccountMembership.objects.get(pk=memberships[0].pk)
        models.GroupAccountMembership.objects.get(pk=memberships[1].pk)
        # The API was called.
        responses.assert_call_count(remove_from_group_url_1, 1)
        responses.assert_call_count(remove_from_group_url_2, 1)

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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.AccountDeactivate.message_already_inactive, str(messages[0])
        )

    def test_account_already_inactive_post(self):
        """Redirects with a message if account is already deactivated."""
        object = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create_batch(2, account=object)
        object.status = object.INACTIVE_STATUS
        object.save()
        # No API calls are made.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.uuid), {"submit": ""}, follow=True
        )
        self.assertRedirects(response, object.get_absolute_url())
        # The object is unchanged.
        object.refresh_from_db()
        self.assertEqual(object.status, object.INACTIVE_STATUS)
        # Memberships are *not* deleted from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        # A message is shown.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.AccountDeactivate.message_already_inactive, str(messages[0])
        )


class AccountReactivateTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:accounts:reactivate", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountReactivate.as_view()

    def get_api_remove_from_group_url(self, group_name, account_email):
        return (
            self.entry_point + "/api/groups/" + group_name + "/MEMBER/" + account_email
        )

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        uuid = uuid4()
        response = self.client.get(self.get_url(uuid))
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(uuid)
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.AccountFactory.create()
        obj.status = obj.INACTIVE_STATUS
        obj.save()
        request = self.factory.get(self.get_url(obj.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=obj.uuid)
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
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        uuid = uuid4()
        request = self.factory.get(self.get_url(uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=uuid)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
        request = self.factory.get(self.get_url(object.uuid))
        request.user = self.user
        response = self.get_view()(request, uuid=object.uuid)
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
        response = self.client.post(
            self.get_url(object.uuid), {"submit": ""}, follow=True
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.AccountReactivate.success_msg, str(messages[0]))

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

    def test_adds_account_from_one_group(self):
        """Reactivating an account from the app also adds it from one group on AnVIL."""
        object = factories.AccountFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(account=object)
        group = membership.group
        object.status = object.INACTIVE_STATUS
        object.save()
        add_to_group_url = self.get_api_remove_from_group_url(group.name, object.email)
        responses.add(responses.PUT, add_to_group_url, status=204)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        responses.assert_call_count(add_to_group_url, 1)
        # History is not added for the GroupAccountMembership.
        self.assertEqual(models.GroupAccountMembership.history.count(), 1)

    def test_adds_account_to_all_groups(self):
        """Reactivating an account from the app also adds it from all groups that it is in."""
        object = factories.AccountFactory.create()
        memberships = factories.GroupAccountMembershipFactory.create_batch(
            2, account=object
        )
        object.status = object.INACTIVE_STATUS
        object.save()
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        add_to_group_url_1 = self.get_api_remove_from_group_url(
            group_1.name, object.email
        )
        responses.add(responses.PUT, add_to_group_url_1, status=204)
        add_to_group_url_2 = self.get_api_remove_from_group_url(
            group_2.name, object.email
        )
        responses.add(responses.PUT, add_to_group_url_2, status=204)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.uuid), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        # Status was updated.
        object.refresh_from_db()
        self.assertEqual(object.status, object.ACTIVE_STATUS)
        responses.assert_call_count(add_to_group_url_1, 1)
        responses.assert_call_count(add_to_group_url_2, 1)

    def test_api_error_when_adding_account_to_groups(self):
        """Message when an API error occurred when adding a user to a group."""
        object = factories.AccountFactory.create()
        memberships = factories.GroupAccountMembershipFactory.create_batch(
            2, account=object
        )
        object.status = object.INACTIVE_STATUS
        object.save()
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        add_to_group_url_1 = self.get_api_remove_from_group_url(
            group_1.name, object.email
        )
        responses.add(responses.PUT, add_to_group_url_1, status=204)
        add_to_group_url_2 = self.get_api_remove_from_group_url(
            group_2.name, object.email
        )
        responses.add(
            responses.PUT,
            add_to_group_url_2,
            status=409,
            json={"message": "test error"},
        )
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.uuid), {"submit": ""}, follow=True
        )
        self.assertRedirects(response, object.get_absolute_url())
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.AccountReactivate.message_error_adding_to_groups.format("test error"),
            str(messages[0]),
        )
        # The Account is not marked as inactive.
        object.refresh_from_db()
        self.assertEqual(object.status, object.ACTIVE_STATUS)
        # Does not remove the user from any groups.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        models.GroupAccountMembership.objects.get(pk=memberships[0].pk)
        models.GroupAccountMembership.objects.get(pk=memberships[1].pk)
        # The API was called.
        responses.assert_call_count(add_to_group_url_1, 1)
        responses.assert_call_count(add_to_group_url_2, 1)

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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.AccountReactivate.message_already_active, str(messages[0])
        )

    def test_account_already_active_post(self):
        """Redirects with a message if account is already deactivated."""
        object = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create_batch(2, account=object)
        # No API calls are made.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.uuid), {"submit": ""}, follow=True
        )
        self.assertRedirects(response, object.get_absolute_url())
        # The object is unchanged.
        object.refresh_from_db()
        self.assertEqual(object.status, object.ACTIVE_STATUS)
        # Memberships are *not* deleted from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        # A message is shown.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.AccountReactivate.message_already_active, str(messages[0])
        )


class AccountAutocompleteTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with the correct permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_returns_all_objects(self):
        """Queryset returns all objects when there is no query."""
        groups = factories.AccountFactory.create_batch(10)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 10)
        self.assertEqual(sorted(returned_ids), sorted([group.pk for group in groups]))

    def test_returns_correct_object_match(self):
        """Queryset returns the correct objects when query matches the email."""
        account = factories.AccountFactory.create(email="test@foo.com")
        request = self.factory.get(self.get_url(), {"q": "test@foo.com"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], account.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Queryset returns the correct objects when query matches the beginning of the email."""
        account = factories.AccountFactory.create(email="test@foo.com")
        request = self.factory.get(self.get_url(), {"q": "tes"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], account.pk)

    def test_returns_correct_object_containing_query(self):
        """Queryset returns the correct objects when the name contains the query."""
        account = factories.AccountFactory.create(email="test@foo.com")
        request = self.factory.get(self.get_url(), {"q": "foo"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], account.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        account = factories.AccountFactory.create(email="test@foo.com")
        request = self.factory.get(self.get_url(), {"q": "TEST@FOO.COM"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], account.pk)

    def test_does_not_return_inactive_accounts(self):
        """Queryset does not return accounts that are inactive."""
        factories.AccountFactory.create(
            email="test@foo.com", status=models.Account.INACTIVE_STATUS
        )
        request = self.factory.get(self.get_url(), {"q": "test@foo.com"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 0)


class ManagedGroupDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo")
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.ManagedGroupFactory.create()
        request = self.factory.get(self.get_url(obj.name))
        request.user = self.user
        response = self.get_view()(request, slug=obj.name)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
        request = self.factory.get(self.get_url(obj.name))
        request.user = self.user
        response = self.get_view()(request, slug=obj.name)
        self.assertIn("workspace_table", response.context_data)
        self.assertIsInstance(
            response.context_data["workspace_table"], tables.WorkspaceGroupAccessTable
        )

    def test_workspace_table_none(self):
        """No workspaces are shown if the group does not have access to any workspaces."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)

    def test_workspace_table_one(self):
        """One workspace is shown if the group have access to one workspace."""
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupAccessFactory.create(group=group)
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 1)

    def test_workspace_table_two(self):
        """Two workspaces are shown if the group have access to two workspaces."""
        group = factories.ManagedGroupFactory.create()
        factories.WorkspaceGroupAccessFactory.create_batch(2, group=group)
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 2)

    def test_shows_workspace_for_only_this_group(self):
        """Only shows workspcaes that this group has access to."""
        group = factories.ManagedGroupFactory.create(name="group-1")
        other_group = factories.ManagedGroupFactory.create(name="group-2")
        factories.WorkspaceGroupAccessFactory.create(group=other_group)
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)

    def test_active_account_table(self):
        """The active account table exists."""
        obj = factories.ManagedGroupFactory.create()
        request = self.factory.get(self.get_url(obj.name))
        request.user = self.user
        response = self.get_view()(request, slug=obj.name)
        self.assertIn("active_account_table", response.context_data)
        self.assertIsInstance(
            response.context_data["active_account_table"],
            tables.GroupAccountMembershipTable,
        )

    def test_active_account_table_none(self):
        """No accounts are shown if the group has no active accounts."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("active_account_table", response.context_data)
        self.assertEqual(len(response.context_data["active_account_table"].rows), 0)

    def test_active_account_table_one(self):
        """One accounts is shown if the group has only that active account."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group)
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("active_account_table", response.context_data)
        self.assertEqual(len(response.context_data["active_account_table"].rows), 1)

    def test_active_account_table_two(self):
        """Two accounts are shown if the group has only those active accounts."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create_batch(2, group=group)
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("active_account_table", response.context_data)
        self.assertEqual(len(response.context_data["active_account_table"].rows), 2)

    def test_shows_active_account_for_only_this_group(self):
        """Only shows accounts that are in this group."""
        group = factories.ManagedGroupFactory.create(name="group-1")
        other_group = factories.ManagedGroupFactory.create(name="group-2")
        factories.GroupAccountMembershipFactory.create(group=other_group)
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("active_account_table", response.context_data)
        self.assertEqual(len(response.context_data["active_account_table"].rows), 0)

    def test_group_table(self):
        """The group table exists."""
        obj = factories.ManagedGroupFactory.create()
        request = self.factory.get(self.get_url(obj.name))
        request.user = self.user
        response = self.get_view()(request, slug=obj.name)
        self.assertIn("group_table", response.context_data)
        self.assertIsInstance(
            response.context_data["group_table"], tables.GroupGroupMembershipTable
        )

    def test_group_table_none(self):
        """No groups are shown if the group has no member groups."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)

    def test_group_table_one(self):
        """One group is shown if the group has only that member group."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=group)
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 1)

    def test_group_table_two(self):
        """Two groups are shown if the group has only those member groups."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create_batch(2, parent_group=group)
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 2)

    def test_group_account_for_only_this_group(self):
        """Only shows member groups that are in this group."""
        group = factories.ManagedGroupFactory.create(name="group-1")
        other_group = factories.ManagedGroupFactory.create(name="group-2")
        factories.GroupGroupMembershipFactory.create(parent_group=other_group)
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)

    def test_workspace_auth_domain_table(self):
        """The auth_domain table exists."""
        obj = factories.ManagedGroupFactory.create()
        request = self.factory.get(self.get_url(obj.name))
        request.user = self.user
        response = self.get_view()(request, slug=obj.name)
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        self.assertIsInstance(
            response.context_data["workspace_authorization_domain_table"],
            tables.WorkspaceTable,
        )

    def test_workspace_auth_domain_table_none(self):
        """No workspaces are shown if the group is not the auth domain for any workspace."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        self.assertEqual(
            len(response.context_data["workspace_authorization_domain_table"].rows), 0
        )

    def test_workspace_auth_domain_table_one(self):
        """One workspace is shown in if the group is the auth domain for it."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        workspace.authorization_domains.add(group)
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        table = response.context_data["workspace_authorization_domain_table"]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(workspace, table.data)

    def test_workspace_auth_domain_table_two(self):
        """Two workspaces are shown in if the group is the auth domain for them."""
        group = factories.ManagedGroupFactory.create()
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_1.authorization_domains.add(group)
        workspace_2 = factories.WorkspaceFactory.create()
        workspace_2.authorization_domains.add(group)
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
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
        request = self.factory.get(self.get_url(group.name))
        request.user = self.user
        response = self.get_view()(request, slug=group.name)
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        self.assertEqual(
            len(response.context_data["workspace_authorization_domain_table"].rows), 0
        )


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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ManagedGroupCreate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(
            response.context_data["form"], forms.ManagedGroupCreateForm
        )

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        url = self.entry_point + "/api/groups/" + "test-group"
        responses.add(responses.POST, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"})
        self.assertEqual(response.status_code, 302)
        new_object = models.ManagedGroup.objects.latest("pk")
        self.assertIsInstance(new_object, models.ManagedGroup)
        self.assertEqual(new_object.name, "test-group")
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_success_message(self):
        """Response includes a success message if successful."""
        url = self.entry_point + "/api/groups/" + "test-group"
        responses.add(responses.POST, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"}, follow=True)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.ManagedGroupCreate.success_msg, str(messages[0]))

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        url = self.entry_point + "/api/groups/" + "test-group"
        responses.add(responses.POST, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"})
        new_object = models.ManagedGroup.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())
        responses.assert_call_count(url, 1)

    def test_cannot_create_duplicate_object(self):
        """Cannot create two groups with the same name."""
        obj = factories.ManagedGroupFactory.create()
        request = self.factory.post(self.get_url(), {"name": obj.name})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("already exists", form.errors["name"][0])
        self.assertQuerysetEqual(
            models.ManagedGroup.objects.all(),
            models.ManagedGroup.objects.filter(pk=obj.pk),
        )
        self.assertEqual(len(responses.calls), 0)

    def test_cannot_create_duplicate_object_case_insensitive(self):
        """Cannot create two groups with the same name, regardless of case."""
        obj = factories.ManagedGroupFactory.create(name="group")
        request = self.factory.post(self.get_url(), {"name": "GROUP"})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("already exists", form.errors["name"][0])
        self.assertQuerysetEqual(
            models.ManagedGroup.objects.all(),
            models.ManagedGroup.objects.filter(pk=obj.pk),
        )
        self.assertEqual(len(responses.calls), 0)

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        request = self.factory.post(self.get_url(), {"name": ""})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.ManagedGroup.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.ManagedGroup.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_api_error_message(self):
        """Shows a message if an AnVIL API error occurs."""
        url = self.entry_point + "/api/groups/" + "test-group"
        responses.add(
            responses.POST, url, status=500, json={"message": "group create test error"}
        )
        # Need a client to check messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: group create test error", str(messages[0]))
        responses.assert_call_count(url, 1)
        # Make sure that no object is created.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)

    @skip("AnVIL API issue")
    def test_api_group_already_exists(self):
        self.fail(
            "AnVIL API returns 201 instead of ??? when trying to create a group that already exists."
        )


class ManagedGroupListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.ManagedGroupTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.ManagedGroupFactory()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.ManagedGroupFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ManagedGroupDelete.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(1))
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(1)
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.ManagedGroupFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        request.user = self.user
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url(1))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=1)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
        url = self.entry_point + "/api/groups/" + object.name
        responses.add(responses.DELETE, url, status=self.api_success_code)
        responses.add(responses.GET, url, status=404, json={"message": "mock message"})
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.ManagedGroup.objects.count(), 0)
        responses.assert_call_count(url, 2)
        # History is added.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        object = factories.ManagedGroupFactory.create(name="test-group")
        url = self.entry_point + "/api/groups/" + object.name
        responses.add(responses.DELETE, url, status=self.api_success_code)
        responses.add(responses.GET, url, status=404, json={"message": "mock message"})
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.name), {"submit": ""}, follow=True
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.ManagedGroupDelete.success_msg, str(messages[0]))

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.ManagedGroupFactory.create()
        other_object = factories.ManagedGroupFactory.create()
        url = self.entry_point + "/api/groups/" + object.name
        responses.add(responses.DELETE, url, status=self.api_success_code)
        responses.add(responses.GET, url, status=404, json={"message": "mock message"})
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        self.assertQuerysetEqual(
            models.ManagedGroup.objects.all(),
            models.ManagedGroup.objects.filter(pk=other_object.pk),
        )
        responses.assert_call_count(url, 2)

    def test_delete_successful_not_actually_deleted_on_anvil(self):
        """anvil_delete raises exception with successful API response but group was not actually deleted.

        The AnVIL group delete API is buggy and often returns a successful API response when it should return an error.
        """
        object = factories.ManagedGroupFactory.create(name="test-group")
        url = self.entry_point + "/api/groups/" + object.name
        responses.add(responses.DELETE, url, status=self.api_success_code)
        # Group was not actually deleted on AnVIL.
        responses.add(responses.GET, url, status=200)
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.name), {"submit": ""}, follow=True
        )
        self.assertRedirects(response, object.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_could_not_delete_group,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        models.ManagedGroup.objects.get(pk=object.pk)
        responses.assert_call_count(url, 2)

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.ManagedGroupFactory.create()
        url = self.entry_point + "/api/groups/" + object.name
        responses.add(responses.DELETE, url, status=self.api_success_code)
        responses.add(responses.GET, url, status=404, json={"message": "mock message"})
        # Need to use the client instead of RequestFactory to check redirection url.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("anvil_consortium_manager:managed_groups:list")
        )
        responses.assert_call_count(url, 2)

    def test_get_redirect_group_is_a_member_of_another_group(self):
        """Redirect get request when trying to delete a group that is a member of another group.

        This is a behavior enforced by AnVIL."""
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(child.name), follow=True)
        self.assertRedirects(response, child.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
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
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(child.name), follow=True)
        self.assertRedirects(response, child.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_is_auth_domain, str(messages[0])
        )
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_is_auth_domain, str(messages[0])
        )
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)

    def test_get_redirect_group_has_access_to_workspace(self):
        """Redirect get request when trying to delete a group that has access to a workspace.

        This is a behavior enforced by AnVIL."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        access = factories.WorkspaceGroupAccessFactory.create(
            workspace=workspace, group=group
        )
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_has_access_to_workspace,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        models.ManagedGroup.objects.get(pk=group.pk)
        # Make sure the relationships still exists.
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 1)
        models.WorkspaceGroupAccess.objects.get(pk=access.pk)

    def test_post_redirect_group_has_access_to_workspace(self):
        """Redirect post request when trying to delete a group that has access to a workspace.

        This is a behavior enforced by AnVIL."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        access = factories.WorkspaceGroupAccessFactory.create(
            workspace=workspace, group=group
        )
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(group.name), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_has_access_to_workspace,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        models.ManagedGroup.objects.get(pk=group.pk)
        # Make sure the relationships still exists.
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 1)
        models.WorkspaceGroupAccess.objects.get(pk=access.pk)

    def test_can_delete_group_that_has_child_groups(self):
        """Can delete a group that has other groups as members."""
        parent = factories.ManagedGroupFactory.create()
        child = factories.ManagedGroupFactory.create()
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        url = self.entry_point + "/api/groups/" + parent.name
        responses.add(responses.DELETE, url, status=self.api_success_code)
        responses.add(responses.GET, url, status=404, json={"message": "mock message"})
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
        responses.assert_call_count(url, 2)
        # History is added for the GroupGroupMembership.
        self.assertEqual(models.GroupGroupMembership.history.count(), 2)
        self.assertEqual(models.GroupGroupMembership.history.latest().history_type, "-")

    def test_can_delete_group_if_it_has_account_members(self):
        """Can delete a group that has other groups as members."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group, account=account)
        url = self.entry_point + "/api/groups/" + group.name
        responses.add(responses.DELETE, url, status=self.api_success_code)
        responses.add(responses.GET, url, status=404, json={"message": "mock message"})
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(group.name), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        # The group was deleted.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)
        # Thee membership was deleted.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)
        # The account still exists.
        models.Account.objects.get(pk=account.pk)
        responses.assert_call_count(url, 2)
        # History is added for GroupAccountMemberships.
        self.assertEqual(models.GroupAccountMembership.history.count(), 2)
        self.assertEqual(
            models.GroupAccountMembership.history.latest().history_type, "-"
        )

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.ManagedGroupFactory.create()
        url = self.entry_point + "/api/groups/" + object.name
        responses.add(
            responses.DELETE,
            url,
            status=500,
            json={"message": "group delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(object.name), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: group delete test error", str(messages[0]))
        responses.assert_call_count(url, 1)
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_not_managed_by_app, str(messages[0])
        )
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.ManagedGroupDelete.message_not_managed_by_app, str(messages[0])
        )
        # Make sure that the object still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)

    @skip("AnVIL API issue - covered by model fields")
    def test_api_not_admin_of_group(self):
        self.fail(
            "AnVIL API returns 204 instead of 403 when trying to delete a group you are not an admin of."
        )

    @skip("AnVIL API issue - covered by model fields")
    def test_api_group_does_not_exist(self):
        self.fail(
            "AnVIL API returns 204 instead of 404 when trying to delete a group that doesn't exist."
        )


class ManagedGroupAutocompleteTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with the correct permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:managed_groups:autocomplete", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.ManagedGroupAutocomplete.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_returns_all_objects(self):
        """Queryset returns all objects when there is no query."""
        groups = factories.ManagedGroupFactory.create_batch(10)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 10)
        self.assertEqual(sorted(returned_ids), sorted([group.pk for group in groups]))

    def test_returns_correct_object_match(self):
        """Queryset returns the correct objects when query matches the name."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        request = self.factory.get(self.get_url(), {"q": "test-group"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], group.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        request = self.factory.get(self.get_url(), {"q": "test"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], group.pk)

    def test_returns_correct_object_containing_query(self):
        """Queryset returns the correct objects when the name contains the query."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        request = self.factory.get(self.get_url(), {"q": "grou"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], group.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        group = factories.ManagedGroupFactory.create(name="TEST-GROUP")
        request = self.factory.get(self.get_url(), {"q": "test"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], group.pk)

    def test_does_not_return_groups_not_managed_by_app(self):
        """Queryset does not return groups that are not managed by the app."""
        factories.ManagedGroupFactory.create(name="test-group", is_managed_by_app=False)
        request = self.factory.get(self.get_url(), {"q": "test-group"})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(json.loads(response.content.decode("utf-8"))["results"], [])


class WorkspaceDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        url = reverse(
            "anvil_consortium_manager:workspaces:detail", args=["foo1", "foo2"]
        )
        response = self.client.get(url)
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + url)

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.get(obj.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=obj.billing_project.name,
            workspace_slug=obj.name,
        )
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        url = reverse(
            "anvil_consortium_manager:workspaces:detail", args=["foo1", "foo2"]
        )
        request = self.factory.get(url)
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.get(obj.get_absolute_url())
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, billing_project_slug="foo1", workspace_slug="foo2")

    def test_group_access_table(self):
        """The workspace group access table exists."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.get(obj.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=obj.billing_project.name,
            workspace_slug=obj.name,
        )
        self.assertIn("group_access_table", response.context_data)
        self.assertIsInstance(
            response.context_data["group_access_table"],
            tables.WorkspaceGroupAccessTable,
        )

    def test_group_access_table_none(self):
        """No groups are shown if the workspace has not been shared with any groups."""
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.get(workspace.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=workspace.billing_project.name,
            workspace_slug=workspace.name,
        )
        self.assertIn("group_access_table", response.context_data)
        self.assertEqual(len(response.context_data["group_access_table"].rows), 0)

    def test_group_access_table_one(self):
        """One group is shown if the workspace has been shared with one group."""
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceGroupAccessFactory.create(workspace=workspace)
        request = self.factory.get(workspace.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=workspace.billing_project.name,
            workspace_slug=workspace.name,
        )
        self.assertIn("group_access_table", response.context_data)
        self.assertEqual(len(response.context_data["group_access_table"].rows), 1)

    def test_group_access_table_two(self):
        """Two groups are shown if the workspace has been shared with two groups."""
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceGroupAccessFactory.create_batch(2, workspace=workspace)
        request = self.factory.get(workspace.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=workspace.billing_project.name,
            workspace_slug=workspace.name,
        )
        self.assertIn("group_access_table", response.context_data)
        self.assertEqual(len(response.context_data["group_access_table"].rows), 2)

    def test_shows_workspace_group_access_for_only_that_workspace(self):
        """Only shows groups that this workspace has been shared with."""
        workspace = factories.WorkspaceFactory.create(name="workspace-1")
        other_workspace = factories.WorkspaceFactory.create(name="workspace-2")
        factories.WorkspaceGroupAccessFactory.create(workspace=other_workspace)
        request = self.factory.get(workspace.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=workspace.billing_project.name,
            workspace_slug=workspace.name,
        )
        self.assertIn("group_access_table", response.context_data)
        self.assertEqual(len(response.context_data["group_access_table"].rows), 0)

    def test_auth_domain_table(self):
        """The workspace auth domain table exists."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.get(obj.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=obj.billing_project.name,
            workspace_slug=obj.name,
        )
        self.assertIn("authorization_domain_table", response.context_data)
        self.assertIsInstance(
            response.context_data["authorization_domain_table"],
            tables.ManagedGroupTable,
        )

    def test_auth_domain_table_none(self):
        """No groups are shown if the workspace has no auth domains."""
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.get(workspace.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=workspace.billing_project.name,
            workspace_slug=workspace.name,
        )
        self.assertIn("authorization_domain_table", response.context_data)
        self.assertEqual(
            len(response.context_data["authorization_domain_table"].rows), 0
        )

    def test_auth_domain_table_one(self):
        """One group is shown if the workspace has one auth domain."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(group)
        request = self.factory.get(workspace.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=workspace.billing_project.name,
            workspace_slug=workspace.name,
        )
        self.assertIn("authorization_domain_table", response.context_data)
        table = response.context_data["authorization_domain_table"]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(group, table.data)

    def test_auth_domain_table_two(self):
        """Two groups are shown if the workspace has two auth domains."""
        workspace = factories.WorkspaceFactory.create()
        group_1 = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(group_1)
        group_2 = factories.ManagedGroupFactory.create()
        workspace.authorization_domains.add(group_2)
        request = self.factory.get(workspace.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=workspace.billing_project.name,
            workspace_slug=workspace.name,
        )
        self.assertIn("authorization_domain_table", response.context_data)
        table = response.context_data["authorization_domain_table"]
        self.assertEqual(len(table.rows), 2)
        self.assertIn(group_1, table.data)
        self.assertIn(group_2, table.data)

    def test_shows_auth_domains_for_only_that_workspace(self):
        """Only shows auth domains for this workspace."""
        workspace = factories.WorkspaceFactory.create(name="workspace-1")
        other_workspace = factories.WorkspaceFactory.create(name="workspace-2")
        group = factories.ManagedGroupFactory.create()
        other_workspace.authorization_domains.add(group)
        request = self.factory.get(workspace.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=workspace.billing_project.name,
            workspace_slug=workspace.name,
        )
        self.assertIn("authorization_domain_table", response.context_data)
        self.assertEqual(
            len(response.context_data["authorization_domain_table"].rows), 0
        )


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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )
        self.workspace_type = DefaultWorkspaceAdapter.type

    def tearDown(self):
        # Clean up the workspace adapter registry if the test adapter was added.
        try:
            workspace_adapter_registry.unregister(TestWorkspaceAdapter)
        except AdapterNotRegisteredError:
            pass
        # Register the default adapter in case it has been unregistered.
        try:
            workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        except AdapterAlreadyRegisteredError:
            pass
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
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url(self.workspace_type),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, workspace_type=self.workspace_type)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, workspace_type=self.workspace_type)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceCreateForm)

    def test_has_formset_in_context(self):
        """Response includes a formset for the workspace_data model."""
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertTrue("workspace_data_formset" in response.context_data)
        formset = response.context_data["workspace_data_formset"]
        self.assertIsInstance(formset, BaseInlineFormSet)
        self.assertEqual(len(formset.forms), 1)
        self.assertIsInstance(formset.forms[0], forms.DefaultWorkspaceDataForm)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        responses.add(
            responses.POST,
            url,
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
            new_object.workspace_data_type,
            DefaultWorkspaceAdapter().get_type(),
        )
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_creates_default_workspace_data(self):
        """Posting valid data to the form creates the default workspace data object."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        responses.add(
            responses.POST,
            url,
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
        self.assertIsInstance(
            new_workspace.defaultworkspacedata, models.DefaultWorkspaceData
        )

    def test_success_message(self):
        """Response includes a success message if successful."""
        billing_project = factories.BillingProjectFactory.create()
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": billing_project.name,
            "name": "test-workspace",
            "attributes": {},
        }
        responses.add(
            responses.POST,
            url,
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceCreate.success_msg, str(messages[0]))

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        billing_project = factories.BillingProjectFactory.create()
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": billing_project.name,
            "name": "test-workspace",
            "attributes": {},
        }
        responses.add(
            responses.POST,
            url,
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
        responses.assert_call_count(url, 1)

    def test_cannot_create_duplicate_object(self):
        """Cannot create two workspaces with the same billing project and name."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.post(
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
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.Workspace.objects.all(),
            models.Workspace.objects.filter(pk=obj.pk),
        )

    def test_can_create_workspace_with_same_billing_project_different_name(self):
        """Can create a workspace with a different name in the same billing project."""
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(
            billing_project=billing_project, name="test-name-1"
        )
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": billing_project.name,
            "name": "test-name-2",
            "attributes": {},
        }
        responses.add(
            responses.POST,
            url,
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
        models.Workspace.objects.get(
            billing_project=billing_project, name="test-name-2"
        )
        responses.assert_call_count(url, 1)

    def test_can_create_workspace_with_same_name_different_billing_project(self):
        """Can create a workspace with the same name in a different billing project."""
        billing_project_1 = factories.BillingProjectFactory.create(name="project-1")
        billing_project_2 = factories.BillingProjectFactory.create(name="project-2")
        workspace_name = "test-name"
        factories.WorkspaceFactory.create(
            billing_project=billing_project_1, name=workspace_name
        )
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": billing_project_2.name,
            "name": "test-name",
            "attributes": {},
        }
        responses.add(
            responses.POST,
            url,
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
        models.Workspace.objects.get(
            billing_project=billing_project_2, name=workspace_name
        )
        responses.assert_call_count(url, 1)

    def test_invalid_input_name(self):
        """Posting invalid data to name field does not create an object."""
        billing_project = factories.BillingProjectFactory.create()
        request = self.factory.post(
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
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("slug", form.errors["name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_invalid_input_billing_project(self):
        """Posting invalid data to billing_project field does not create an object."""
        request = self.factory.post(
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
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("valid choice", form.errors["billing_project"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_post_invalid_name_billing_project(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(self.workspace_type), {})
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
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
        request = self.factory.post(self.get_url(self.workspace_type), {})
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
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
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": billing_project.name,
            "name": "test-workspace",
            "attributes": {},
        }
        responses.add(
            responses.POST,
            url,
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error: workspace create test error", str(messages[0]))
        responses.assert_call_count(url, 1)
        # Make sure that no object is created.
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_can_create_a_workspace_with_one_authorization_domain(self):
        """Can create a workspace with one authorization domain."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        auth_domain = factories.ManagedGroupFactory.create()
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [{"membersGroupName": auth_domain.name}],
        }
        responses.add(
            responses.POST,
            url,
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
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")
        # History is added for the authorization domain.
        self.assertEqual(models.WorkspaceAuthorizationDomain.history.count(), 1)
        self.assertEqual(
            models.WorkspaceAuthorizationDomain.history.latest().history_type, "+"
        )

    def test_create_workspace_with_two_auth_domains(self):
        """Can create a workspace with two authorization domains."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        auth_domain_1 = factories.ManagedGroupFactory.create(name="auth1")
        auth_domain_2 = factories.ManagedGroupFactory.create(name="auth2")
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [
                {"membersGroupName": auth_domain_1.name},
                {"membersGroupName": auth_domain_2.name},
            ],
        }
        responses.add(
            responses.POST,
            url,
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
        responses.assert_call_count(url, 1)

    def test_invalid_auth_domain(self):
        """Does not create a workspace when an invalid authorization domain is specified."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        url = self.entry_point + "/api/workspaces"
        request = self.factory.post(
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
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("authorization_domains", form.errors.keys())
        self.assertIn("valid choice", form.errors["authorization_domains"][0])
        # No object was created.
        self.assertEqual(len(models.Workspace.objects.all()), 0)
        # No API calls made.
        responses.assert_call_count(url, 0)

    def test_one_valid_one_invalid_auth_domain(self):
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        auth_domain = factories.ManagedGroupFactory.create()
        url = self.entry_point + "/api/workspaces"
        request = self.factory.post(
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
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("authorization_domains", form.errors.keys())
        self.assertIn("valid choice", form.errors["authorization_domains"][0])
        # No object was created.
        self.assertEqual(len(models.Workspace.objects.all()), 0)
        # No API calls made.
        responses.assert_call_count(url, 0)

    def test_auth_domain_does_not_exist_on_anvil(self):
        """No workspace is displayed if the auth domain group doesn't exist on AnVIL."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        auth_domain = factories.ManagedGroupFactory.create()
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [
                {"membersGroupName": auth_domain.name},
            ],
        }
        responses.add(
            responses.POST,
            url,
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: api error", str(messages[0]))
        # Did not create any new Workspaces.
        self.assertEqual(models.Workspace.objects.count(), 0)
        responses.assert_call_count(url, 1)

    def test_not_admin_of_auth_domain_on_anvil(self):
        """No workspace is displayed if we are not the admins of the auth domain on AnVIL."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        auth_domain = factories.ManagedGroupFactory.create()
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
            "authorizationDomain": [
                {"membersGroupName": auth_domain.name},
            ],
        }
        responses.add(
            responses.POST,
            url,
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: api error", str(messages[0]))
        # Did not create any new Workspaces.
        self.assertEqual(models.Workspace.objects.count(), 0)
        responses.assert_call_count(url, 1)

    def test_not_user_of_billing_project(self):
        """Posting a billing project where we are not users does not create an object."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project", has_app_as_user=False
        )
        request = self.factory.post(
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
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("valid choice", form.errors["billing_project"][0])
        # No workspace was created.
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_adapter_includes_workspace_data_formset(self):
        """Response includes the workspace data formset if specified."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = "test"
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
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
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        responses.add(
            responses.POST,
            url,
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
        # workspace_data_type is set properly.
        self.assertEqual(
            new_workspace.workspace_data_type,
            TestWorkspaceAdapter().get_type(),
        )
        # Workspace data is added.
        self.assertEqual(app_models.TestWorkspaceData.objects.count(), 1)
        new_workspace_data = app_models.TestWorkspaceData.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.study_name, "test study")
        responses.assert_call_count(url, 1)

    def test_adapter_does_not_create_objects_if_workspace_data_form_invalid(self):
        """Posting invalid data to the workspace_data_form form does not create a workspace when using an adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = "test"
        billing_project = factories.BillingProjectFactory.create()
        url = self.entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        responses.add(
            responses.POST,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        request = self.factory.post(
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
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )
        self.workspace_type = DefaultWorkspaceAdapter().get_type()

    def tearDown(self):
        # Clean up the workspace adapter registry if the test adapter was added.
        try:
            workspace_adapter_registry.unregister(TestWorkspaceAdapter)
        except AdapterNotRegisteredError:
            pass
        # Register the default adapter in case it has been unregistered.
        try:
            workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        except AdapterAlreadyRegisteredError:
            pass
        super().tearDown()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:import", args=args)

    def get_api_url(self, billing_project_name, workspace_name):
        return (
            self.entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
        )

    def get_api_json_response(
        self, billing_project, workspace, authorization_domains=[], access="OWNER"
    ):
        """Return a pared down version of the json response from the AnVIL API with only fields we need."""
        json_data = {
            "accessLevel": access,
            "owners": [],
            "workspace": {
                "authorizationDomain": [
                    {"membersGroupName": x} for x in authorization_domains
                ],
                "name": workspace,
                "namespace": billing_project,
            },
        }
        return json_data

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceImport.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url(self.workspace_type),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceImportForm)

    def test_has_formset_in_context(self):
        """Response includes a formset for the workspace_data model."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertTrue("workspace_data_formset" in response.context_data)
        formset = response.context_data["workspace_data_formset"]
        self.assertIsInstance(formset, BaseInlineFormSet)
        self.assertEqual(len(formset.forms), 1)
        self.assertIsInstance(formset.forms[0], forms.DefaultWorkspaceDataForm)

    def test_form_choices_no_available_workspaces(self):
        """Choices are populated correctly with one available workspace."""
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceImport.message_no_available_workspaces, str(messages[0])
        )

    def test_form_choices_one_available_workspace(self):
        """Choices are populated correctly with one available workspace."""
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response("bp-1", "ws-1")],
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        # Choices are populated correctly.
        workspace_choices = response.context_data["form"].fields["workspace"].choices
        self.assertEqual(len(workspace_choices), 2)
        # The first choice is the empty string.
        self.assertEqual("", workspace_choices[0][0])
        # Second choice is the workspace.
        self.assertTrue(("bp-1/ws-1", "bp-1/ws-1") in workspace_choices)

    def test_form_choices_two_available_workspaces(self):
        """Choices are populated correctly with two available workspaces."""
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[
                self.get_api_json_response("bp-1", "ws-1"),
                self.get_api_json_response("bp-2", "ws-2"),
            ],
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        # Choices are populated correctly.
        workspace_choices = response.context_data["form"].fields["workspace"].choices
        self.assertEqual(len(workspace_choices), 3)
        # The first choice is the empty string.
        self.assertEqual("", workspace_choices[0][0])
        # The next choices are the workspaces.
        self.assertTrue(("bp-1/ws-1", "bp-1/ws-1") in workspace_choices)
        self.assertTrue(("bp-2/ws-2", "bp-2/ws-2") in workspace_choices)

    def test_form_does_not_show_already_imported_workspaces(self):
        """The form does not show workspaces that have already been imported in the choices."""
        billing_project = factories.BillingProjectFactory.create(name="bp")
        factories.WorkspaceFactory.create(
            billing_project=billing_project, name="ws-imported"
        )
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceImport.message_no_available_workspaces, str(messages[0])
        )

    def test_form_does_not_show_workspaces_not_owner(self):
        """The form does not show workspaces where we aren't owners in the choices."""
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[
                self.get_api_json_response("bp", "ws-owner", access="OWNER"),
                self.get_api_json_response("bp", "ws-reader", access="READER"),
            ],
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
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
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        # Billing project API call.
        billing_project_url = (
            self.entry_point + "/api/billing/v2/" + billing_project_name
        )
        responses.add(responses.GET, billing_project_url, status=200)
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
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
            new_workspace.workspace_data_type,
            DefaultWorkspaceAdapter().get_type(),
        )
        responses.assert_call_count(billing_project_url, 1)
        responses.assert_call_count(url, 1)
        # History is added for the workspace.
        self.assertEqual(new_workspace.history.count(), 1)
        self.assertEqual(new_workspace.history.latest().history_type, "+")
        # History is added for the BillingProject.
        self.assertEqual(new_billing_project.history.count(), 1)
        self.assertEqual(new_billing_project.history.latest().history_type, "+")

    def test_creates_default_workspace_data_without_custom_adapter(self):
        """The default workspace data object is created if no custom aadpter is used."""
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        # Billing project API call.
        billing_project_url = (
            self.entry_point + "/api/billing/v2/" + billing_project_name
        )
        responses.add(responses.GET, billing_project_url, status=200)
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
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
        new_workspace = models.Workspace.objects.latest("pk")
        # Also creates a workspace data object.
        self.assertEqual(models.DefaultWorkspaceData.objects.count(), 1)
        self.assertIsInstance(
            new_workspace.defaultworkspacedata, models.DefaultWorkspaceData
        )

    def test_success_message(self):
        """Can import a workspace from AnVIL when the billing project does not exist in Django and we are users."""
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        # Billing project API call.
        billing_project_url = (
            self.entry_point + "/api/billing/v2/" + billing_project_name
        )
        responses.add(responses.GET, billing_project_url, status=200)
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
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
            follow=True,
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceImport.success_msg, str(messages[0]))

    def test_can_import_workspace_and_billing_project_as_not_user(self):
        """Can import a workspace from AnVIL when the billing project does not exist in Django and we are not users."""
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        # Billing project API call.
        billing_project_url = (
            self.entry_point + "/api/billing/v2/" + billing_project_name
        )
        responses.add(
            responses.GET, billing_project_url, status=404, json={"message": "other"}
        )
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
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
        responses.assert_call_count(billing_project_url, 1)
        responses.assert_call_count(url, 1)
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
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
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
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a workspace.
        self.assertEqual(models.Workspace.objects.count(), 1)
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        responses.assert_call_count(url, 1)
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
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            # Assume that this is the only workspace we can see on AnVIL.
            json=[workspace_json],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=workspace_json,
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
        responses.assert_call_count(url, 1)
        # History is added for the workspace.
        self.assertEqual(new_workspace.history.count(), 1)
        self.assertEqual(new_workspace.history.latest().history_type, "+")
        # History is added for the authorization domain.
        self.assertEqual(models.WorkspaceAuthorizationDomain.history.count(), 1)
        self.assertEqual(
            models.WorkspaceAuthorizationDomain.history.latest().history_type, "+"
        )

    def test_can_import_workspace_with_auth_domain_not_in_app(self):
        """Can import a workspace with an auth domain that is not already in the app."""
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        auth_domain_name = "auth-group"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
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
        responses.add(
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
        group_url = self.entry_point + "/api/groups"
        responses.add(
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
        responses.assert_call_count(url, 1)
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
        self.assertEqual(
            models.WorkspaceAuthorizationDomain.history.latest().history_type, "+"
        )

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        billing_project = factories.BillingProjectFactory.create(name="billing-project")
        workspace_name = "workspace"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
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
            },
        )
        new_object = models.Workspace.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())
        responses.assert_call_count(url, 1)

    def test_workspace_already_imported(self):
        """Does not import a workspace that already exists in Django."""
        workspace = factories.WorkspaceFactory.create()
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[
                self.get_api_json_response(
                    workspace.billing_project.name, workspace.name
                )
            ],
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
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response("foo", "bar")],
        )
        # No API call.
        request = self.factory.post(
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
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
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
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response("foo", "bar")],
        )
        request = self.factory.post(
            self.get_url(self.workspace_type),
            {
                # Default workspace data for formset.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
            },
        )
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 1)  # just the workspace list.

    def test_other_anvil_api_error(self):
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: an error", str(messages[0]))
        # Did not create any objects.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        self.assertEqual(models.Workspace.objects.count(), 0)
        responses.assert_call_count(url, 1)

    def test_anvil_api_error_workspace_list_get(self):
        # Available workspaces API call.
        responses.add(
            responses.GET,
            self.entry_point + "/api/workspaces",
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=500,
            json={"message": "an error"},
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        # Check messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceImport.message_error_fetching_workspaces, str(messages[0])
        )
        # Did not create any objects.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_anvil_api_error_workspace_list_post(self):
        # Available workspaces API call.
        responses.add(
            responses.GET,
            self.entry_point + "/api/workspaces",
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceImport.message_error_fetching_workspaces, str(messages[0])
        )
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
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
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
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
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
            new_workspace.workspace_data_type,
            TestWorkspaceAdapter().get_type(),
        )
        # Workspace data is added.
        self.assertEqual(app_models.TestWorkspaceData.objects.count(), 1)
        new_workspace_data = app_models.TestWorkspaceData.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.study_name, "test study")
        responses.assert_call_count(url, 1)

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
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        request = self.factory.post(
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

        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
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
        self.assertEqual(len(responses.calls), 2)


class WorkspaceListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.workspace_type = DefaultWorkspaceAdapter().get_type()

    def tearDown(self):
        # Clean up the workspace adapter registry if the test adapter was added.
        try:
            workspace_adapter_registry.unregister(TestWorkspaceAdapter)
        except AdapterNotRegisteredError:
            pass
        # Register the default adapter in case it has been unregistered.
        try:
            workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        except AdapterAlreadyRegisteredError:
            pass
        super().tearDown()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url(self.workspace_type),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, workspace_type=self.workspace_type)

    def test_view_status_code_client(self):
        factories.WorkspaceFactory()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.WorkspaceTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.WorkspaceFactory()
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.WorkspaceFactory.create_batch(2)
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_adapter(self):
        """Displays the correct table if specified in the adapter."""
        # Overriding settings doesn't work, because appconfig.ready has already run and
        # registered the default adapter. Instead, unregister the default and register the
        # new adapter here.
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        self.workspace_type = TestWorkspaceAdapter().get_type()
        request = self.factory.get(self.get_url(self.workspace_type))
        request.user = self.user
        response = self.get_view()(request, workspace_type=self.workspace_type)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], app_tables.TestWorkspaceDataTable
        )

    def test_only_shows_workspaces_with_correct_type(self):
        """Only workspaces with the same workspace_type are shown in the table."""
        factories.WorkspaceFactory(workspace_data_type="test")
        request = self.factory.get(self.get_url("default"))
        request.user = self.user
        response = self.get_view()(request, workspace_type="default")
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)


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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:delete", args=args)

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
        request = self.factory.get(self.get_url(obj.billing_project.name, obj.name))
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=obj.billing_project.name,
            workspace_slug=obj.name,
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url("foo1", "foo2"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=1)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        object = factories.WorkspaceFactory.create(
            billing_project=billing_project, name="test-workspace"
        )
        url = self.entry_point + "/api/workspaces/test-billing-project/test-workspace"
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.billing_project.name, object.name), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 0)
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        object = factories.WorkspaceFactory.create(
            billing_project=billing_project, name="test-workspace"
        )
        url = self.entry_point + "/api/workspaces/test-billing-project/test-workspace"
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.billing_project.name, object.name),
            {"submit": ""},
            follow=True,
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceDelete.success_msg, str(messages[0]))

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.WorkspaceFactory.create()
        other_object = factories.WorkspaceFactory.create()
        url = (
            self.entry_point
            + "/api/workspaces/"
            + object.billing_project.name
            + "/"
            + object.name
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.billing_project.name, object.name), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertQuerysetEqual(
            models.Workspace.objects.all(),
            models.Workspace.objects.filter(pk=other_object.pk),
        )
        responses.assert_call_count(url, 1)

    def test_can_delete_workspace_with_auth_domain(self):
        """A workspace can be deleted if it has an auth domain, and the auth domain group is not deleted."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        object = factories.WorkspaceFactory.create(
            billing_project=billing_project, name="test-workspace"
        )
        auth_domain = factories.ManagedGroupFactory.create(name="test-group")
        wad = models.WorkspaceAuthorizationDomain.objects.create(
            workspace=object, group=auth_domain
        )
        # object.authorization_domains.add(auth_domain)
        url = self.entry_point + "/api/workspaces/test-billing-project/test-workspace"
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.billing_project.name, object.name), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.WorkspaceAuthorizationDomain.objects.count(), 0)
        # The auth domain group still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        models.ManagedGroup.objects.get(pk=auth_domain.pk)
        responses.assert_call_count(url, 1)
        # History is added for workspace.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "-")
        # History is added for auth domain.
        self.assertEqual(wad.history.count(), 2)
        self.assertEqual(wad.history.latest().history_type, "-")

    def test_can_delete_workspace_that_has_been_shared_with_group(self):
        """A workspace can be deleted if it has been shared with a group, and the group is not deleted."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        object = factories.WorkspaceFactory.create(
            billing_project=billing_project, name="test-workspace"
        )
        group = factories.ManagedGroupFactory.create(name="test-group")
        factories.WorkspaceGroupAccessFactory.create(workspace=object, group=group)
        url = self.entry_point + "/api/workspaces/test-billing-project/test-workspace"
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.billing_project.name, object.name), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)
        # The group still exists.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        models.ManagedGroup.objects.get(pk=group.pk)
        responses.assert_call_count(url, 1)
        # History is added for workspace.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "-")
        # History is added for WorkspaceGroupAccess.
        self.assertEqual(models.WorkspaceGroupAccess.history.count(), 2)
        self.assertEqual(models.WorkspaceGroupAccess.history.latest().history_type, "-")

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.WorkspaceFactory.create()
        # Need to use the client instead of RequestFactory to check redirection url.
        url = (
            self.entry_point
            + "/api/workspaces/"
            + object.billing_project.name
            + "/"
            + object.name
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.billing_project.name, object.name), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:list",
                args=[DefaultWorkspaceAdapter().get_type()],
            ),
        )
        responses.assert_call_count(url, 1)

    def test_adapter_success_url(self):
        """Redirects to the expected page."""
        # Register a new adapter.
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        object = factories.WorkspaceFactory.create(
            workspace_data_type=TestWorkspaceAdapter().get_type()
        )
        # Need to use the client instead of RequestFactory to check redirection url.
        url = (
            self.entry_point
            + "/api/workspaces/"
            + object.billing_project.name
            + "/"
            + object.name
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.billing_project.name, object.name), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse(
                "anvil_consortium_manager:workspaces:list",
                args=[TestWorkspaceAdapter().get_type()],
            ),
        )
        responses.assert_call_count(url, 1)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.WorkspaceFactory.create()
        url = (
            self.entry_point
            + "/api/workspaces/"
            + object.billing_project.name
            + "/"
            + object.name
        )
        responses.add(
            responses.DELETE,
            url,
            status=500,
            json={"message": "workspace delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.billing_project.name, object.name), {"submit": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error: workspace delete test error", str(messages[0]))
        responses.assert_call_count(url, 1)
        # Make sure that the object still exists.
        self.assertEqual(models.Workspace.objects.count(), 1)


class WorkspaceAutocompleteTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with the correct permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_returns_all_objects(self):
        """Queryset returns all objects when there is no query."""
        groups = factories.WorkspaceFactory.create_batch(10)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 10)
        self.assertEqual(sorted(returned_ids), sorted([group.pk for group in groups]))

    def test_returns_correct_object_match(self):
        """Queryset returns the correct objects when query matches the name."""
        workspace = factories.WorkspaceFactory.create(name="test-workspace")
        request = self.factory.get(self.get_url(), {"q": "test-workspace"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        workspace = factories.WorkspaceFactory.create(name="test-workspace")
        request = self.factory.get(self.get_url(), {"q": "test"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_containing_query(self):
        """Queryset returns the correct objects when the name contains the query."""
        workspace = factories.WorkspaceFactory.create(name="test-workspace")
        request = self.factory.get(self.get_url(), {"q": "work"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        workspace = factories.WorkspaceFactory.create(name="test-workspace")
        request = self.factory.get(self.get_url(), {"q": "TEST-WORKSPACE"})
        request.user = self.user
        response = self.get_view()(request)
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)


class GroupGroupMembershipDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:managed_groups:member_groups:detail", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("parent", "child"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url("parent", "child"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.GroupGroupMembershipFactory.create()
        request = self.factory.get(self.get_url("parent", "child"))
        request.user = self.user
        response = self.get_view()(
            request,
            parent_group_slug=obj.parent_group.name,
            child_group_slug=obj.child_group.name,
        )
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url("parent", "child"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request, parent_group_slug="parent", child_group_slug="child"
            )

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        factories.GroupGroupMembershipFactory.create()
        request = self.factory.get(self.get_url("parent", "child"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request, parent_group_slug="parent", child_group_slug="child"
            )


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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:group_group_membership:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipCreate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(
            response.context_data["form"], forms.GroupGroupMembershipForm
        )

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        parent_group = factories.ManagedGroupFactory.create(name="group-1")
        child_group = factories.ManagedGroupFactory.create(name="group-2")
        url = (
            self.entry_point
            + "/api/groups/"
            + parent_group.name
            + "/MEMBER/"
            + child_group.get_email()
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
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
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_success_message(self):
        """Response includes a success message if successful."""
        parent_group = factories.ManagedGroupFactory.create(name="group-1")
        child_group = factories.ManagedGroupFactory.create(name="group-2")
        url = (
            self.entry_point
            + "/api/groups/"
            + parent_group.name
            + "/MEMBER/"
            + child_group.get_email()
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupGroupMembershipCreate.success_msg, str(messages[0]))

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        parent_group = factories.ManagedGroupFactory.create(name="group-1")
        child_group = factories.ManagedGroupFactory.create(name="group-2")
        url = (
            self.entry_point
            + "/api/groups/"
            + parent_group.name
            + "/ADMIN/"
            + child_group.get_email()
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
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
        responses.assert_call_count(url, 1)

    def test_redirects_to_list(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        parent_group = factories.ManagedGroupFactory.create(name="group-1")
        child_group = factories.ManagedGroupFactory.create(name="group-2")
        url = (
            self.entry_point
            + "/api/groups/"
            + parent_group.name
            + "/ADMIN/"
            + child_group.get_email()
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        self.assertRedirects(
            response, reverse("anvil_consortium_manager:group_group_membership:list")
        )
        responses.assert_call_count(url, 1)

    def test_cannot_create_duplicate_object_with_same_role(self):
        """Cannot create a second GroupGroupMembership object for the same parent and child with the same role."""
        obj = factories.GroupGroupMembershipFactory.create(
            role=models.GroupGroupMembership.MEMBER
        )
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": obj.parent_group.pk,
                "child_group": obj.child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.GroupGroupMembership.objects.all(),
            models.GroupGroupMembership.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_with_different_role(self):
        """Cannot create a second GroupGroupMembership object for the same parent and child with a different role."""
        obj = factories.GroupGroupMembershipFactory.create(
            role=models.GroupGroupMembership.MEMBER
        )
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": obj.parent_group.pk,
                "child_group": obj.child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
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
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=group_1
        )
        url = (
            self.entry_point
            + "/api/groups/"
            + parent.name
            + "/MEMBER/"
            + group_2.get_email()
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
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
        responses.assert_call_count(url, 1)

    def test_can_add_a_child_group_to_two_parents(self):
        group_1 = factories.ManagedGroupFactory.create(name="test-group-1")
        group_2 = factories.ManagedGroupFactory.create(name="test-group-2")
        child = factories.ManagedGroupFactory.create(name="child_1-group")
        factories.GroupGroupMembershipFactory.create(
            parent_group=group_1, child_group=child
        )
        url = (
            self.entry_point
            + "/api/groups/"
            + group_2.name
            + "/MEMBER/"
            + child.get_email()
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
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
        responses.assert_call_count(url, 1)

    def test_invalid_input_child(self):
        """Posting invalid data to child_group field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": group.pk,
                "child_group": group.pk + 1,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("valid choice", form.errors["child_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_invalid_input_parent(self):
        """Posting invalid data to parent group field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": group.pk + 1,
                "child_group": group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
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
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": "foo",
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("valid choice", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        request.user = self.user
        response = self.get_view()(request)
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
        request = self.factory.post(
            self.get_url(),
            {"child_group": child_group.pk, "role": "foo"},
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("required", form.errors["parent_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_child_group(self):
        """Posting blank data to the child_group field does not create an object."""
        parent_group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"parent_group": parent_group.pk, "role": "foo"},
        )
        request.user = self.user
        response = self.get_view()(request)
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
        request = self.factory.post(
            self.get_url(),
            {"parent_group": parent_group.pk, "child_group": child_group.pk},
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_a_group_to_itself_member(self):
        """Cannot create a GroupGroupMembership object where the parent and child are the same group."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": group.pk,
                "child_group": group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("add a group to itself", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_a_group_to_itself_admin(self):
        """Cannot create a GroupGroupMembership object where the parent and child are the same group."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": group.pk,
                "child_group": group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
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
        factories.GroupGroupMembershipFactory.create(
            parent_group=grandparent, child_group=parent
        )
        factories.GroupGroupMembershipFactory.create(
            parent_group=parent, child_group=child
        )
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": child.pk,
                "child_group": grandparent.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("circular", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)

    def test_cannot_add_child_group_if_parent_not_managed_by_app(self):
        """Cannot add a child group to a parent group if the parent group is not managed by the app."""
        parent_group = factories.ManagedGroupFactory.create(
            name="group-1", is_managed_by_app=False
        )
        child_group = factories.ManagedGroupFactory.create(name="group-2")
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
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
        url = (
            self.entry_point
            + "/api/groups/"
            + parent_group.name
            + "/MEMBER/"
            + child_group.get_email()
        )
        responses.add(
            responses.PUT,
            url,
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership create test error",
            str(messages[0]),
        )
        responses.assert_call_count(url, 1)
        # Make sure that the object was not created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    @skip("AnVIL API issue - covered by model fields")
    def test_api_no_permission_for_parent_group(self):
        self.fail(
            "Trying to add a child group to a parent group that you don't have permission for returns a successful code."  # noqa
        )

    @skip("AnVIL API issue")
    def test_api_child_group_exists_parent_group_does_not_exist(self):
        self.fail(
            "Trying to add a group that exists to a group that doesn't exist returns a successful code."
        )

    @skip("AnVIL API issue")
    def test_api_child_group_does_not_exist_parent_group_does_not_exist(self):
        self.fail(
            "Trying to add a group that doesn't exist to a group that doesn't exist returns a successful code."
        )

    @skip("AnVIL API issue")
    def test_api_child_group_does_not_exist_parent_group_exists(self):
        self.fail(
            "Trying to add a group that doesn't exist to a group that exists returns a successful code."
        )


class GroupGroupMembershipListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:group_group_membership:list", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.GroupGroupMembershipTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.GroupGroupMembershipFactory()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.GroupGroupMembershipFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:managed_groups:member_groups:delete", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipDelete.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("parent", "child"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url("parent", "child"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.GroupGroupMembershipFactory.create()
        request = self.factory.get(
            self.get_url(obj.parent_group.name, obj.child_group.name)
        )
        request.user = self.user
        response = self.get_view()(
            request,
            parent_group_slug=obj.parent_group.name,
            child_group_slug=obj.child_group.name,
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url("parent", "child"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request, parent_group_slug="parent", child_group_slug="child"
            )

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url("parent", "child"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request, parent_group_slug="parent", child_group_slug="child"
            )

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url("parent", "child"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request, parent_group_slug="parent", child_group_slug="child"
            )

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        obj = factories.GroupGroupMembershipFactory.create(
            role=models.GroupGroupMembership.MEMBER
        )
        url = (
            self.entry_point
            + "/api/groups/"
            + obj.parent_group.name
            + "/"
            + obj.role
            + "/"
            + obj.child_group.get_email()
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(obj.history.count(), 2)
        self.assertEqual(obj.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        obj = factories.GroupGroupMembershipFactory.create(
            role=models.GroupGroupMembership.MEMBER
        )
        url = (
            self.entry_point
            + "/api/groups/"
            + obj.parent_group.name
            + "/"
            + obj.role
            + "/"
            + obj.child_group.get_email()
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.parent_group.name, obj.child_group.name),
            {"submit": ""},
            follow=True,
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupGroupMembershipDelete.success_msg, str(messages[0]))

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        obj = factories.GroupGroupMembershipFactory.create()
        other_object = factories.GroupGroupMembershipFactory.create()
        url = (
            self.entry_point
            + "/api/groups/"
            + obj.parent_group.name
            + "/"
            + obj.role
            + "/"
            + obj.child_group.get_email()
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        self.assertQuerysetEqual(
            models.GroupGroupMembership.objects.all(),
            models.GroupGroupMembership.objects.filter(pk=other_object.pk),
        )
        responses.assert_call_count(url, 1)

    def test_success_url(self):
        """Redirects to the expected page."""
        obj = factories.GroupGroupMembershipFactory.create()
        parent_group = obj.parent_group
        url = (
            self.entry_point
            + "/api/groups/"
            + obj.parent_group.name
            + "/"
            + obj.role
            + "/"
            + obj.child_group.get_email()
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        # Need to use the client instead of RequestFactory to check redirection url.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, parent_group.get_absolute_url())
        responses.assert_call_count(url, 1)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        obj = factories.GroupGroupMembershipFactory.create()
        url = (
            self.entry_point
            + "/api/groups/"
            + obj.parent_group.name
            + "/"
            + obj.role
            + "/"
            + obj.child_group.get_email()
        )
        responses.add(
            responses.DELETE,
            url,
            status=500,
            json={"message": "group group membership delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.parent_group.name, obj.child_group.name), {"submit": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            "AnVIL API Error: group group membership delete test error",
            str(messages[0]),
        )
        responses.assert_call_count(url, 1)
        # Make sure that the object still exists.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)

    def test_get_redirect_parent_group_not_managed_by_app(self):
        """Redirect get when trying to delete GroupGroupMembership when a parent group is not managed by the app."""
        parent_group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        child_group = factories.ManagedGroupFactory.create()
        obj = factories.GroupGroupMembershipFactory.create(
            parent_group=parent_group, child_group=child_group
        )
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(obj.parent_group.name, obj.child_group.name), follow=True
        )
        self.assertRedirects(response, obj.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
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
        obj = factories.GroupGroupMembershipFactory.create(
            parent_group=parent_group, child_group=child_group
        )
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.parent_group.name, obj.child_group.name), follow=True
        )
        self.assertRedirects(response, obj.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupGroupMembershipDelete.message_parent_group_not_managed_by_app,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)

    @skip("AnVIL API issue - covered by model fields")
    def test_api_no_permission_for_parent_group(self):
        self.fail(
            "Trying to remove a child group from a parent group that you don't have permission for returns a successful code."  # noqa
        )

    @skip("AnVIL API issue")
    def test_api_child_group_exists_parent_group_does_not_exist(self):
        self.fail(
            "Trying to remove a group that exists from a group that doesn't exist returns a successful code."
        )

    @skip("AnVIL API issue")
    def test_api_child_group_does_not_exist_parent_group_does_not_exist(self):
        self.fail(
            "Trying to remove a group that doesn't exist from a group that doesn't exist returns a successful code."
        )

    @skip("AnVIL API issue")
    def test_api_child_group_does_not_exist_parent_group_exists(self):
        self.fail(
            "Trying to remove a group that doesn't exist from a group that exists returns a successful code."
        )


class GroupAccountMembershipDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:managed_groups:member_accounts:detail", args=args
        )

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
        request = self.factory.get(obj.get_absolute_url())
        request.user = self.user
        request = self.factory.get(self.get_url(obj.group.name, obj.account.uuid))
        request.user = self.user
        response = self.get_view()(
            request,
            group_slug=obj.group.name,
            account_uuid=obj.account.uuid,
        )
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:group_account_membership:new", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipCreate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(
            response.context_data["form"], forms.GroupAccountMembershipForm
        )

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        account = factories.AccountFactory.create(email="email@example.com")
        url = (
            self.entry_point + "/api/groups/" + group.name + "/MEMBER/" + account.email
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
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
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_success_message(self):
        """Response includes a success message if successful."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        account = factories.AccountFactory.create(email="email@example.com")
        url = (
            self.entry_point + "/api/groups/" + group.name + "/MEMBER/" + account.email
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupAccountMembershipCreate.success_msg, str(messages[0])
        )

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        account = factories.AccountFactory.create(email="email@example.com")
        url = self.entry_point + "/api/groups/" + group.name + "/ADMIN/" + account.email
        responses.add(responses.PUT, url, status=self.api_success_code)
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
        responses.assert_call_count(url, 1)

    def test_redirects_to_list(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        url = self.entry_point + "/api/groups/" + group.name + "/ADMIN/" + account.email
        responses.add(responses.PUT, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertRedirects(
            response, reverse("anvil_consortium_manager:group_account_membership:list")
        )
        responses.assert_call_count(url, 1)

    def test_cannot_create_duplicate_object_with_same_role(self):
        """Cannot create a second GroupAccountMembership object for the same account and group with the same role."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        obj = factories.GroupAccountMembershipFactory(
            group=group, account=account, role=models.GroupAccountMembership.MEMBER
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
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
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.GroupAccountMembership.objects.all(),
            models.GroupAccountMembership.objects.filter(pk=obj.pk),
        )

    def test_can_add_two_groups_for_one_account(self):
        group_1 = factories.ManagedGroupFactory.create(name="test-group-1")
        group_2 = factories.ManagedGroupFactory.create(name="test-group-2")
        account = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group_1, account=account)
        url = (
            self.entry_point
            + "/api/groups/"
            + group_2.name
            + "/MEMBER/"
            + account.email
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
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
        responses.assert_call_count(url, 1)

    def test_can_add_two_accounts_to_one_group(self):
        group = factories.ManagedGroupFactory.create()
        account_1 = factories.AccountFactory.create(email="test_1@example.com")
        account_2 = factories.AccountFactory.create(email="test_2@example.com")
        factories.GroupAccountMembershipFactory.create(group=group, account=account_1)
        url = (
            self.entry_point
            + "/api/groups/"
            + group.name
            + "/MEMBER/"
            + account_2.email
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
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
        responses.assert_call_count(url, 1)

    def test_invalid_input_account(self):
        """Posting invalid data to account field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": 1,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("account", form.errors.keys())
        self.assertIn("valid choice", form.errors["account"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_invalid_input_group(self):
        """Posting invalid data to group field does not create an object."""
        account = factories.AccountFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": 1,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
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
        request = self.factory.post(
            self.get_url(),
            {"group": group.pk, "account": account.pk, "role": "foo"},
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("valid choice", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        request.user = self.user
        response = self.get_view()(request)
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
        request = self.factory.post(
            self.get_url(),
            {"account": account.pk, "role": models.GroupAccountMembership.MEMBER},
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_account(self):
        """Posting blank data to the account field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"group": group.pk, "role": models.GroupAccountMembership.MEMBER},
        )
        request.user = self.user
        response = self.get_view()(request)
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
        request = self.factory.post(
            self.get_url(), {"group": group.pk, "account": account.pk}
        )
        request.user = self.user
        response = self.get_view()(request)
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
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
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
        url = (
            self.entry_point + "/api/groups/" + group.name + "/MEMBER/" + account.email
        )
        responses.add(
            responses.PUT,
            url,
            status=500,
            json={"message": "group account membership create test error"},
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
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership create test error",
            str(messages[0]),
        )
        responses.assert_call_count(url, 1)
        # Make sure that the object was not created.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_cannot_add_inactive_account_to_group(self):
        """Cannot add an inactive account to a group."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create(status=models.Account.INACTIVE_STATUS)
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
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
        inactive_account = factories.AccountFactory.create(
            status=models.Account.INACTIVE_STATUS
        )
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)
        form = response.context_data["form"]
        self.assertIn(active_account, form.fields["account"].queryset)
        self.assertNotIn(inactive_account, form.fields["account"].queryset)

    @skip("AnVIL API issue - covered by model fields")
    def test_api_no_permission_for_group(self):
        self.fail(
            "Trying to add a user to a group that you don't have permission for returns a successful code."
        )

    @skip("AnVIL API issue")
    def test_api_user_exists_group_does_not_exist(self):
        self.fail(
            "Trying to add a user that exists to a group that doesn't exist returns a successful code."
        )

    @skip("AnVIL API issue")
    def test_api_user_does_not_exist_group_does_not_exist(self):
        self.fail(
            "Trying to add a user that doesn't exist to a group that doesn't exist returns a successful code."
        )

    @skip("AnVIL API issue")
    def test_api_user_does_not_exist_group_exists(self):
        self.fail(
            "Trying to add a user that doesn't exist to a group that exists returns a successful code."
        )


class GroupAccountMembershipListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:group_account_membership:list", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.GroupAccountMembershipTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.GroupAccountMembershipFactory()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.GroupAccountMembershipFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:group_account_membership:list_active", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipActiveList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.GroupAccountMembershipTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.GroupAccountMembershipFactory()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.GroupAccountMembershipFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_does_not_show_inactive_accounts(self):
        """Inactive accounts are not shown."""
        factories.GroupAccountMembershipFactory.create_batch(
            2, account__status=models.Account.INACTIVE_STATUS
        )
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:group_account_membership:list_inactive", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipInactiveList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.GroupAccountMembershipTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        membership = factories.GroupAccountMembershipFactory()
        membership.account.status = models.Account.INACTIVE_STATUS
        membership.account.save()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        memberships = factories.GroupAccountMembershipFactory.create_batch(2)
        memberships[0].account.status = models.Account.INACTIVE_STATUS
        memberships[0].account.save()
        memberships[1].account.status = models.Account.INACTIVE_STATUS
        memberships[1].account.save()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_does_not_show_active_accounts(self):
        """Active accounts are not shown."""
        factories.GroupAccountMembershipFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
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
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:managed_groups:member_accounts:delete", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipDelete.as_view()

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
        request = self.factory.get(self.get_url(obj.group.name, obj.account.uuid))
        request.user = self.user
        response = self.get_view()(
            request, group_slug=obj.group.name, account_uuid=obj.account.uuid
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        uuid = uuid4()
        request = self.factory.get(self.get_url("foo", uuid))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, group_slug="foo", account_uuid=uuid)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
        url = (
            self.entry_point
            + "/api/groups/"
            + object.group.name
            + "/"
            + object.role
            + "/"
            + object.account.email
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.group.name, object.account.uuid), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(object.history.count(), 2)
        self.assertEqual(object.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        object = factories.GroupAccountMembershipFactory.create()
        url = (
            self.entry_point
            + "/api/groups/"
            + object.group.name
            + "/"
            + object.role
            + "/"
            + object.account.email
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.group.name, object.account.uuid),
            {"submit": ""},
            follow=True,
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupAccountMembershipDelete.success_msg, str(messages[0])
        )

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.GroupAccountMembershipFactory.create()
        other_object = factories.GroupAccountMembershipFactory.create()
        url = (
            self.entry_point
            + "/api/groups/"
            + object.group.name
            + "/"
            + object.role
            + "/"
            + object.account.email
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.group.name, object.account.uuid), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        self.assertQuerysetEqual(
            models.GroupAccountMembership.objects.all(),
            models.GroupAccountMembership.objects.filter(pk=other_object.pk),
        )
        responses.assert_call_count(url, 1)

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.GroupAccountMembershipFactory.create()
        group = object.group
        # Need to use the client instead of RequestFactory to check redirection url.
        url = (
            self.entry_point
            + "/api/groups/"
            + object.group.name
            + "/"
            + object.role
            + "/"
            + object.account.email
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.group.name, object.account.uuid), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, group.get_absolute_url())
        responses.assert_call_count(url, 1)

    def test_get_redirect_group_not_managed_by_app(self):
        """Redirect get when trying to delete GroupAccountMembership when the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        account = factories.AccountFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, account=account
        )
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(membership.group.name, membership.account.uuid), follow=True
        )
        self.assertRedirects(response, membership.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
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
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, account=account
        )
        # Need to use a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(membership.group.name, membership.account.uuid), follow=True
        )
        self.assertRedirects(response, membership.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupAccountMembershipDelete.message_group_not_managed_by_app,
            str(messages[0]),
        )
        # Make sure that the object still exists.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.GroupAccountMembershipFactory.create()
        url = (
            self.entry_point
            + "/api/groups/"
            + object.group.name
            + "/"
            + object.role
            + "/"
            + object.account.email
        )
        responses.add(
            responses.DELETE,
            url,
            status=500,
            json={"message": "group account membership delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(object.group.name, object.account.uuid), {"submit": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: group account membership delete test error",
            str(messages[0]),
        )
        responses.assert_call_count(url, 1)
        # Make sure that the object still exists.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)

    @skip("AnVIL API issue - covered by model fields")
    def test_api_no_permission_for_group(self):
        self.fail(
            "Trying to delete a user that exists to a group that you don't have permission for returns a successful code."  # noqa
        )

    @skip("AnVIL API issue")
    def test_api_user_exists_group_does_not_exist(self):
        self.fail(
            "Trying to delete a user that exists from a group that doesn't exist returns a successful code."
        )

    @skip("AnVIL API issue")
    def test_api_user_does_not_exist_group_does_not_exist(self):
        self.fail(
            "Trying to delete a user that doesn't exist from a group that doesn't exist returns a successful code."
        )

    @skip("AnVIL API issue")
    def test_api_user_does_not_exist_group_exists(self):
        self.fail(
            "Trying to delete a user that doesn't exist from a group that exists returns a successful code."
        )


class WorkspaceGroupAccessDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:access:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(
            self.get_url("billing_project", "workspace", "group")
        )
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url("billing_project", "workspace", "group"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.WorkspaceGroupAccessFactory.create()
        request = self.factory.get(obj.get_absolute_url())
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=obj.workspace.billing_project.name,
            workspace_slug=obj.workspace.name,
            group_slug=obj.group.name,
        )
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(
            self.get_url("billing_project", "workspace", "group")
        )
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
        factories.WorkspaceGroupAccessFactory.create()
        request = self.factory.get(
            self.get_url("billing_project", "workspace", "group")
        )
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="billing_project",
                workspace_slug="workspace",
                group_slug="group",
            )


class WorkspaceGroupAccessCreateTest(AnVILAPIMockTestMixin, TestCase):

    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspace_group_access:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessCreate.as_view()

    def get_api_json_response(
        self, invites_sent=[], users_not_found=[], users_updated=[]
    ):
        return {
            "invitesSent": invites_sent,
            "usersNotFound": users_not_found,
            "usersUpdated": users_updated,
        }

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(
            response.context_data["form"], forms.WorkspaceGroupAccessForm
        )

    def test_can_create_an_object_reader(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project=billing_project
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
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
                "access": models.WorkspaceGroupAccess.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access, models.WorkspaceGroupAccess.READER)
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_create_a_writer_with_can_compute(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project=billing_project
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
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
                "access": models.WorkspaceGroupAccess.WRITER,
                "can_compute": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access, models.WorkspaceGroupAccess.WRITER)
        self.assertEqual(new_object.can_compute, True)
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_success_message(self):
        """Response includes a success message if successful."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project=billing_project
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
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
                "access": models.WorkspaceGroupAccess.READER,
                "can_compute": False,
            },
            follow=True,
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceGroupAccessCreate.success_msg, str(messages[0]))

    def test_can_create_an_object_writer(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.get_email(),
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + workspace.billing_project.name
            + "/"
            + workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
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
                "access": models.WorkspaceGroupAccess.WRITER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access, models.WorkspaceGroupAccess.WRITER)
        self.assertEqual(new_object.can_compute, False)
        responses.assert_call_count(url, 1)

    def test_can_create_an_object_owner(self):
        """Posting valid data to the form creates an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.get_email(),
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + workspace.billing_project.name
            + "/"
            + workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
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
                "access": models.WorkspaceGroupAccess.OWNER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access, models.WorkspaceGroupAccess.OWNER)
        responses.assert_call_count(url, 1)

    def test_redirects_to_list(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.get_email(),
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + workspace.billing_project.name
            + "/"
            + workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
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
                "access": models.WorkspaceGroupAccess.OWNER,
                "can_compute": False,
            },
        )
        self.assertRedirects(
            response, reverse("anvil_consortium_manager:workspace_group_access:list")
        )
        responses.assert_call_count(url, 1)

    def test_cannot_create_duplicate_object_with_same_access(self):
        """Cannot create a second object for the same workspace and group with the same access level."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupAccessFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupAccess.READER,
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
                "can_compute": False,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.WorkspaceGroupAccess.objects.all(),
            models.WorkspaceGroupAccess.objects.filter(pk=obj.pk),
        )

    def test_cannot_create_duplicate_object_with_different_access(self):
        """Cannot create a second object for the same workspace and group with a different access level."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupAccessFactory(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupAccess.READER,
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.OWNER,
                "can_compute": False,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerysetEqual(
            models.WorkspaceGroupAccess.objects.all(),
            models.WorkspaceGroupAccess.objects.filter(pk=obj.pk),
        )

    def test_can_have_two_workspaces_for_one_group(self):
        group_1 = factories.ManagedGroupFactory.create(name="test-group-1")
        group_2 = factories.ManagedGroupFactory.create(name="test-group-2")
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceGroupAccessFactory.create(group=group_1, workspace=workspace)
        json_data = [
            {
                "email": group_2.get_email(),
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + workspace.billing_project.name
            + "/"
            + workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
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
                "access": models.WorkspaceGroupAccess.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 2)
        responses.assert_call_count(url, 1)

    def test_can_have_two_groups_for_one_workspace(self):
        group = factories.ManagedGroupFactory.create()
        workspace_1 = factories.WorkspaceFactory.create(name="test-workspace-1")
        workspace_2 = factories.WorkspaceFactory.create(name="test-workspace-2")
        factories.WorkspaceGroupAccessFactory.create(group=group, workspace=workspace_1)
        json_data = [
            {
                "email": group.get_email(),
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + workspace_2.billing_project.name
            + "/"
            + workspace_2.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
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
                "access": models.WorkspaceGroupAccess.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 2)
        responses.assert_call_count(url, 1)

    def test_invalid_input_group(self):
        """Posting invalid data to group field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": 1,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
                "can_compute": False,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_invalid_input_workspace(self):
        """Posting invalid data to workspace field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": 1,
                "access": models.WorkspaceGroupAccess.READER,
                "can_compute": False,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("valid choice", form.errors["workspace"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_invalid_input_access(self):
        """Posting invalid data to access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": "foo",
                "can_compute": False,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("valid choice", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_invalid_reader_with_can_compute(self):
        """Posting invalid data to access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
                "can_compute": True,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("cannot be granted compute", form.non_field_errors()[0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data_group(self):
        """Posting blank data to the group field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
                "can_compute": False,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data_workspace(self):
        """Posting blank data to the workspace field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "access": models.WorkspaceGroupAccess.READER,
                "can_compute": False,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data_access(self):
        """Posting blank data to the access field does not create an object."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.ManagedGroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "can_compute": False,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data_can_compute(self):
        """Posting blank data to the can_compute field does not create an object."""
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": group.get_email(),
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + workspace.billing_project.name
            + "/"
            + workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
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
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertEqual(new_object.can_compute, False)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 1)

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
        url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
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
                "access": models.WorkspaceGroupAccess.READER,
                "can_compute": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        # The form is valid, but there was a different error.
        self.assertTrue(form.is_valid())
        self.assertEqual(response.status_code, 200)
        # Check for the correct message.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn(
            views.WorkspaceGroupAccessCreate.message_group_not_found,
            str(messages[0]),
        )
        responses.assert_call_count(url, 1)
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        group = factories.ManagedGroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        url = (
            self.entry_point
            + "/api/workspaces/"
            + workspace.billing_project.name
            + "/"
            + workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=500,
            json={"message": "workspace group access create test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: workspace group access create test error",
            str(messages[0]),
        )
        responses.assert_call_count(url, 1)
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    @skip("AnVIL API issue")
    def test_api_sharing_workspace_that_doesnt_exist_with_group_that_doesnt_exist(
        self,
    ):
        self.fail(
            "Sharing a workspace that doesn't exist with a group that doesn't exist returns a successful code."  # noqa
        )


class WorkspaceGroupAccessUpdateTest(AnVILAPIMockTestMixin, TestCase):
    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:access:update", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessUpdate.as_view()

    def get_api_json_response(
        self, invites_sent=[], users_not_found=[], users_updated=[]
    ):
        return {
            "invitesSent": invites_sent,
            "usersNotFound": users_not_found,
            "usersUpdated": users_updated,
        }

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(
            self.get_url("billing_project", "workspace", "group")
        )
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url("billing_project", "workspace", "group"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.WorkspaceGroupAccessFactory.create()
        request = self.factory.get(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            )
        )
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=obj.workspace.billing_project.name,
            workspace_slug=obj.workspace.name,
            group_slug=obj.group.name,
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(
            self.get_url("billing_project", "workspace", "group")
        )
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug="billing_project",
                workspace_slug="workspace",
                group_slug="group",
            )

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(
            self.get_url("billing_project", "workspace", "group")
        )
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
        obj = factories.WorkspaceGroupAccessFactory.create()
        request = self.factory.get(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            )
        )
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=obj.workspace.billing_project.name,
            workspace_slug=obj.workspace.name,
            group_slug=obj.group.name,
        )
        self.assertTrue("form" in response.context_data)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(
            self.get_url("billing_project", "workspace", "group")
        )
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
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project=billing_project
        )
        obj = factories.WorkspaceGroupAccessFactory.create(
            group=group, workspace=workspace, access=models.WorkspaceGroupAccess.READER
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {
                "access": models.WorkspaceGroupAccess.WRITER,
            },
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupAccess.WRITER)
        # History is added.
        self.assertEqual(obj.history.count(), 2)
        self.assertEqual(obj.history.latest().history_type, "~")

    def test_can_update_can_compute(self):
        """Can update the can_compute field."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project=billing_project
        )
        obj = factories.WorkspaceGroupAccessFactory.create(
            group=group, workspace=workspace, access=models.WorkspaceGroupAccess.WRITER
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {"access": models.WorkspaceGroupAccess.WRITER, "can_compute": True},
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupAccess.WRITER)
        self.assertEqual(obj.can_compute, True)
        # History is added.
        self.assertEqual(obj.history.count(), 2)
        self.assertEqual(obj.history.latest().history_type, "~")

    def test_invalid_reader_can_compute(self):
        """The form is not valid when trying to update a READER's can_compute value to True."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project=billing_project
        )
        obj = factories.WorkspaceGroupAccessFactory.create(
            group=group, workspace=workspace, access=models.WorkspaceGroupAccess.READER
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {"access": models.WorkspaceGroupAccess.READER, "can_compute": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("cannot be granted compute", form.non_field_errors()[0])
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupAccess.READER)
        self.assertEqual(obj.can_compute, False)
        # History is not added.
        self.assertEqual(obj.history.count(), 1)

    def test_success_message(self):
        """Response includes a success message if successful."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project=billing_project
        )
        obj = factories.WorkspaceGroupAccessFactory.create(
            group=group, workspace=workspace, access=models.WorkspaceGroupAccess.READER
        )
        json_data = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {
                "access": models.WorkspaceGroupAccess.WRITER,
            },
            follow=True,
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceGroupAccessUpdate.success_msg, str(messages[0]))

    def test_redirects_to_detail(self):
        """After successfully updating an object, view redirects to the model's get_absolute_url."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        obj = factories.WorkspaceGroupAccessFactory(
            access=models.WorkspaceGroupAccess.READER
        )
        json_data = [
            {
                "email": obj.group.get_email(),
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + obj.workspace.billing_project.name
            + "/"
            + obj.workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {
                "access": models.WorkspaceGroupAccess.WRITER,
            },
        )
        self.assertRedirects(response, obj.get_absolute_url())
        responses.assert_call_count(url, 1)

    def test_post_blank_data_access(self):
        """Posting blank data to the access field does not update the object."""
        obj = factories.WorkspaceGroupAccessFactory.create(
            access=models.WorkspaceGroupAccess.READER
        )
        request = self.factory.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {"access": ""},
        )
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=obj.workspace.billing_project.name,
            workspace_slug=obj.workspace.name,
            group_slug=obj.group.name,
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupAccess.READER)

    def test_post_blank_data_can_compute(self):
        """Posting blank data to the can_compute field updates the object."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project__name="test-billing-project"
        )
        obj = factories.WorkspaceGroupAccessFactory.create(
            group=group,
            workspace=workspace,
            access=models.WorkspaceGroupAccess.OWNER,
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
        url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {"access": models.WorkspaceGroupAccess.WRITER},
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupAccess.WRITER)
        self.assertEqual(obj.can_compute, False)

    def test_post_invalid_data_access(self):
        """Posting invalid data to the access field does not update the object."""
        obj = factories.WorkspaceGroupAccessFactory.create(
            access=models.WorkspaceGroupAccess.READER
        )
        request = self.factory.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {"access": "foo"},
        )
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=obj.workspace.billing_project.name,
            workspace_slug=obj.workspace.name,
            group_slug=obj.group.name,
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("valid choice", form.errors["access"][0])
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupAccess.READER)

    def test_post_group_pk(self):
        """Posting a group pk has no effect."""
        original_group = factories.ManagedGroupFactory.create()
        obj = factories.WorkspaceGroupAccessFactory(
            group=original_group, access=models.WorkspaceGroupAccess.READER
        )
        new_group = factories.ManagedGroupFactory.create()
        json_data = [
            {
                "email": obj.group.get_email(),
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + obj.workspace.billing_project.name
            + "/"
            + obj.workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {
                "group": new_group.pk,
                "access": models.WorkspaceGroupAccess.WRITER,
            },
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.group, original_group)
        responses.assert_call_count(url, 1)

    def test_post_workspace_pk(self):
        """Posting a workspace pk has no effect."""
        original_workspace = factories.WorkspaceFactory.create()
        obj = factories.WorkspaceGroupAccessFactory(
            workspace=original_workspace, access=models.WorkspaceGroupAccess.READER
        )
        new_workspace = factories.WorkspaceFactory.create()
        json_data = [
            {
                "email": obj.group.get_email(),
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + obj.workspace.billing_project.name
            + "/"
            + obj.workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
            json=self.get_api_json_response(users_updated=json_data),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {
                "workspace": new_workspace.pk,
                "access": models.WorkspaceGroupAccess.WRITER,
            },
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.workspace, original_workspace)
        responses.assert_call_count(url, 1)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        obj = factories.WorkspaceGroupAccessFactory.create(
            access=models.WorkspaceGroupAccess.READER
        )
        url = (
            self.entry_point
            + "/api/workspaces/"
            + obj.workspace.billing_project.name
            + "/"
            + obj.workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=500,
            json={"message": "workspace group access update test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {
                "access": models.WorkspaceGroupAccess.WRITER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: workspace group access update test error",
            str(messages[0]),
        )
        responses.assert_call_count(url, 1)
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 1)
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupAccess.READER)

    @skip("AnVIL API issue")
    def test_api_updating_access_to_workspace_that_doesnt_exist_for_group_that_doesnt_exist(
        self,
    ):
        self.fail(
            "Updating access from workspace that doesn't exist for a group that doesn't exist returns a successful code."  # noqa
        )


class WorkspaceGroupAccessListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:workspace_group_access:list", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.WorkspaceGroupAccessTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.WorkspaceGroupAccessFactory()
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.WorkspaceGroupAccessFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class WorkspaceGroupAccessDeleteTest(AnVILAPIMockTestMixin, TestCase):

    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:access:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessDelete.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(
            self.get_url("billing_project", "workspace", "group")
        )
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL)
            + "?next="
            + self.get_url("billing_project", "workspace", "group"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.WorkspaceGroupAccessFactory.create()
        request = self.factory.get(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            )
        )
        request.user = self.user
        response = self.get_view()(
            request,
            billing_project_slug=obj.workspace.billing_project.name,
            workspace_slug=obj.workspace.name,
            group_slug=obj.group.name,
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(
            self.get_url("billing_project", "workspace", "group")
        )
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug="billing_project",
                workspace_slug="workspace",
                group_slug="group",
            )

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(
            self.get_url("billing_project", "workspace", "group")
        )
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
        request = self.factory.get(
            self.get_url("billing_project", "workspace", "group")
        )
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
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project=billing_project
        )
        obj = factories.WorkspaceGroupAccessFactory.create(
            group=group, workspace=workspace
        )
        json_data = [
            {
                "email": obj.group.get_email(),
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(obj.history.count(), 2)
        self.assertEqual(obj.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project=billing_project
        )
        obj = factories.WorkspaceGroupAccessFactory.create(
            group=group, workspace=workspace
        )
        json_data = [
            {
                "email": obj.group.get_email(),
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {"submit": ""},
            follow=True,
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceGroupAccessDelete.success_msg, str(messages[0]))

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        obj = factories.WorkspaceGroupAccessFactory.create()
        other_object = factories.WorkspaceGroupAccessFactory.create()
        json_data = [
            {
                "email": obj.group.get_email(),
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + obj.workspace.billing_project.name
            + "/"
            + obj.workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 1)
        self.assertQuerysetEqual(
            models.WorkspaceGroupAccess.objects.all(),
            models.WorkspaceGroupAccess.objects.filter(pk=other_object.pk),
        )
        responses.assert_call_count(url, 1)

    def test_delete_with_can_compute(self):
        """Can delete a record with can_compute=True."""
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project=billing_project
        )
        obj = factories.WorkspaceGroupAccessFactory.create(
            group=group,
            workspace=workspace,
            can_compute=True,
        )
        json_data = [
            {
                "email": obj.group.get_email(),
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": True,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)
        responses.assert_call_count(url, 1)
        # History is added.
        self.assertEqual(obj.history.count(), 2)
        self.assertEqual(obj.history.latest().history_type, "-")

    def test_success_url(self):
        """Redirects to the expected page."""
        obj = factories.WorkspaceGroupAccessFactory.create()
        json_data = [
            {
                "email": obj.group.get_email(),
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + obj.workspace.billing_project.name
            + "/"
            + obj.workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        # Need to use the client instead of RequestFactory to check redirection url.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("anvil_consortium_manager:workspace_group_access:list")
        )
        responses.assert_call_count(url, 1)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        obj = factories.WorkspaceGroupAccessFactory.create()
        url = (
            self.entry_point
            + "/api/workspaces/"
            + obj.workspace.billing_project.name
            + "/"
            + obj.workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=500,
            json={"message": "workspace group access delete test error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                obj.workspace.billing_project.name, obj.workspace.name, obj.group.name
            ),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "AnVIL API Error: workspace group access delete test error",
            str(messages[0]),
        )
        responses.assert_call_count(url, 1)
        # Make sure that the object was not created.
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 1)

    @skip("AnVIL API issue")
    def test_api_removing_access_to_workspace_that_doesnt_exist_for_group_that_doesnt_exist(
        self,
    ):
        self.fail(
            "Removing access from workspace that doesn't exist for a group that doesn't exist returns a successful code."  # noqa
        )
