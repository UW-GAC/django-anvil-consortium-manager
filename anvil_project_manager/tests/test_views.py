from unittest import mock, skip

import responses
from django.http.response import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .. import forms, models, tables, views
from . import factories
from .utils import AnVILAPIMockTestMixin


class IndexTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:index", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.Index.as_view()

    def test_view_success_code(self):
        """Returns a successful status code."""
        request = self.factory.get(self.get_url())
        # request.user = AnonymousUser()
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)


class AnVILStatusTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()

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
        return reverse("anvil_project_manager:status", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AnVILStatus.as_view()

    def test_view_success_code(self):
        """Returns a successful status code."""
        url_me = self.entry_point + "/me?userDetailsOnly=true"
        responses.add(responses.GET, url_me, status=200, json=self.get_json_me_data())
        url_status = self.entry_point + "/status"
        responses.add(
            responses.GET, url_status, status=200, json=self.get_json_status_data()
        )
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        responses.assert_call_count(url_me, 1)
        responses.assert_call_count(url_status, 1)

    def test_context_data_anvil_status_ok(self):
        """Context data contains anvil_status."""
        url_me = self.entry_point + "/me?userDetailsOnly=true"
        responses.add(responses.GET, url_me, status=200, json=self.get_json_me_data())
        url_status = self.entry_point + "/status"
        responses.add(
            responses.GET, url_status, status=200, json=self.get_json_status_data()
        )
        request = self.factory.get(self.get_url())
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
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 2)
        self.assertEqual("AnVIL API Error: error checking API status", str(messages[0]))
        self.assertEqual("AnVIL API Error: error checking API user", str(messages[1]))
        responses.assert_call_count(url_me, 1)
        responses.assert_call_count(url_status, 1)


class BillingProjectDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:billing_projects:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.BillingProjectFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.BillingProjectFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)

    def test_workspace_table(self):
        """The workspace table exists."""
        obj = factories.BillingProjectFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertIn("workspace_table", response.context_data)
        self.assertIsInstance(
            response.context_data["workspace_table"], tables.WorkspaceTable
        )

    def test_workspace_table_none(self):
        """No workspaces are shown if the billing project does not have any workspaces."""
        billing_project = factories.BillingProjectFactory.create()
        request = self.factory.get(self.get_url(billing_project.pk))
        response = self.get_view()(request, pk=billing_project.pk)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)

    def test_workspace_table_one(self):
        """One workspace is shown if the group have access to one workspace."""
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(billing_project=billing_project)
        request = self.factory.get(self.get_url(billing_project.pk))
        response = self.get_view()(request, pk=billing_project.pk)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 1)

    def test_workspace_table_two(self):
        """Two workspaces are shown if the group have access to two workspaces."""
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create_batch(2, billing_project=billing_project)
        request = self.factory.get(self.get_url(billing_project.pk))
        response = self.get_view()(request, pk=billing_project.pk)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 2)

    def test_shows_workspace_for_only_this_group(self):
        """Only shows workspcaes that this group has access to."""
        billing_project = factories.BillingProjectFactory.create()
        other_billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(billing_project=other_billing_project)
        request = self.factory.get(self.get_url(billing_project.pk))
        response = self.get_view()(request, pk=billing_project.pk)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)


class BillingProjectCreateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:billing_projects:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        request = self.factory.post(self.get_url(), {"name": "test-group"})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.BillingProject.objects.latest("pk")
        self.assertIsInstance(new_object, models.BillingProject)

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        response = self.client.post(self.get_url(), {"name": "test-group"})
        new_object = models.BillingProject.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())

    def test_cannot_create_duplicate_object(self):
        """Cannot create two groups with the same name."""
        obj = factories.BillingProjectFactory.create()
        request = self.factory.post(self.get_url(), {"name": obj.name})
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
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.BillingProject.objects.count(), 0)


class BillingProjectListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:billing_projects:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.BillingProjectTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.BillingProjectFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.BillingProjectFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class BillingProjectDeleteTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:billing_projects:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.BillingProjectDelete.as_view()

    def test_view_status_code(self):
        """Returns a successful status code for an existing object."""
        object = factories.BillingProjectFactory.create()
        request = self.factory.get(self.get_url(object.pk))
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url(1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=1)

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        object = factories.BillingProjectFactory.create()
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.BillingProjectFactory.create()
        other_object = factories.BillingProjectFactory.create()
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.BillingProject.objects.count(), 1)
        self.assertQuerysetEqual(
            models.BillingProject.objects.all(),
            models.BillingProject.objects.filter(pk=other_object.pk),
        )

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.BillingProjectFactory.create()
        # Need to use the client instead of RequestFactory to check redirection url.
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("anvil_project_manager:billing_projects:list")
        )


class AccountDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:accounts:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.AccountFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.AccountFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)

    def test_group_account_membership_table(self):
        """The group membership table exists."""
        obj = factories.AccountFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertIn("group_table", response.context_data)
        self.assertIsInstance(
            response.context_data["group_table"], tables.GroupAccountMembershipTable
        )

    def test_group_account_membership_none(self):
        """No groups are shown if the account is not part of any groups."""
        account = factories.AccountFactory.create()
        request = self.factory.get(self.get_url(account.pk))
        response = self.get_view()(request, pk=account.pk)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)

    def test_group_account_membership_one(self):
        """One group is shown if the account is part of one group."""
        account = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create(account=account)
        request = self.factory.get(self.get_url(account.pk))
        response = self.get_view()(request, pk=account.pk)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 1)

    def test_group_account_membership_two(self):
        """Two groups are shown if the account is part of two groups."""
        account = factories.AccountFactory.create()
        factories.GroupAccountMembershipFactory.create_batch(2, account=account)
        request = self.factory.get(self.get_url(account.pk))
        response = self.get_view()(request, pk=account.pk)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 2)

    def test_shows_group_account_membership_for_only_that_user(self):
        """Only shows groups that this research is part of."""
        account = factories.AccountFactory.create(email="email_1@example.com")
        other_account = factories.AccountFactory.create(email="email_2@example.com")
        factories.GroupAccountMembershipFactory.create(account=other_account)
        request = self.factory.get(self.get_url(account.pk))
        response = self.get_view()(request, pk=account.pk)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)


class AccountCreateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:accounts:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        request = self.factory.post(self.get_url(), {"email": "test@example.com"})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.Account.objects.latest("pk")
        self.assertIsInstance(new_object, models.Account)
        self.assertFalse(new_object.is_service_account)

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        response = self.client.post(self.get_url(), {"email": "test@example.com"})
        new_object = models.Account.objects.latest("pk")
        self.assertRedirects(
            response,
            new_object.get_absolute_url(),
        )

    def test_cannot_create_duplicate_object(self):
        """Cannot create two accounts with the same email."""
        obj = factories.AccountFactory.create()
        request = self.factory.post(self.get_url(), {"email": obj.email})
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
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors.keys())
        self.assertIn("required", form.errors["email"][0])
        self.assertEqual(models.Account.objects.count(), 0)

    def test_can_create_service_account(self):
        """Can create a service account."""
        request = self.factory.post(
            self.get_url(), {"email": "test@example.com", "is_service_account": True}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.Account.objects.latest("pk")
        self.assertIsInstance(new_object, models.Account)
        self.assertTrue(new_object.is_service_account)


class AccountListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:accounts:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.AccountTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.AccountFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.AccountFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_service_account(self):
        factories.AccountFactory.create(is_service_account=True)
        factories.AccountFactory.create(is_service_account=False)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class AccountDeleteTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:accounts:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.AccountDelete.as_view()

    def test_view_status_code(self):
        """Returns a successful status code for an existing object."""
        object = factories.AccountFactory.create()
        request = self.factory.get(self.get_url(object.pk))
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url(1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=1)

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        object = factories.AccountFactory.create()
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 0)

    def test_view_deletes_object_service_account(self):
        """Posting submit to the form successfully deletes the service account object."""
        object = factories.AccountFactory.create(is_service_account=True)
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Account.objects.count(), 0)

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.AccountFactory.create()
        other_object = factories.AccountFactory.create()
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
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
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("anvil_project_manager:accounts:list"))


class GroupDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:groups:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)

    def test_workspace_table(self):
        """The workspace table exists."""
        obj = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertIn("workspace_table", response.context_data)
        self.assertIsInstance(
            response.context_data["workspace_table"], tables.WorkspaceGroupAccessTable
        )

    def test_workspace_table_none(self):
        """No workspaces are shown if the group does not have access to any workspaces."""
        group = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)

    def test_workspace_table_one(self):
        """One workspace is shown if the group have access to one workspace."""
        group = factories.GroupFactory.create()
        factories.WorkspaceGroupAccessFactory.create(group=group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 1)

    def test_workspace_table_two(self):
        """Two workspaces are shown if the group have access to two workspaces."""
        group = factories.GroupFactory.create()
        factories.WorkspaceGroupAccessFactory.create_batch(2, group=group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 2)

    def test_shows_workspace_for_only_this_group(self):
        """Only shows workspcaes that this group has access to."""
        group = factories.GroupFactory.create(name="group-1")
        other_group = factories.GroupFactory.create(name="group-2")
        factories.WorkspaceGroupAccessFactory.create(group=other_group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("workspace_table", response.context_data)
        self.assertEqual(len(response.context_data["workspace_table"].rows), 0)

    def test_account_table(self):
        """The account table exists."""
        obj = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertIn("account_table", response.context_data)
        self.assertIsInstance(
            response.context_data["account_table"], tables.GroupAccountMembershipTable
        )

    def test_account_table_none(self):
        """No accounts are shown if the group has no accounts."""
        group = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("account_table", response.context_data)
        self.assertEqual(len(response.context_data["account_table"].rows), 0)

    def test_account_table_one(self):
        """One accounts is shown if the group has only that account."""
        group = factories.GroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("account_table", response.context_data)
        self.assertEqual(len(response.context_data["account_table"].rows), 1)

    def test_account_table_two(self):
        """Two accounts are shown if the group has only those accounts."""
        group = factories.GroupFactory.create()
        factories.GroupAccountMembershipFactory.create_batch(2, group=group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("account_table", response.context_data)
        self.assertEqual(len(response.context_data["account_table"].rows), 2)

    def test_shows_account_for_only_this_group(self):
        """Only shows accounts that are in this group."""
        group = factories.GroupFactory.create(name="group-1")
        other_group = factories.GroupFactory.create(name="group-2")
        factories.GroupAccountMembershipFactory.create(group=other_group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("account_table", response.context_data)
        self.assertEqual(len(response.context_data["account_table"].rows), 0)

    def test_group_table(self):
        """The group table exists."""
        obj = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertIn("group_table", response.context_data)
        self.assertIsInstance(
            response.context_data["group_table"], tables.GroupGroupMembershipTable
        )

    def test_group_table_none(self):
        """No groups are shown if the group has no member groups."""
        group = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)

    def test_group_table_one(self):
        """One group is shown if the group has only that member group."""
        group = factories.GroupFactory.create()
        factories.GroupGroupMembershipFactory.create(parent_group=group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 1)

    def test_group_table_two(self):
        """Two groups are shown if the group has only those member groups."""
        group = factories.GroupFactory.create()
        factories.GroupGroupMembershipFactory.create_batch(2, parent_group=group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 2)

    def test_group_account_for_only_this_group(self):
        """Only shows member groups that are in this group."""
        group = factories.GroupFactory.create(name="group-1")
        other_group = factories.GroupFactory.create(name="group-2")
        factories.GroupGroupMembershipFactory.create(parent_group=other_group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("group_table", response.context_data)
        self.assertEqual(len(response.context_data["group_table"].rows), 0)

    def test_workspace_auth_domain_table(self):
        """The auth_domain table exists."""
        obj = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        self.assertIsInstance(
            response.context_data["workspace_authorization_domain_table"],
            tables.WorkspaceTable,
        )

    def test_workspace_auth_domain_table_none(self):
        """No workspaces are shown if the group is not the auth domain for any workspace."""
        group = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        self.assertEqual(
            len(response.context_data["workspace_authorization_domain_table"].rows), 0
        )

    def test_workspace_auth_domain_table_one(self):
        """One workspace is shown in if the group is the auth domain for it."""
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        workspace.authorization_domains.add(group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        table = response.context_data["workspace_authorization_domain_table"]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(workspace, table.data)

    def test_workspace_auth_domain_table_two(self):
        """Two workspaces are shown in if the group is the auth domain for them."""
        group = factories.GroupFactory.create()
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_1.authorization_domains.add(group)
        workspace_2 = factories.WorkspaceFactory.create()
        workspace_2.authorization_domains.add(group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        table = response.context_data["workspace_authorization_domain_table"]
        self.assertEqual(len(table.rows), 2)
        self.assertIn(workspace_1, table.data)
        self.assertIn(workspace_2, table.data)

    def test_workspace_auth_domain_account_for_only_this_group(self):
        """Only shows workspaces for which this group is the auth domain."""
        group = factories.GroupFactory.create(name="group")
        other_group = factories.GroupFactory.create(name="other-group")
        other_workspace = factories.WorkspaceFactory.create()
        other_workspace.authorization_domains.add(other_group)
        factories.GroupGroupMembershipFactory.create(parent_group=other_group)
        request = self.factory.get(self.get_url(group.pk))
        response = self.get_view()(request, pk=group.pk)
        self.assertIn("workspace_authorization_domain_table", response.context_data)
        self.assertEqual(
            len(response.context_data["workspace_authorization_domain_table"].rows), 0
        )


class GroupCreateTest(AnVILAPIMockTestMixin, TestCase):

    api_success_code = 201

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:groups:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        url = self.entry_point + "/api/groups/" + "test-group"
        responses.add(responses.POST, url, status=self.api_success_code)
        request = self.factory.post(self.get_url(), {"name": "test-group"})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.Group.objects.latest("pk")
        self.assertIsInstance(new_object, models.Group)
        self.assertEqual(new_object.name, "test-group")
        responses.assert_call_count(url, 1)

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        url = self.entry_point + "/api/groups/" + "test-group"
        responses.add(responses.POST, url, status=self.api_success_code)
        response = self.client.post(self.get_url(), {"name": "test-group"})
        new_object = models.Group.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())
        responses.assert_call_count(url, 1)

    def test_cannot_create_duplicate_object(self):
        """Cannot create two groups with the same name."""
        obj = factories.GroupFactory.create()
        request = self.factory.post(self.get_url(), {"name": obj.name})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("already exists", form.errors["name"][0])
        self.assertQuerysetEqual(
            models.Group.objects.all(),
            models.Group.objects.filter(pk=obj.pk),
        )
        self.assertEqual(len(responses.calls), 0)

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        request = self.factory.post(self.get_url(), {"name": ""})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.Group.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors.keys())
        self.assertIn("required", form.errors["name"][0])
        self.assertEqual(models.Group.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_api_error_message(self):
        """Shows a message if an AnVIL API error occurs."""
        url = self.entry_point + "/api/groups/" + "test-group"
        responses.add(
            responses.POST, url, status=500, json={"message": "group create test error"}
        )
        # Need a client to check messages.
        response = self.client.post(self.get_url(), {"name": "test-group"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: group create test error", str(messages[0]))
        responses.assert_call_count(url, 1)
        # Make sure that no object is created.
        self.assertEqual(models.Group.objects.count(), 0)

    @skip("AnVIL API issue")
    def test_api_group_already_exists(self):
        self.fail(
            "AnVIL API returns 201 instead of ??? when trying to create a group that already exists."
        )


class GroupListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:groups:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.GroupTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.GroupFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.GroupFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class GroupDeleteTest(AnVILAPIMockTestMixin, TestCase):

    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:groups:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupDelete.as_view()

    def test_view_status_code(self):
        """Returns a successful status code for an existing object."""
        object = factories.GroupFactory.create()
        request = self.factory.get(self.get_url(object.pk))
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url(1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=1)

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        object = factories.GroupFactory.create(name="test-group")
        url = self.entry_point + "/api/groups/" + object.name
        responses.add(responses.DELETE, url, status=self.api_success_code)
        # self.mock_request.return_value = self.get_mock_response(self.api_success_code)
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Group.objects.count(), 0)
        responses.assert_call_count(url, 1)

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.GroupFactory.create()
        other_object = factories.GroupFactory.create()
        url = self.entry_point + "/api/groups/" + object.name
        responses.add(responses.DELETE, url, status=self.api_success_code)
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Group.objects.count(), 1)
        self.assertQuerysetEqual(
            models.Group.objects.all(),
            models.Group.objects.filter(pk=other_object.pk),
        )
        responses.assert_call_count(url, 1)

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.GroupFactory.create()
        url = self.entry_point + "/api/groups/" + object.name
        responses.add(responses.DELETE, url, status=self.api_success_code)
        # Need to use the client instead of RequestFactory to check redirection url.
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("anvil_project_manager:groups:list"))
        responses.assert_call_count(url, 1)

    def test_get_redirect_group_used_as_auth_domain(self):
        """Redirect when trying to delete a group used as an auth domain with a get request."""
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        workspace.authorization_domains.add(group)
        # Need to use a client for messages.
        response = self.client.get(self.get_url(group.pk), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupDelete.message_group_is_auth_domain, str(messages[0])
        )
        # Make sure that the object still exists.
        self.assertEqual(models.Group.objects.count(), 1)

    def test_post_redirect_group_used_as_auth_domain(self):
        """Cannot delete a group used as an auth domain with a post request."""
        group = factories.GroupFactory.create()
        workspace = factories.WorkspaceFactory.create()
        workspace.authorization_domains.add(group)
        # Need to use a client for messages.
        response = self.client.post(self.get_url(group.pk), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.GroupDelete.message_group_is_auth_domain, str(messages[0])
        )
        # Make sure that the object still exists.
        self.assertEqual(models.Group.objects.count(), 1)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.GroupFactory.create()
        url = self.entry_point + "/api/groups/" + object.name
        responses.add(
            responses.DELETE,
            url,
            status=500,
            json={"message": "group delete test error"},
        )
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: group delete test error", str(messages[0]))
        responses.assert_call_count(url, 1)
        # Make sure that the object still exists.
        self.assertEqual(models.Group.objects.count(), 1)

    def test_get_redirect_group_not_managed_by_app(self):
        """Redirect when trying to delete a group that the app doesn't manage."""
        group = factories.GroupFactory.create(is_managed_by_app=False)
        # Need to use a client for messages.
        response = self.client.get(self.get_url(group.pk), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupDelete.message_not_admin, str(messages[0]))
        # Make sure that the object still exists.
        self.assertEqual(models.Group.objects.count(), 1)

    def test_post_redirect_group_not_managed_by_app(self):
        """Redirect when trying to delete a group that the app doesn't manage with a post request."""
        group = factories.GroupFactory.create(is_managed_by_app=False)
        # Need to use a client for messages.
        response = self.client.post(self.get_url(group.pk), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        # Check for messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.GroupDelete.message_not_admin, str(messages[0]))
        # Make sure that the object still exists.
        self.assertEqual(models.Group.objects.count(), 1)

    @skip("AnVIL API issue")
    def test_api_not_admin_of_group(self):
        self.fail(
            "AnVIL API returns 204 instead of 403 when trying to delete a group you are not an admin of."
        )

    @skip("AnVIL API issue")
    def test_api_group_does_not_exist(self):
        self.fail(
            "AnVIL API returns 204 instead of 404 when trying to delete a group that doesn't exist."
        )


class WorkspaceDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspaces:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)

    def test_group_access_table(self):
        """The workspace group access table exists."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertIn("group_access_table", response.context_data)
        self.assertIsInstance(
            response.context_data["group_access_table"],
            tables.WorkspaceGroupAccessTable,
        )

    def test_group_access_table_none(self):
        """No groups are shown if the workspace has not been shared with any groups."""
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.get(self.get_url(workspace.pk))
        response = self.get_view()(request, pk=workspace.pk)
        self.assertIn("group_access_table", response.context_data)
        self.assertEqual(len(response.context_data["group_access_table"].rows), 0)

    def test_group_access_table_one(self):
        """One group is shown if the workspace has been shared with one group."""
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceGroupAccessFactory.create(workspace=workspace)
        request = self.factory.get(self.get_url(workspace.pk))
        response = self.get_view()(request, pk=workspace.pk)
        self.assertIn("group_access_table", response.context_data)
        self.assertEqual(len(response.context_data["group_access_table"].rows), 1)

    def test_group_access_table_two(self):
        """Two groups are shown if the workspace has been shared with two groups."""
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceGroupAccessFactory.create_batch(2, workspace=workspace)
        request = self.factory.get(self.get_url(workspace.pk))
        response = self.get_view()(request, pk=workspace.pk)
        self.assertIn("group_access_table", response.context_data)
        self.assertEqual(len(response.context_data["group_access_table"].rows), 2)

    def test_shows_workspace_group_access_for_only_that_workspace(self):
        """Only shows groups that this workspace has been shared with."""
        workspace = factories.WorkspaceFactory.create(name="workspace-1")
        other_workspace = factories.WorkspaceFactory.create(name="workspace-2")
        factories.WorkspaceGroupAccessFactory.create(workspace=other_workspace)
        request = self.factory.get(self.get_url(workspace.pk))
        response = self.get_view()(request, pk=workspace.pk)
        self.assertIn("group_access_table", response.context_data)
        self.assertEqual(len(response.context_data["group_access_table"].rows), 0)

    def test_auth_domain_table(self):
        """The workspace auth domain table exists."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertIn("authorization_domain_table", response.context_data)
        self.assertIsInstance(
            response.context_data["authorization_domain_table"], tables.GroupTable
        )

    def test_auth_domain_table_none(self):
        """No groups are shown if the workspace has no auth domains."""
        workspace = factories.WorkspaceFactory.create()
        request = self.factory.get(self.get_url(workspace.pk))
        response = self.get_view()(request, pk=workspace.pk)
        self.assertIn("authorization_domain_table", response.context_data)
        self.assertEqual(
            len(response.context_data["authorization_domain_table"].rows), 0
        )

    def test_auth_domain_table_one(self):
        """One group is shown if the workspace has one auth domain."""
        workspace = factories.WorkspaceFactory.create()
        group = factories.GroupFactory.create()
        workspace.authorization_domains.add(group)
        request = self.factory.get(self.get_url(workspace.pk))
        response = self.get_view()(request, pk=workspace.pk)
        self.assertIn("authorization_domain_table", response.context_data)
        table = response.context_data["authorization_domain_table"]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(group, table.data)

    def test_auth_domain_table_two(self):
        """Two groups are shown if the workspace has two auth domains."""
        workspace = factories.WorkspaceFactory.create()
        group_1 = factories.GroupFactory.create()
        workspace.authorization_domains.add(group_1)
        group_2 = factories.GroupFactory.create()
        workspace.authorization_domains.add(group_2)
        request = self.factory.get(self.get_url(workspace.pk))
        response = self.get_view()(request, pk=workspace.pk)
        self.assertIn("authorization_domain_table", response.context_data)
        table = response.context_data["authorization_domain_table"]
        self.assertEqual(len(table.rows), 2)
        self.assertIn(group_1, table.data)
        self.assertIn(group_2, table.data)

    def test_shows_auth_domains_for_only_that_workspace(self):
        """Only shows auth domains for this workspace."""
        workspace = factories.WorkspaceFactory.create(name="workspace-1")
        other_workspace = factories.WorkspaceFactory.create(name="workspace-2")
        group = factories.GroupFactory.create()
        other_workspace.authorization_domains.add(group)
        request = self.factory.get(self.get_url(workspace.pk))
        response = self.get_view()(request, pk=workspace.pk)
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

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspaces:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

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
        request = self.factory.post(
            self.get_url(),
            {"billing_project": billing_project.pk, "name": "test-workspace"},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.Workspace.objects.latest("pk")
        self.assertIsInstance(new_object, models.Workspace)
        responses.assert_call_count(url, 1)

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
        response = self.client.post(
            self.get_url(),
            {"billing_project": billing_project.pk, "name": "test-workspace"},
        )
        new_object = models.Workspace.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())
        responses.assert_call_count(url, 1)

    def test_cannot_create_duplicate_object(self):
        """Cannot create two workspaces with the same billing project and name."""
        obj = factories.WorkspaceFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"billing_project": obj.billing_project.pk, "name": obj.name},
        )
        response = self.get_view()(request)
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
        request = self.factory.post(
            self.get_url(),
            {"billing_project": billing_project.pk, "name": "test-name-2"},
        )
        response = self.get_view()(request)
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
        request = self.factory.post(
            self.get_url(),
            {"billing_project": billing_project_2.pk, "name": workspace_name},
        )
        response = self.get_view()(request)
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
            self.get_url(),
            {"billing_project": billing_project.pk, "name": "invalid name"},
        )
        response = self.get_view()(request)
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
            self.get_url(), {"billing_project": 1, "name": "test-name"}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project", form.errors.keys())
        self.assertIn("valid choice", form.errors["billing_project"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_post_invalid_name_billing_project(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
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
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
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
        response = self.client.post(
            self.get_url(),
            {"billing_project": billing_project.pk, "name": "test-workspace"},
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
        auth_domain = factories.GroupFactory.create()
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
        request = self.factory.post(
            self.get_url(),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk],
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.Workspace.objects.latest("pk")
        self.assertIsInstance(new_object, models.Workspace)
        self.assertEqual(len(new_object.authorization_domains.all()), 1)
        self.assertIn(auth_domain, new_object.authorization_domains.all())
        responses.assert_call_count(url, 1)

    def test_create_workspace_with_two_auth_domains(self):
        """Can create a workspace with two authorization domains."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        auth_domain_1 = factories.GroupFactory.create()
        auth_domain_2 = factories.GroupFactory.create()
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
        request = self.factory.post(
            self.get_url(),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain_1.pk, auth_domain_2.pk],
            },
        )
        response = self.get_view()(request)
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
            self.get_url(),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [1],
            },
        )
        response = self.get_view()(request)
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
        auth_domain = factories.GroupFactory.create()
        url = self.entry_point + "/api/workspaces"
        request = self.factory.post(
            self.get_url(),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk, auth_domain.pk + 1],
            },
        )
        response = self.get_view()(request)
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
        auth_domain = factories.GroupFactory.create()
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
        response = self.client.post(
            self.get_url(),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk],
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
        auth_domain = factories.GroupFactory.create()
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
        response = self.client.post(
            self.get_url(),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                "authorization_domains": [auth_domain.pk],
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


class WorkspaceImportTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the WorkspaceImport view."""

    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspaces:import", args=args)

    def get_api_url(self, billing_project_name, workspace_name):
        return (
            self.entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
        )

    def get_api_json_response(self, billing_project, workspace, access="OWNER"):
        """Return a pared down version of the json response from the AnVIL API with only fields we need."""
        json_data = {
            "accessLevel": access,
            "owners": [],
            "workspace": {
                "authorizationDomain": [],
                "name": workspace,
                "namespace": billing_project,
            },
        }
        return json_data

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceImport.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)
        print(type(response.context_data["form"]))
        self.assertIsInstance(response.context_data["form"], forms.WorkspaceImportForm)

    def test_can_import_workspace(self):
        """Can import a workspace from AnVIL."""
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        request = self.factory.post(
            self.get_url(),
            {
                "billing_project_name": billing_project_name,
                "workspace_name": workspace_name,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        # Created a billing project.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        new_billing_project = models.BillingProject.objects.latest("pk")
        self.assertEqual(new_billing_project.name, billing_project_name)
        # Created a workspace.
        self.assertEqual(models.Workspace.objects.count(), 1)
        new_workspace = models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        responses.assert_call_count(url, 1)

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        response = self.client.post(
            self.get_url(),
            {
                "billing_project_name": billing_project_name,
                "workspace_name": workspace_name,
            },
        )
        new_object = models.Workspace.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())
        responses.assert_call_count(url, 1)

    def test_workspace_already_imported(self):
        """Does not import a workspace that already exists in Django."""
        workspace = factories.WorkspaceFactory.create()
        # No API calls.
        # Messages need the client.
        response = self.client.post(
            self.get_url(),
            {
                "billing_project_name": workspace.billing_project.name,
                "workspace_name": workspace.name,
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
        self.assertIn(views.WorkspaceImport.message_workspace_exists, str(messages[0]))
        # Did not create any new BillingProjects.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        # Did not create eany new Workspaces.
        self.assertEqual(models.Workspace.objects.count(), 1)

    def test_invalid_billing_project(self):
        """Does not create an object if billing project name is invalid."""
        billing_project_name = "billing project"
        workspace_name = "workspace"
        # No API call.
        request = self.factory.post(
            self.get_url(),
            {
                "billing_project_name": billing_project_name,
                "workspace_name": workspace_name,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project_name", form.errors.keys())
        self.assertIn("slug", form.errors["billing_project_name"][0])
        # Did not create any objects.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_invalid_workspace_name(self):
        """Does not create an object if workspace name is invalid."""
        billing_project_name = "billing-project"
        workspace_name = "workspace name"
        # No API call.
        request = self.factory.post(
            self.get_url(),
            {
                "billing_project_name": billing_project_name,
                "workspace_name": workspace_name,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace_name", form.errors.keys())
        self.assertIn("slug", form.errors["workspace_name"][0])
        # Did not create any objects.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        self.assertEqual(models.Workspace.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project_name", form.errors.keys())
        self.assertIn("required", form.errors["billing_project_name"][0])
        self.assertIn("workspace_name", form.errors.keys())
        self.assertIn("required", form.errors["workspace_name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_post_blank_data_billing_project(self):
        """Posting blank data in the billing project name field does not create an object."""
        request = self.factory.post(
            self.get_url(), {"workspace_name": "test-workspace"}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("billing_project_name", form.errors.keys())
        self.assertIn("required", form.errors["billing_project_name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_post_blank_data_workspace_name(self):
        """Posting blank data in the workspace_name field does not create an object."""
        request = self.factory.post(
            self.get_url(), {"billing_project_name": "test-billing-project"}
        )
        request = self.factory.post(self.get_url(), {})
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace_name", form.errors.keys())
        self.assertIn("required", form.errors["workspace_name"][0])
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(len(responses.calls), 0)

    def test_no_access_to_workspace(self):
        """Does not import a workspace if we don't have access to it."""
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=404,
            json={"message": "api error"},
        )
        response = self.client.post(
            self.get_url(),
            {
                "billing_project_name": billing_project_name,
                "workspace_name": workspace_name,
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
        self.assertIn(
            views.WorkspaceImport.message_anvil_no_access_to_workspace, str(messages[0])
        )
        # Did not create any objects.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        self.assertEqual(models.Workspace.objects.count(), 0)
        responses.assert_call_count(url, 1)

    def test_not_owner_of_workspace(self):
        """Does not import a workspace if we are not an owner."""
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=self.api_success_code,
            json=self.get_api_json_response(
                billing_project_name, workspace_name, access="READER"
            ),
        )
        response = self.client.post(
            self.get_url(),
            {
                "billing_project_name": billing_project_name,
                "workspace_name": workspace_name,
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
        self.assertIn(views.WorkspaceImport.message_anvil_not_owner, str(messages[0]))
        # Did not create any objects.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        self.assertEqual(models.Workspace.objects.count(), 0)
        responses.assert_call_count(url, 1)

    def test_other_anvil_api_error(self):
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=500,
            json={"message": "an error"},
        )
        response = self.client.post(
            self.get_url(),
            {
                "billing_project_name": billing_project_name,
                "workspace_name": workspace_name,
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


class WorkspaceListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspaces:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.WorkspaceTable)

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.WorkspaceFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.WorkspaceFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class WorkspaceDeleteTest(AnVILAPIMockTestMixin, TestCase):

    api_success_code = 202

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspaces:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceDelete.as_view()

    def test_view_status_code(self):
        """Returns a successful status code for an existing object."""
        object = factories.WorkspaceFactory.create()
        request = self.factory.get(self.get_url(object.pk))
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url(1))
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
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 0)
        responses.assert_call_count(url, 1)

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
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertQuerysetEqual(
            models.Workspace.objects.all(),
            models.Workspace.objects.filter(pk=other_object.pk),
        )
        responses.assert_call_count(url, 1)

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
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("anvil_project_manager:workspaces:list"))
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
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error: workspace delete test error", str(messages[0]))
        responses.assert_call_count(url, 1)
        # Make sure that the object still exists.
        self.assertEqual(models.Workspace.objects.count(), 1)


class GroupGroupMembershipDetailTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:group_group_membership:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.GroupGroupMembershipFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.GroupGroupMembershipFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)


class GroupGroupMembershipCreateTest(AnVILAPIMockTestMixin, TestCase):

    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:group_group_membership:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        parent_group = factories.GroupFactory.create(name="group-1")
        child_group = factories.GroupFactory.create(name="group-2")
        url = (
            self.entry_point
            + "/api/groups/"
            + parent_group.name
            + "/MEMBER/"
            + child_group.get_email()
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupGroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupGroupMembership)
        self.assertEqual(new_object.role, models.GroupGroupMembership.MEMBER)
        responses.assert_call_count(url, 1)

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        parent_group = factories.GroupFactory.create(name="group-1")
        child_group = factories.GroupFactory.create(name="group-2")
        url = (
            self.entry_point
            + "/api/groups/"
            + parent_group.name
            + "/ADMIN/"
            + child_group.get_email()
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupGroupMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupGroupMembership)
        self.assertEqual(new_object.role, models.GroupGroupMembership.ADMIN)
        responses.assert_call_count(url, 1)

    def test_redirects_to_list(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        parent_group = factories.GroupFactory.create(name="group-1")
        child_group = factories.GroupFactory.create(name="group-2")
        url = (
            self.entry_point
            + "/api/groups/"
            + parent_group.name
            + "/ADMIN/"
            + child_group.get_email()
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
        response = self.client.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        self.assertRedirects(
            response, reverse("anvil_project_manager:group_group_membership:list")
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
        group_1 = factories.GroupFactory.create(name="test-group-1")
        group_2 = factories.GroupFactory.create(name="test-group-2")
        parent = factories.GroupFactory.create(name="parent-group")
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
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": parent.pk,
                "child_group": group_2.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)
        responses.assert_call_count(url, 1)

    def test_can_add_a_child_group_to_two_parents(self):
        group_1 = factories.GroupFactory.create(name="test-group-1")
        group_2 = factories.GroupFactory.create(name="test-group-2")
        child = factories.GroupFactory.create(name="child_1-group")
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
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": group_2.pk,
                "child_group": child.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)
        responses.assert_call_count(url, 1)

    def test_invalid_input_child(self):
        """Posting invalid data to child_group field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": group.pk,
                "child_group": group.pk + 1,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("valid choice", form.errors["child_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_invalid_input_parent(self):
        """Posting invalid data to parent group field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": group.pk + 1,
                "child_group": group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("valid choice", form.errors["parent_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_invalid_input_role(self):
        """Posting invalid data to group field does not create an object."""
        parent_group = factories.GroupFactory.create()
        child_group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": "foo",
            },
        )
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
        child_group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"child_group": child_group.pk, "role": "foo"},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertIn("required", form.errors["parent_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_child_group(self):
        """Posting blank data to the child_group field does not create an object."""
        parent_group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"parent_group": parent_group.pk, "role": "foo"},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("child_group", form.errors.keys())
        self.assertIn("required", form.errors["child_group"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_post_blank_data_role(self):
        """Posting blank data to the role field does not create an object."""
        parent_group = factories.GroupFactory.create(name="parent")
        child_group = factories.GroupFactory.create(name="child")
        request = self.factory.post(
            self.get_url(),
            {"parent_group": parent_group.pk, "child_group": child_group.pk},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_a_group_to_itself_member(self):
        """Cannot create a GroupGroupMembership object where the parent and child are the same group."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": group.pk,
                "child_group": group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("add a group to itself", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_a_group_to_itself_admin(self):
        """Cannot create a GroupGroupMembership object where the parent and child are the same group."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": group.pk,
                "child_group": group.pk,
                "role": models.GroupGroupMembership.ADMIN,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("add a group to itself", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_cant_add_circular_relationship(self):
        """Cannot create a GroupGroupMembership object that makes a cirular relationship."""
        grandparent = factories.GroupFactory.create()
        parent = factories.GroupFactory.create()
        child = factories.GroupFactory.create()
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
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("circular", form.non_field_errors()[0])
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)

    def test_cannot_add_child_group_if_parent_not_managed_by_app(self):
        """Cannot add a child group to a parent group if the parent group is not managed by the app."""
        parent_group = factories.GroupFactory.create(
            name="group-1", is_managed_by_app=False
        )
        child_group = factories.GroupFactory.create(name="group-2")
        request = self.factory.post(
            self.get_url(),
            {
                "parent_group": parent_group.pk,
                "child_group": child_group.pk,
                "role": models.GroupGroupMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("parent_group", form.errors.keys())
        self.assertEqual(
            form.errors["parent_group"][0],
            forms.GroupGroupMembershipForm.error_not_admin_of_parent_group,
        )
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        parent_group = factories.GroupFactory.create()
        child_group = factories.GroupFactory.create()
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

    @skip("AnVIL API issue")
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

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:group_group_membership:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.GroupGroupMembershipTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.GroupGroupMembershipFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.GroupGroupMembershipFactory.create_batch(2)
        request = self.factory.get(self.get_url())
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

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:group_group_membership:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupGroupMembershipDelete.as_view()

    def test_view_status_code(self):
        """Returns a successful status code for an existing object."""
        object = factories.GroupGroupMembershipFactory.create()
        request = self.factory.get(self.get_url(object.pk))
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url(1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=1)

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        object = factories.GroupGroupMembershipFactory.create(
            role=models.GroupGroupMembership.MEMBER
        )
        url = (
            self.entry_point
            + "/api/groups/"
            + object.parent_group.name
            + "/"
            + object.role
            + "/"
            + object.child_group.get_email()
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)
        responses.assert_call_count(url, 1)

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.GroupGroupMembershipFactory.create()
        other_object = factories.GroupGroupMembershipFactory.create()
        url = (
            self.entry_point
            + "/api/groups/"
            + object.parent_group.name
            + "/"
            + object.role
            + "/"
            + object.child_group.get_email()
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        self.assertQuerysetEqual(
            models.GroupGroupMembership.objects.all(),
            models.GroupGroupMembership.objects.filter(pk=other_object.pk),
        )
        responses.assert_call_count(url, 1)

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.GroupGroupMembershipFactory.create()
        url = (
            self.entry_point
            + "/api/groups/"
            + object.parent_group.name
            + "/"
            + object.role
            + "/"
            + object.child_group.get_email()
        )
        responses.add(responses.DELETE, url, status=self.api_success_code)
        # Need to use the client instead of RequestFactory to check redirection url.
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("anvil_project_manager:group_group_membership:list")
        )
        responses.assert_call_count(url, 1)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.GroupGroupMembershipFactory.create()
        url = (
            self.entry_point
            + "/api/groups/"
            + object.parent_group.name
            + "/"
            + object.role
            + "/"
            + object.child_group.get_email()
        )
        responses.add(
            responses.DELETE,
            url,
            status=500,
            json={"message": "group group membership delete test error"},
        )
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
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

    @skip("AnVIL API issue")
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

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_project_manager:group_account_membership:detail", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.GroupAccountMembershipFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.GroupAccountMembershipFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)


class GroupAccountMembershipCreateTest(AnVILAPIMockTestMixin, TestCase):

    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:group_account_membership:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object_member(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create(name="test-group")
        account = factories.AccountFactory.create(email="email@example.com")
        url = (
            self.entry_point + "/api/groups/" + group.name + "/MEMBER/" + account.email
        )
        responses.add(responses.PUT, url, status=self.api_success_code)
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupAccountMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupAccountMembership)
        self.assertEqual(new_object.role, models.GroupAccountMembership.MEMBER)
        responses.assert_call_count(url, 1)

    def test_can_create_an_object_admin(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create(name="test-group")
        account = factories.AccountFactory.create(email="email@example.com")
        url = self.entry_point + "/api/groups/" + group.name + "/ADMIN/" + account.email
        responses.add(responses.PUT, url, status=self.api_success_code)
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.GroupAccountMembership.objects.latest("pk")
        self.assertIsInstance(new_object, models.GroupAccountMembership)
        self.assertEqual(new_object.role, models.GroupAccountMembership.ADMIN)
        responses.assert_call_count(url, 1)

    def test_redirects_to_list(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        group = factories.GroupFactory.create()
        account = factories.AccountFactory.create()
        url = self.entry_point + "/api/groups/" + group.name + "/ADMIN/" + account.email
        responses.add(responses.PUT, url, status=self.api_success_code)
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.ADMIN,
            },
        )
        self.assertRedirects(
            response, reverse("anvil_project_manager:group_account_membership:list")
        )
        responses.assert_call_count(url, 1)

    def test_cannot_create_duplicate_object_with_same_role(self):
        """Cannot create a second GroupAccountMembership object for the same account and group with the same role."""
        group = factories.GroupFactory.create()
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
        group = factories.GroupFactory.create()
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
        group_1 = factories.GroupFactory.create(name="test-group-1")
        group_2 = factories.GroupFactory.create(name="test-group-2")
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
        request = self.factory.post(
            self.get_url(),
            {
                "group": group_2.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        responses.assert_call_count(url, 1)

    def test_can_add_two_accounts_to_one_group(self):
        group = factories.GroupFactory.create()
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
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account_2.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        responses.assert_call_count(url, 1)

    def test_invalid_input_account(self):
        """Posting invalid data to account field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": 1,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
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
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_invalid_input_role(self):
        """Posting invalid data to group field does not create an object."""
        group = factories.GroupFactory.create()
        account = factories.AccountFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"group": group.pk, "account": account.pk, "role": "foo"},
        )
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
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_post_blank_data_account(self):
        """Posting blank data to the account field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"group": group.pk, "role": models.GroupAccountMembership.MEMBER},
        )
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
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(), {"group": group.pk, "account": account.pk}
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors.keys())
        self.assertIn("required", form.errors["role"][0])
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_cannot_add_account_if_group_not_managed_by_app(self):
        """Cannot add an account to a group if the group is not managed by the app."""
        group = factories.GroupFactory.create(is_managed_by_app=False)
        account = factories.AccountFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "account": account.pk,
                "role": models.GroupAccountMembership.MEMBER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertEqual(
            form.errors["group"][0],
            forms.GroupAccountMembershipForm.error_not_admin_of_group,
        )
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        group = factories.GroupFactory.create()
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

    @skip("AnVIL API issue")
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

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:group_account_membership:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.GroupAccountMembershipTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.GroupAccountMembershipFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.GroupAccountMembershipFactory.create_batch(2)
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class GroupAccountMembershipDeleteTest(AnVILAPIMockTestMixin, TestCase):

    api_success_code = 204

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_project_manager:group_account_membership:delete", args=args
        )

    def get_view(self):
        """Return the view being tested."""
        return views.GroupAccountMembershipDelete.as_view()

    def test_view_status_code(self):
        """Returns a successful status code for an existing object."""
        object = factories.GroupAccountMembershipFactory.create()
        request = self.factory.get(self.get_url(object.pk))
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url(1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=1)

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
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)
        responses.assert_call_count(url, 1)

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
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
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
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("anvil_project_manager:group_account_membership:list")
        )
        responses.assert_call_count(url, 1)

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
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
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

    @skip("AnVIL API issue")
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

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspace_group_access:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessDetail.as_view()

    def test_view_status_code_with_existing_object(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.WorkspaceGroupAccessFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.WorkspaceGroupAccessFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)


class WorkspaceGroupAccessCreateTest(AnVILAPIMockTestMixin, TestCase):

    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()

    def get_mock_response(self, status_code, message="mock message"):
        return mock.Mock(status_code=status_code, json=lambda: {"message": message})

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspace_group_access:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessCreate.as_view()

    def test_status_code(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_has_form_in_context(self):
        """Response includes a form."""
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)

    def test_can_create_an_object_reader(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create(name="test-group")
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
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access, models.WorkspaceGroupAccess.READER)
        responses.assert_call_count(url, 1)

    def test_can_create_an_object_writer(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create()
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
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.WRITER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access, models.WorkspaceGroupAccess.WRITER)
        responses.assert_call_count(url, 1)

    def test_can_create_an_object_owner(self):
        """Posting valid data to the form creates an object."""
        group = factories.GroupFactory.create()
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
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.OWNER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        new_object = models.WorkspaceGroupAccess.objects.latest("pk")
        self.assertIsInstance(new_object, models.WorkspaceGroupAccess)
        self.assertEqual(new_object.access, models.WorkspaceGroupAccess.OWNER)
        responses.assert_call_count(url, 1)

    def test_redirects_to_list(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        group = factories.GroupFactory.create()
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
        )
        response = self.client.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.OWNER,
            },
        )
        self.assertRedirects(
            response, reverse("anvil_project_manager:workspace_group_access:list")
        )
        responses.assert_call_count(url, 1)

    def test_cannot_create_duplicate_object_with_same_access(self):
        """Cannot create a second object for the same workspace and group with the same access level."""
        group = factories.GroupFactory.create()
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
            },
        )
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
        group = factories.GroupFactory.create()
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
            },
        )
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
        group_1 = factories.GroupFactory.create(name="test-group-1")
        group_2 = factories.GroupFactory.create(name="test-group-2")
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
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group_2.pk,
                "workspace": workspace.pk,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 2)
        responses.assert_call_count(url, 1)

    def test_can_have_two_groups_for_one_workspace(self):
        group = factories.GroupFactory.create()
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
        )
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace_2.pk,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
        response = self.get_view()(request)
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
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("valid choice", form.errors["group"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_invalid_input_workspace(self):
        """Posting invalid data to workspace field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": 1,
                "access": models.WorkspaceGroupAccess.READER,
            },
        )
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
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {
                "group": group.pk,
                "workspace": workspace.pk,
                "access": "foo",
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("valid choice", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        request = self.factory.post(self.get_url(), {})
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
            },
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors.keys())
        self.assertIn("required", form.errors["group"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_post_blank_data_workspace(self):
        """Posting blank data to the workspace field does not create an object."""
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"group": group.pk, "access": models.WorkspaceGroupAccess.READER},
        )
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
        group = factories.GroupFactory.create()
        request = self.factory.post(
            self.get_url(),
            {"group": group.pk, "workspace": workspace.pk},
        )
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        group = factories.GroupFactory.create()
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

    def get_mock_response(self, status_code, message="mock message"):
        return mock.Mock(status_code=status_code, json=lambda: {"message": message})

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspace_group_access:update", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessUpdate.as_view()

    def test_status_code(self):
        """Returns a successful status code for an existing object pk."""
        obj = factories.WorkspaceGroupAccessFactory.create()
        request = self.factory.get(self.get_url(obj.pk))
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.WorkspaceGroupAccessFactory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)

    def test_can_update_role(self):
        """Can update the role through the view."""
        group = factories.GroupFactory.create(name="test-group")
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
        )
        request = self.factory.post(
            self.get_url(obj.pk),
            {
                "access": models.WorkspaceGroupAccess.WRITER,
            },
        )
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupAccess.WRITER)

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
        )
        response = self.client.post(
            self.get_url(obj.pk),
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
            self.get_url(obj.pk),
            {"access": ""},
        )
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("required", form.errors["access"][0])
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupAccess.READER)

    def test_post_invalid_data_access(self):
        """Posting invalid data to the access field does not update the object."""
        obj = factories.WorkspaceGroupAccessFactory.create(
            access=models.WorkspaceGroupAccess.READER
        )
        request = self.factory.post(
            self.get_url(obj.pk),
            {"access": "foo"},
        )
        response = self.get_view()(request, pk=obj.pk)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("access", form.errors.keys())
        self.assertIn("valid choice", form.errors["access"][0])
        obj.refresh_from_db()
        self.assertEqual(obj.access, models.WorkspaceGroupAccess.READER)

    def test_post_group_pk(self):
        """Posting a group pk has no effect."""
        original_group = factories.GroupFactory.create()
        obj = factories.WorkspaceGroupAccessFactory(
            group=original_group, access=models.WorkspaceGroupAccess.READER
        )
        new_group = factories.GroupFactory.create()
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
        )
        request = self.factory.post(
            self.get_url(obj.pk),
            {
                "group": new_group.pk,
                "access": models.WorkspaceGroupAccess.WRITER,
            },
        )
        response = self.get_view()(request, pk=obj.pk)
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
        )
        request = self.factory.post(
            self.get_url(obj.pk),
            {
                "workspace": new_workspace.pk,
                "access": models.WorkspaceGroupAccess.WRITER,
            },
        )
        response = self.get_view()(request, pk=obj.pk)
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
        response = self.client.post(
            self.get_url(obj.pk),
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

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspace_group_access:list", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessList.as_view()

    def test_view_status_code(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_has_correct_table_class(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.WorkspaceGroupAccessTable
        )

    def test_view_with_no_objects(self):
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.WorkspaceGroupAccessFactory()
        request = self.factory.get(self.get_url())
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.WorkspaceGroupAccessFactory.create_batch(2)
        request = self.factory.get(self.get_url())
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

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_project_manager:workspace_group_access:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceGroupAccessDelete.as_view()

    def test_view_status_code(self):
        """Returns a successful status code for an existing object."""
        object = factories.WorkspaceGroupAccessFactory.create()
        request = self.factory.get(self.get_url(object.pk))
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 200)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url(1))
        with self.assertRaises(Http404):
            self.get_view()(request, pk=1)

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        group = factories.GroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            name="test-workspace", billing_project=billing_project
        )
        object = factories.WorkspaceGroupAccessFactory.create(
            group=group, workspace=workspace
        )
        json_data = [
            {
                "email": object.group.get_email(),
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
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 0)
        responses.assert_call_count(url, 1)

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        object = factories.WorkspaceGroupAccessFactory.create()
        other_object = factories.WorkspaceGroupAccessFactory.create()
        json_data = [
            {
                "email": object.group.get_email(),
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + object.workspace.billing_project.name
            + "/"
            + object.workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        request = self.factory.post(self.get_url(object.pk), {"submit": ""})
        response = self.get_view()(request, pk=object.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.WorkspaceGroupAccess.objects.count(), 1)
        self.assertQuerysetEqual(
            models.WorkspaceGroupAccess.objects.all(),
            models.WorkspaceGroupAccess.objects.filter(pk=other_object.pk),
        )
        responses.assert_call_count(url, 1)

    def test_success_url(self):
        """Redirects to the expected page."""
        object = factories.WorkspaceGroupAccessFactory.create()
        json_data = [
            {
                "email": object.group.get_email(),
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        url = (
            self.entry_point
            + "/api/workspaces/"
            + object.workspace.billing_project.name
            + "/"
            + object.workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        # Need to use the client instead of RequestFactory to check redirection url.
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("anvil_project_manager:workspace_group_access:list")
        )
        responses.assert_call_count(url, 1)

    def test_api_error(self):
        """Shows a message if an AnVIL API error occurs."""
        # Need a client to check messages.
        object = factories.WorkspaceGroupAccessFactory.create()
        url = (
            self.entry_point
            + "/api/workspaces/"
            + object.workspace.billing_project.name
            + "/"
            + object.workspace.name
            + "/acl?inviteUsersNotFound=false"
        )
        responses.add(
            responses.PATCH,
            url,
            status=500,
            json={"message": "workspace group access delete test error"},
        )
        response = self.client.post(self.get_url(object.pk), {"submit": ""})
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
