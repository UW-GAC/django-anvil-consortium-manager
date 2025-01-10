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

from anvil_consortium_manager import anvil_api
from anvil_consortium_manager.models import (
    Account,
    AnVILProjectManagerAccess,
)
from anvil_consortium_manager.tests.factories import (
    AccountFactory,
    BillingProjectFactory,
    DefaultWorkspaceDataFactory,
    GroupAccountMembershipFactory,
    ManagedGroupFactory,
    WorkspaceFactory,
    WorkspaceGroupSharingFactory,
)
from anvil_consortium_manager.tests.utils import AnVILAPIMockTestMixin, TestCase

from .. import forms, models, tables, views
from ..audit import base as base_audit
from ..audit import managed_groups as managed_group_audit
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
        return reverse("anvil_consortium_manager:auditor:billing_projects:all", args=args)

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


class AccountAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the AccountAudit view."""

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
        return reverse("anvil_consortium_manager:auditor:accounts:all", args=args)

    def get_api_url(self, email):
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
        return views.AccountAudit.as_view()

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
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
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

    def test_audit_verified_one_verified(self):
        """audit_verified with one verified record."""
        account = AccountFactory.create()
        api_url = self.get_api_url(account.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=self.get_api_json_response(account.email),
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

    def test_audit_errors_one_verified(self):
        """audit_errors with one verified record."""
        account = AccountFactory.create()
        api_url = self.get_api_url(account.email)
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
        self.assertEqual(len(response.context_data["error_table"].rows), 0)

    def test_audit_ok_is_ok(self):
        """audit_ok when audit_results.ok() is True."""
        account = AccountFactory.create()
        api_url = self.get_api_url(account.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=self.get_api_json_response(account.email),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_ok", response.context_data)
        self.assertEqual(response.context_data["audit_ok"], True)

    def test_audit_ok_is_not_ok(self):
        """audit_ok when audit_results.ok() is True."""
        account = AccountFactory.create()
        api_url = self.get_api_url(account.email)
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


class ManagedGroupAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the ManagedGroupAudit view."""

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
        return reverse("anvil_consortium_manager:auditor:managed_groups:all", args=args)

    def get_api_groups_url(self):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1"

    def get_api_group_json(self, group_name, role):
        """Return json data about groups in the API format."""
        json_data = {
            "groupEmail": group_name + "@firecloud.org",
            "groupName": group_name,
            "role": role,
        }
        return json_data

    def get_api_url_members(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member"

    def get_api_url_admins(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/admin"

    def get_api_json_response_admins(self, emails=[]):
        """Return json data about groups in the API format."""
        return [anvil_api.AnVILAPIClient().auth_session.credentials.service_account_email] + emails

    def get_api_json_response_members(self, emails=[]):
        """Return json data about groups in the API format."""
        return emails

    def get_view(self):
        """Return the view being tested."""
        return views.ManagedGroupAudit.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
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

    def test_template(self):
        """Template loads successfully."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_audit_verified(self):
        """audit_verified is in the context data."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("verified_table", response.context_data)
        self.assertIsInstance(response.context_data["verified_table"], base_audit.VerifiedTable)
        self.assertEqual(len(response.context_data["verified_table"].rows), 0)

    def test_audit_verified_one_record(self):
        """audit_verified with one verified record."""
        group = ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json(group.name, "Admin")],
        )
        # Group membership API call.
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("verified_table", response.context_data)
        self.assertEqual(len(response.context_data["verified_table"].rows), 1)

    def test_audit_errors(self):
        """audit_errors is in the context data."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("error_table", response.context_data)
        self.assertIsInstance(response.context_data["error_table"], base_audit.ErrorTable)
        self.assertEqual(len(response.context_data["error_table"].rows), 0)

    def test_audit_errors_one_record(self):
        """audit_errors with one error record."""
        group = ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            # Error - we are not the admin
            json=[self.get_api_group_json(group.name, "Member")],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("error_table", response.context_data)
        self.assertEqual(len(response.context_data["error_table"].rows), 1)

    def test_audit_not_in_app(self):
        """audit_not_in_app is in the context data."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("not_in_app_table", response.context_data)
        self.assertIsInstance(response.context_data["not_in_app_table"], base_audit.NotInAppTable)
        self.assertEqual(len(response.context_data["not_in_app_table"].rows), 0)

    def test_audit_not_in_app_one_record(self):
        """audit_not_in_app with one record not in app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json("foo", "Admin")],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("not_in_app_table", response.context_data)
        self.assertEqual(len(response.context_data["not_in_app_table"].rows), 1)

    def test_audit_ok_is_ok(self):
        """audit_ok when audit_results.ok() is True."""
        group = ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json(group.name, "Admin")],
        )
        # Group membership API call.
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_ok", response.context_data)
        self.assertEqual(response.context_data["audit_ok"], True)

    def test_audit_ok_is_not_ok(self):
        """audit_ok when audit_results.ok() is False."""
        group = ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            # Error - we are not admin.
            json=[self.get_api_group_json(group.name, "Member")],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_ok", response.context_data)
        self.assertEqual(response.context_data["audit_ok"], False)


class ManagedGroupMembershipAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the ManagedGroupAudit view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.group = ManagedGroupFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:auditor:managed_groups:membership:by_group:all", args=args)

    def get_api_url_members(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member"

    def get_api_url_admins(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/admin"

    def get_api_json_response_admins(self, emails=[]):
        """Return json data about groups in the API format."""
        return [anvil_api.AnVILAPIClient().auth_session.credentials.service_account_email] + emails

    def get_api_json_response_members(self, emails=[]):
        """Return json data about groups in the API format."""
        return emails

    def get_view(self):
        """Return the view being tested."""
        return views.ManagedGroupMembershipAudit.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo"))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo"))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
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

    def test_template(self):
        """Template loads successfully."""
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertEqual(response.status_code, 200)

    def test_table_classes(self):
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("verified_table", response.context_data)
        self.assertIsInstance(response.context_data["verified_table"], base_audit.VerifiedTable)
        self.assertIn("error_table", response.context_data)
        self.assertIsInstance(response.context_data["error_table"], base_audit.ErrorTable)
        self.assertIn("not_in_app_table", response.context_data)
        self.assertIsInstance(response.context_data["not_in_app_table"], base_audit.NotInAppTable)
        self.assertIn("ignored_table", response.context_data)
        self.assertIsInstance(
            response.context_data["ignored_table"], managed_group_audit.ManagedGroupMembershipIgnoredTable
        )

    def test_audit_verified(self):
        """audit_verified is in the context data."""
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("verified_table", response.context_data)
        self.assertIsInstance(response.context_data["verified_table"], base_audit.VerifiedTable)
        self.assertEqual(len(response.context_data["verified_table"].rows), 0)

    def test_audit_verified_one_record(self):
        """audit_verified with one verified record."""
        membership = GroupAccountMembershipFactory.create(group=self.group)
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[membership.account.email]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("verified_table", response.context_data)
        self.assertEqual(len(response.context_data["verified_table"].rows), 1)

    def test_audit_errors(self):
        """audit_errors is in the context data."""
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("error_table", response.context_data)
        self.assertIsInstance(response.context_data["error_table"], base_audit.ErrorTable)
        self.assertEqual(len(response.context_data["error_table"].rows), 0)

    def test_audit_errors_one_record(self):
        """audit_errors with one error record."""
        membership = GroupAccountMembershipFactory.create(group=self.group)
        # Group membership API call.
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[membership.account.email]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("error_table", response.context_data)
        self.assertEqual(len(response.context_data["error_table"].rows), 1)

    def test_audit_not_in_app(self):
        """audit_not_in_app is in the context data."""
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("not_in_app_table", response.context_data)
        self.assertIsInstance(response.context_data["not_in_app_table"], base_audit.NotInAppTable)
        self.assertEqual(len(response.context_data["not_in_app_table"].rows), 0)

    def test_audit_not_in_app_one_record(self):
        """audit_not_in_app with one record not in app."""
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=["foo@bar.com"]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("not_in_app_table", response.context_data)
        self.assertEqual(len(response.context_data["not_in_app_table"].rows), 1)

    def test_audit_not_in_app_link_to_ignore(self):
        """Link to ignore create view appears when a not_in_app result is found."""
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=["foo@bar.com"]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        expected_url = reverse(
            "anvil_consortium_manager:auditor:managed_groups:membership:by_group:ignored:new",
            args=[self.group.name, "foo@bar.com"],
        )
        self.assertIn(expected_url, response.content.decode("utf-8"))

    def test_audit_ignored(self):
        """ignored_table is in the context data."""
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("ignored_table", response.context_data)
        self.assertIsInstance(response.context_data["ignored_table"], base_audit.IgnoredTable)
        self.assertEqual(len(response.context_data["ignored_table"].rows), 0)

    def test_audit_one_ignored_record(self):
        """ignored_table with one ignored record."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create(group=self.group)
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[obj.ignored_email]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("ignored_table", response.context_data)
        self.assertIsInstance(response.context_data["ignored_table"], base_audit.IgnoredTable)
        self.assertEqual(len(response.context_data["ignored_table"].rows), 1)

    def test_audit_one_ignored_record_not_in_anvil(self):
        """The ignored record is not a group member in AnVIL."""
        factories.IgnoredManagedGroupMembershipFactory.create(group=self.group)
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("ignored_table", response.context_data)
        self.assertIsInstance(response.context_data["ignored_table"], base_audit.IgnoredTable)
        self.assertEqual(len(response.context_data["ignored_table"].rows), 1)

    def test_audit_ok_is_ok(self):
        """audit_ok when audit_results.ok() is True."""
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("audit_ok", response.context_data)
        self.assertEqual(response.context_data["audit_ok"], True)

    def test_audit_ok_is_not_ok(self):
        """audit_ok when audit_results.ok() is False."""
        api_url_members = self.get_api_url_members(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=["foo@bar.com"]),
        )
        api_url_admins = self.get_api_url_admins(self.group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.group.name))
        self.assertIn("audit_ok", response.context_data)
        self.assertEqual(response.context_data["audit_ok"], False)

    def test_group_not_managed_by_app(self):
        """Redirects with a message when group is not managed by app."""
        group = ManagedGroupFactory.create(is_managed_by_app=False)
        # Only clients load the template.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(group.name), follow=True)
        self.assertRedirects(response, group.get_absolute_url())
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            str(messages[0]),
            views.ManagedGroupMembershipAudit.message_not_managed_by_app,
        )

    def test_group_does_not_exist_in_app(self):
        """Raises a 404 error with an invalid object pk."""
        ManagedGroupFactory.create()
        request = self.factory.get(self.get_url("foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, slug="foo")


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
        return reverse("anvil_consortium_manager:auditor:managed_groups:membership:by_group:ignored:detail", args=args)

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
            "anvil_consortium_manager:auditor:managed_groups:membership:by_group:ignored:delete",
            args=[obj.group.name, obj.ignored_email],
        )
        self.assertNotContains(response, expected_url)
        expected_url = reverse(
            "anvil_consortium_manager:auditor:managed_groups:membership:by_group:ignored:update",
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
            "anvil_consortium_manager:auditor:managed_groups:membership:by_group:ignored:delete",
            args=[obj.group.name, obj.ignored_email],
        )
        self.assertContains(response, expected_url)
        expected_url = reverse(
            "anvil_consortium_manager:auditor:managed_groups:membership:by_group:ignored:update",
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
        delattr(UserModel, "get_absolute_url")
        self.assertContains(response, "test_profile_testuser2")


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
        return reverse("anvil_consortium_manager:auditor:managed_groups:membership:by_group:ignored:new", args=args)

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

    def test_get_object_exists(self):
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.group.name, obj.ignored_email))
        self.assertRedirects(response, obj.get_absolute_url())

    def test_post_object_exists(self):
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.group.name, obj.ignored_email),
            {
                "group": obj.group.pk,
                "ignored_email": obj.ignored_email,
                "note": fake.sentence(),
            },
        )
        self.assertRedirects(response, obj.get_absolute_url())
        self.assertEqual(models.IgnoredManagedGroupMembership.objects.count(), 1)
        self.assertIn(obj, models.IgnoredManagedGroupMembership.objects.all())


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
        return reverse("anvil_consortium_manager:auditor:managed_groups:membership:by_group:ignored:delete", args=args)

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


class IgnoredManagedGroupMembershipListTest(TestCase):
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
        return reverse("anvil_consortium_manager:auditor:managed_groups:membership:ignored", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.IgnoredManagedGroupMembershipList.as_view()

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
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
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
        self.assertIsInstance(response.context_data["table"], tables.IgnoredManagedGroupMembershipTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.IgnoredManagedGroupMembershipFactory()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.IgnoredManagedGroupMembershipFactory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_filter_group_name_return_no_object(self):
        factories.IgnoredManagedGroupMembershipFactory.create(group__name="foo")
        factories.IgnoredManagedGroupMembershipFactory.create(group__name="bar")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"group__name__icontains": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_group_name_returns_one_object_exact(self):
        instance = factories.IgnoredManagedGroupMembershipFactory.create(group__name="foo")
        factories.IgnoredManagedGroupMembershipFactory.create(group__name="bar")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"group__name__icontains": "foo"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_group_name_returns_one_object_case_insensitive(self):
        instance = factories.IgnoredManagedGroupMembershipFactory.create(group__name="Foo")
        factories.IgnoredManagedGroupMembershipFactory.create(group__name="bar")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"group__name__icontains": "foo"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_group_name_returns_one_object_case_contains(self):
        instance = factories.IgnoredManagedGroupMembershipFactory.create(group__name="foo")
        factories.IgnoredManagedGroupMembershipFactory.create(group__name="bar")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"group__name__icontains": "oo"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_group_name_returns_multiple_objects(self):
        instance_1 = factories.IgnoredManagedGroupMembershipFactory.create(group__name="group1")
        instance_2 = factories.IgnoredManagedGroupMembershipFactory.create(group__name="group2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"group__name__icontains": "group"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)
        self.assertIn(instance_1, response.context_data["table"].data)
        self.assertIn(instance_2, response.context_data["table"].data)

    def test_view_with_filter_email_return_no_object(self):
        factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="foo@test.com")
        factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="bar")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"ignored_email__icontains": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_email_returns_one_object_exact(self):
        instance = factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="foo@test.com")
        factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="bar@test.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"ignored_email__icontains": "foo@test.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_email_returns_one_object_case_insensitive(self):
        instance = factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="Foo@test.com")
        factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="bar@test.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"ignored_email__icontains": "foo@test.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_email_returns_one_object_case_contains(self):
        instance = factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="foo@test.com")
        factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="bar@test.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"ignored_email__icontains": "oo"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_email_returns_multiple_objects(self):
        instance_1 = factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="foo1@test.com")
        instance_2 = factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="foo2@test.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"ignored_email__icontains": "foo"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)
        self.assertIn(instance_1, response.context_data["table"].data)
        self.assertIn(instance_2, response.context_data["table"].data)

    def test_view_with_filter_group_name_and_email(self):
        factories.IgnoredManagedGroupMembershipFactory.create(group__name="abc", ignored_email="foo@test.com")
        instance = factories.IgnoredManagedGroupMembershipFactory.create(
            group__name="def", ignored_email="foo@test.com"
        )
        factories.IgnoredManagedGroupMembershipFactory.create(group__name="def", ignored_email="bar@test.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"group__name__icontains": "def", "ignored_email__icontains": "foo"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)


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
        return reverse("anvil_consortium_manager:auditor:managed_groups:membership:by_group:ignored:update", args=args)

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


class WorkspaceAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the WorkspaceAudit view."""

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
        return reverse("anvil_consortium_manager:auditor:workspaces:all", args=args)

    def get_api_url(self):
        return self.api_client.rawls_entry_point + "/api/workspaces"

    def get_api_workspace_json(self, billing_project_name, workspace_name, access, auth_domains=[]):
        """Return the json dictionary for a single workspace on AnVIL."""
        return {
            "accessLevel": access,
            "workspace": {
                "name": workspace_name,
                "namespace": billing_project_name,
                "authorizationDomain": [{"membersGroupName": x} for x in auth_domains],
                "isLocked": False,
            },
        }

    def get_api_workspace_acl_url(self, billing_project_name, workspace_name):
        return (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
            + "/acl"
        )

    def get_api_workspace_acl_response(self):
        """Return a json for the workspace/acl method where no one else can access."""
        return {
            "acl": {
                self.service_account_email: {
                    "accessLevel": "OWNER",
                    "canCompute": True,
                    "canShare": True,
                    "pending": False,
                }
            }
        }

    def get_api_bucket_options_url(self, billing_project_name, workspace_name):
        return self.api_client.rawls_entry_point + "/api/workspaces/" + billing_project_name + "/" + workspace_name

    def get_api_bucket_options_response(self):
        """Return a json for the workspace/acl method that is not requester pays."""
        return {"bucketOptions": {"requesterPays": False}}

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceAudit.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
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

    def test_template(self):
        """Template loads successfully."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_audit_verified(self):
        """audit_verified is in the context data."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("verified_table", response.context_data)
        self.assertIsInstance(response.context_data["verified_table"], base_audit.VerifiedTable)
        self.assertEqual(len(response.context_data["verified_table"].rows), 0)

    def test_audit_verified_one_record(self):
        """audit_verified with one verified record."""
        workspace = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json(workspace.billing_project.name, workspace.name, "OWNER")],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("verified_table", response.context_data)
        self.assertEqual(len(response.context_data["verified_table"].rows), 1)

    def test_audit_errors(self):
        """audit_errors is in the context data."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("error_table", response.context_data)
        self.assertIsInstance(response.context_data["error_table"], base_audit.ErrorTable)
        self.assertEqual(len(response.context_data["error_table"].rows), 0)

    def test_audit_errors_one_record(self):
        """audit_errors with one error record."""
        workspace = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            # Error - we are not an owner.
            json=[self.get_api_workspace_json(workspace.billing_project.name, workspace.name, "READER")],
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("error_table", response.context_data)
        self.assertEqual(len(response.context_data["error_table"].rows), 1)

    def test_audit_not_in_app(self):
        """audit_not_in_app is in the context data."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("not_in_app_table", response.context_data)
        self.assertIsInstance(response.context_data["not_in_app_table"], base_audit.NotInAppTable)
        self.assertEqual(len(response.context_data["not_in_app_table"].rows), 0)

    def test_audit_not_in_app_one_record(self):
        """audit_not_in_app with one record not in app."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("foo", "bar", "OWNER")],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("not_in_app_table", response.context_data)
        self.assertEqual(len(response.context_data["not_in_app_table"].rows), 1)

    def test_audit_ok_is_ok(self):
        """audit_ok when audit_results.ok() is True."""
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_ok", response.context_data)
        self.assertEqual(response.context_data["audit_ok"], True)

    def test_audit_ok_is_not_ok(self):
        """audit_ok when audit_results.ok() is False."""
        workspace = WorkspaceFactory.create()
        api_url = self.get_api_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            # Error - we are not admin.
            json=[self.get_api_workspace_json(workspace.billing_project.name, workspace.name, "READER")],
        )
        # Response to check workspace bucket options.
        workspace_acl_url = self.get_api_bucket_options_url(workspace.billing_project.name, workspace.name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_bucket_options_response(),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_ok", response.context_data)
        self.assertEqual(response.context_data["audit_ok"], False)


class WorkspaceSharingAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the WorkspaceSharingAudit view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        # Set this variable here because it will include the service account.
        # Tests can update it with the update_api_response method.
        self.api_response = {"acl": {}}
        self.update_api_response(self.service_account_email, "OWNER", can_compute=True, can_share=True)
        # Create a workspace for use in tests.
        self.workspace = WorkspaceFactory.create()
        self.api_url = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + self.workspace.billing_project.name
            + "/"
            + self.workspace.name
            + "/acl"
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:all", args=args)

    def update_api_response(self, email, access, can_compute=False, can_share=False):
        """Return a paired down json for a single ACL, including the service account."""
        self.api_response["acl"].update(
            {
                email: {
                    "accessLevel": access,
                    "canCompute": can_compute,
                    "canShare": can_share,
                    "pending": False,
                }
            }
        )

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceSharingAudit.as_view()

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
        # Group membership API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertEqual(response.status_code, 200)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
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

    def test_template(self):
        """Template loads successfully."""
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertEqual(response.status_code, 200)

    def test_audit_verified(self):
        """audit_verified is in the context data."""
        # Group membership API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("verified_table", response.context_data)
        self.assertIsInstance(response.context_data["verified_table"], base_audit.VerifiedTable)
        self.assertEqual(len(response.context_data["verified_table"].rows), 0)

    def test_audit_verified_one_record(self):
        """audit_verified with one verified record."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        self.update_api_response(access.group.email, "READER")
        # Group membership API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("verified_table", response.context_data)
        self.assertEqual(len(response.context_data["verified_table"].rows), 1)

    def test_audit_errors(self):
        """audit_errors is in the context data."""
        # Group membership API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("error_table", response.context_data)
        self.assertIsInstance(response.context_data["error_table"], base_audit.ErrorTable)
        self.assertEqual(len(response.context_data["error_table"].rows), 0)

    def test_audit_errors_one_record(self):
        """audit_errors with one error record."""
        access = WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        # Different access recorded.
        self.update_api_response(access.group.email, "WRITER")
        # Group membership API call.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("error_table", response.context_data)
        self.assertEqual(len(response.context_data["error_table"].rows), 1)

    def test_audit_not_in_app(self):
        """audit_not_in_app is in the context data."""
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
            # Admin insetad of member.
            # json=self.get_api_group_members_json_response(),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("not_in_app_table", response.context_data)
        self.assertIsInstance(response.context_data["not_in_app_table"], base_audit.NotInAppTable)
        self.assertEqual(len(response.context_data["not_in_app_table"].rows), 0)

    def test_audit_not_in_app_one_record(self):
        """audit_not_in_app with one record not in app."""
        self.update_api_response("foo@bar.com", "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("not_in_app_table", response.context_data)
        self.assertEqual(len(response.context_data["not_in_app_table"].rows), 1)

    def test_audit_not_in_app_link_to_ignore(self):
        """Link to ignore create view appears when a not_in_app result is found."""
        self.update_api_response("foo@bar.com", "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        expected_url = reverse(
            "anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:ignored:new",
            args=[self.workspace.billing_project.name, self.workspace.name, "foo@bar.com"],
        )
        self.assertIn(expected_url, response.content.decode("utf-8"))

    def test_audit_ignored(self):
        """ignored_table is in the context data."""
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("ignored_table", response.context_data)
        self.assertIsInstance(response.context_data["ignored_table"], base_audit.IgnoredTable)
        self.assertEqual(len(response.context_data["ignored_table"].rows), 0)

    def test_audit_one_ignored_record(self):
        """ignored_table with one ignored record."""
        obj = factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.update_api_response(obj.ignored_email, "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("ignored_table", response.context_data)
        self.assertIsInstance(response.context_data["ignored_table"], base_audit.IgnoredTable)
        self.assertEqual(len(response.context_data["ignored_table"].rows), 1)

    def test_audit_one_ignored_record_not_in_anvil(self):
        """The ignored record does not have the workspace shared with them in AnVIL."""
        factories.IgnoredWorkspaceSharingFactory.create(workspace=self.workspace)
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("ignored_table", response.context_data)
        self.assertIsInstance(response.context_data["ignored_table"], base_audit.IgnoredTable)
        self.assertEqual(len(response.context_data["ignored_table"].rows), 1)

    def test_audit_ok_is_ok(self):
        """audit_ok when audit_results.ok() is True."""
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
            # Admin insetad of member.
            # json=self.get_api_group_members_json_response(),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("audit_ok", response.context_data)
        self.assertEqual(response.context_data["audit_ok"], True)

    def test_audit_ok_is_not_ok(self):
        """audit_ok when audit_results.ok() is False."""
        self.update_api_response("foo@bar.com", "READER")
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
            # Not in app
            # json=self.get_api_group_members_json_response(members=["foo@bar.com"]),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name))
        self.assertIn("audit_ok", response.context_data)
        self.assertEqual(response.context_data["audit_ok"], False)

    def test_workspace_does_not_exist_in_app(self):
        """Raises a 404 error with an invalid workspace slug."""
        billing_project = BillingProjectFactory.create()
        request = self.factory.get(self.get_url(billing_project.name, self.workspace.name))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=billing_project.name,
                workspace_slug=self.workspace.name,
            )

    def test_billing_project_does_not_exist_in_app(self):
        """Raises a 404 error with an invalid billing project slug."""
        request = self.factory.get(self.get_url("foo", self.workspace.name))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, billing_project_slug="foo", workspace_slug=self.workspace.name)


class IgnoredWorkspaceSharingDetailTest(TestCase):
    """Tests for the IgnoredWorkspaceSharingDetail view."""

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
        return reverse("anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:ignored:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.IgnoredWorkspaceSharingDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar", "bar@example.com"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar", "bar@example.com"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        self.assertEqual(response.status_code, 200)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
        request = self.factory.get(self.get_url("foo", "bar", "bar@example.com"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo1", "bar", "bar@example.com"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_invalid_obj(self):
        """Raises a 404 error with an invalid object pk."""
        request = self.factory.get(self.get_url("foo1", "bar", "bar@example.com"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request)

    def test_invalid_obj_different_billing_project(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        request = self.factory.get(self.get_url("foo", obj.workspace.name, obj.ignored_email))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request)

    def test_invalid_obj_different_workspace(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        request = self.factory.get(self.get_url(obj.workspace.billing_project.name, "bar", obj.ignored_email))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request)

    def test_invalid_obj_different_email(self):
        """Raises a 404 error with an invalid object pk."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        email = fake.email()
        request = self.factory.get(self.get_url(obj.workspace.billing_project.name, obj.workspace.name, email))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request)

    def test_detail_page_links_staff_view(self):
        """Links to other object detail pages appear correctly when user has staff view permission."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        html = """<a href="{url}">{text}</a>""".format(url=obj.workspace.get_absolute_url(), text=str(obj.workspace))
        self.assertContains(response, html)
        # "Added by" link is tested in a separate test, since not all projects will have an absolute url for the user.
        # Action buttons.
        expected_url = reverse(
            "anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:ignored:delete",
            args=[obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email],
        )
        self.assertNotContains(response, expected_url)
        expected_url = reverse(
            "anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:ignored:update",
            args=[obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email],
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
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(user)
        response = self.client.get(obj.get_absolute_url())
        html = """<a href="{url}">{text}</a>""".format(url=obj.workspace.get_absolute_url(), text=str(obj.workspace))
        self.assertContains(response, html)
        # "Added by" link is tested in a separate test, since not all projects will have an absolute url for the user.
        # Action buttons.
        expected_url = reverse(
            "anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:ignored:delete",
            args=[obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email],
        )
        self.assertContains(response, expected_url)
        expected_url = reverse(
            "anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:ignored:update",
            args=[obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email],
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
        obj = factories.IgnoredWorkspaceSharingFactory.create(added_by=user)
        self.client.force_login(self.user)
        response = self.client.get(obj.get_absolute_url())
        delattr(UserModel, "get_absolute_url")
        self.assertContains(response, "test_profile_testuser2")


class IgnoredWorkspaceSharingCreateTest(TestCase):
    """Tests for the IgnoredWorkspaceSharingCreate view."""

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
        self.workspace = WorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:ignored:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.IgnoredWorkspaceSharingCreate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar", "bar@example.com"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar", "bar@example.com"),
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(self.workspace.billing_project.name, self.workspace.name, "foo@bar.com")
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar", "bar@example.com"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
        request = self.factory.get(self.get_url("foo", "bar", "bar@example.com"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar", "bar@example.com"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name, fake.email()))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.IgnoredWorkspaceSharingForm)

    def test_context_workspace(self):
        """Context contains the workspace."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name, fake.email()))
        self.assertTrue("workspace" in response.context_data)
        self.assertEqual(response.context_data["workspace"], self.workspace)

    def test_context_email(self):
        """Context contains the email."""
        email = fake.email()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name, email))
        self.assertTrue("email" in response.context_data)
        self.assertEqual(response.context_data["email"], email)

    def test_form_hidden_input(self):
        """The proper inputs are hidden in the form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name, fake.email()))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"].fields["workspace"].widget, HiddenInput)
        self.assertIsInstance(response.context_data["form"].fields["ignored_email"].widget, HiddenInput)

    def test_get_initial(self):
        """Initial data is set correctly."""
        email = fake.email()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, self.workspace.name, email))
        initial = response.context_data["form"].initial
        self.assertIn("workspace", initial)
        self.assertEqual(self.workspace, initial["workspace"])
        self.assertIn("ignored_email", initial)
        self.assertEqual(email, initial["ignored_email"])

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name, "my@email.com"),
            {"workspace": self.workspace.pk, "ignored_email": "my@email.com", "note": "foo bar"},
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.IgnoredWorkspaceSharing.objects.latest("pk")
        self.assertIsInstance(new_object, models.IgnoredWorkspaceSharing)
        self.assertEqual(new_object.workspace, self.workspace)
        self.assertEqual(new_object.ignored_email, "my@email.com")
        self.assertEqual(new_object.note, "foo bar")
        self.assertEqual(new_object.added_by, self.user)

    def test_success_message(self):
        """Response includes a success message if successful."""
        email = fake.email()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name, email),
            {
                "workspace": self.workspace.pk,
                "ignored_email": email,
                "note": fake.sentence(),
            },
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.IgnoredWorkspaceSharingCreate.success_message, str(messages[0]))

    def test_success_redirect(self):
        """After successfully creating an object, view redirects to the model's list view."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        email = fake.email()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name, email),
            {
                "workspace": self.workspace.pk,
                "ignored_email": email,
                "note": fake.sentence(),
            },
        )
        obj = models.IgnoredWorkspaceSharing.objects.latest("pk")
        self.assertRedirects(response, obj.get_absolute_url())

    def test_cannot_create_duplicate_object(self):
        """Cannot create a second object for the same group and email."""
        obj = factories.IgnoredWorkspaceSharingFactory.create(note="original note")
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name, obj.ignored_email),
            {"workspace": obj.workspace.pk, "ignored_email": obj.ignored_email, "note": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        # import ipdb; ipdb.set_trace()
        self.assertIn("already exists", form.non_field_errors()[0])
        self.assertQuerySetEqual(
            models.IgnoredWorkspaceSharing.objects.all(),
            models.IgnoredWorkspaceSharing.objects.filter(pk=obj.pk),
        )
        obj.refresh_from_db()
        self.assertEqual(obj.note, "original note")

    def test_get_workspace_not_found_billing_project(self):
        """Raises 404 if group in URL does not exist when posting data."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("foo", self.workspace.name, "test@eaxmple.com"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(models.IgnoredWorkspaceSharing.objects.count(), 0)

    def test_get_workspace_not_found_workspace_name(self):
        """Raises 404 if group in URL does not exist when posting data."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace.billing_project.name, "foo", "test@eaxmple.com"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(models.IgnoredWorkspaceSharing.objects.count(), 0)

    def test_post_workspace_not_found_billing_project(self):
        """Raises 404 if group in URL does not exist when posting data."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url("foo", self.workspace.name, "test@eaxmple.com"),
            {
                "workspace": self.workspace,
                "ignored_email": "test@example.com",
                "note": "a note",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(models.IgnoredWorkspaceSharing.objects.count(), 0)

    def test_post_workspace_not_found_name(self):
        """Raises 404 if group in URL does not exist when posting data."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, "foo", "test@eaxmple.com"),
            {
                "workspace": self.workspace,
                "ignored_email": "test@example.com",
                "note": "a note",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(models.IgnoredWorkspaceSharing.objects.count(), 0)

    def test_invalid_input_email(self):
        """Posting invalid data to role field does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name, "foo"),
            {
                "workspace": self.workspace.pk,
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
        self.assertEqual(models.IgnoredWorkspaceSharing.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name, "foo@bar.com"), {}
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertIn("ignored_email", form.errors.keys())
        self.assertIn("required", form.errors["ignored_email"][0])
        self.assertIn("note", form.errors.keys())
        self.assertIn("required", form.errors["note"][0])
        self.assertEqual(models.IgnoredWorkspaceSharing.objects.count(), 0)

    def test_post_blank_data_workspace(self):
        """Posting blank data to the group field does not create an object."""
        email = fake.email(0)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name, email),
            {
                "ignored_email": email,
                "note": "foo bar",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertEqual(models.IgnoredWorkspaceSharing.objects.count(), 0)

    def test_post_blank_data_email(self):
        """Posting blank data to the account field does not create an object."""
        email = fake.email(0)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name, email),
            {
                "workspace": self.workspace.pk,
                # "ignored_email": email,
                "note": "foo bar",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("ignored_email", form.errors.keys())
        self.assertIn("required", form.errors["ignored_email"][0])
        self.assertEqual(models.IgnoredWorkspaceSharing.objects.count(), 0)

    def test_post_blank_data_note(self):
        """Posting blank data to the note field does not create an object."""
        email = fake.email(0)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace.billing_project.name, self.workspace.name, email),
            {
                "workspace": self.workspace.pk,
                "ignored_email": email,
                # "note": "foo bar",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("note", form.errors.keys())
        self.assertIn("required", form.errors["note"][0])
        self.assertEqual(models.IgnoredWorkspaceSharing.objects.count(), 0)

    def test_get_object_exists(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email)
        )
        self.assertRedirects(response, obj.get_absolute_url())

    def test_post_object_exists(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email),
            {
                "workspace": obj.workspace.pk,
                "ignored_email": obj.ignored_email,
                "note": fake.sentence(),
            },
        )
        self.assertRedirects(response, obj.get_absolute_url())
        self.assertEqual(models.IgnoredWorkspaceSharing.objects.count(), 1)
        self.assertIn(obj, models.IgnoredWorkspaceSharing.objects.all())


class IgnoredWorkspaceSharingUpdateTest(TestCase):
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
        return reverse("anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:ignored:update", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.IgnoredWorkspaceSharingUpdate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar", "email"))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar", "email"))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email)
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar", "email"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
        request = self.factory.get(self.get_url("foo", "bar", "email"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar", "email"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_object_does_not_exist(self):
        """Raises Http404 if object does not exist."""
        request = self.factory.get(self.get_url("foo", "bar", "test@example.com"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email)
        )
        self.assertTrue("form" in response.context_data)
        # Form is auto-generated by the view, so don't check the class.

    def test_can_modify_note(self):
        """Can set the note when creating a billing project."""
        obj = factories.IgnoredWorkspaceSharingFactory.create(note="original note")
        # Need a client for messages.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email),
            {"note": "new note"},
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.note, "new note")

    def test_success_message(self):
        """Response includes a success message if successful."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email),
            {"note": "new note"},
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.IgnoredWorkspaceSharingUpdate.success_message, str(messages[0]))

    def test_redirects_to_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email),
            {"note": "new note"},
        )
        self.assertRedirects(response, obj.get_absolute_url())

    def test_missing_note(self):
        obj = factories.IgnoredWorkspaceSharingFactory.create(note="original note")
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email),
            {},
        )
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
        obj = factories.IgnoredWorkspaceSharingFactory.create(note="original note")
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email), {"note": ""}
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("note", form.errors)
        self.assertEqual(len(form.errors["note"]), 1)
        self.assertIn("required", form.errors["note"][0])
        obj.refresh_from_db()
        self.assertEqual(obj.note, "original note")


class IgnoredWorkspaceSharingDeleteTest(TestCase):
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
        return reverse("anvil_consortium_manager:auditor:workspaces:sharing:by_workspace:ignored:delete", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.IgnoredWorkspaceSharingDelete.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar", "email"))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar", "email"))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email)
        )
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url("foo", "bar", "email"))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_with_limited_view_permission(self):
        """Raises permission denied if user has limited view permission."""
        user = User.objects.create_user(username="test-limited", password="test-limited")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
        request = self.factory.get(self.get_url("foo", "bar", "email"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar", "email"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_with_invalid_pk(self):
        """Returns a 404 when the object doesn't exist."""
        request = self.factory.get(self.get_url("foo", "bar", "email"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request)

    def test_view_deletes_object(self):
        """Posting submit to the form successfully deletes the object."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email), {"submit": ""}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Account.objects.count(), 0)
        # History is added.
        self.assertEqual(obj.history.count(), 2)
        self.assertEqual(obj.history.latest().history_type, "-")

    def test_success_message(self):
        """Response includes a success message if successful."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        DefaultWorkspaceDataFactory.create(workspace=obj.workspace)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email),
            {"submit": ""},
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.IgnoredWorkspaceSharingDelete.success_message, str(messages[0]))

    def test_only_deletes_specified_pk(self):
        """View only deletes the specified pk."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        DefaultWorkspaceDataFactory.create(workspace=obj.workspace)
        other_obj = factories.IgnoredWorkspaceSharingFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.IgnoredWorkspaceSharing.objects.count(), 1)
        self.assertQuerySetEqual(
            Account.objects.all(),
            Account.objects.filter(pk=other_obj.pk),
        )

    def test_success_url(self):
        """Redirects to the expected page."""
        obj = factories.IgnoredWorkspaceSharingFactory.create()
        DefaultWorkspaceDataFactory.create(workspace=obj.workspace)
        # Need to use the client instead of RequestFactory to check redirection url.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.workspace.billing_project.name, obj.workspace.name, obj.ignored_email),
            {"submit": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, obj.workspace.get_absolute_url())


class IgnoredWorkspaceSharingListTest(TestCase):
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
        return reverse("anvil_consortium_manager:auditor:workspaces:sharing:ignored", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.IgnoredWorkspaceSharingList.as_view()

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
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
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
        self.assertIsInstance(response.context_data["table"], tables.IgnoredWorkspaceSharingTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        factories.IgnoredWorkspaceSharingFactory()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        factories.IgnoredWorkspaceSharingFactory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)

    def test_view_with_filter_workspace_name_return_no_object(self):
        factories.IgnoredWorkspaceSharingFactory.create(workspace__name="foo")
        factories.IgnoredWorkspaceSharingFactory.create(workspace__name="bar")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"workspace__name__icontains": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_workspace_name_returns_one_object_exact(self):
        instance = factories.IgnoredWorkspaceSharingFactory.create(workspace__name="foo")
        factories.IgnoredWorkspaceSharingFactory.create(workspace__name="bar")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"workspace__name__icontains": "foo"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_workspace_name_returns_one_object_case_insensitive(self):
        instance = factories.IgnoredWorkspaceSharingFactory.create(workspace__name="Foo")
        factories.IgnoredWorkspaceSharingFactory.create(workspace__name="bar")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"workspace__name__icontains": "foo"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_workspace_name_returns_one_object_case_contains(self):
        instance = factories.IgnoredWorkspaceSharingFactory.create(workspace__name="foo")
        factories.IgnoredWorkspaceSharingFactory.create(workspace__name="bar")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"workspace__name__icontains": "oo"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_workspace_name_returns_multiple_objects(self):
        instance_1 = factories.IgnoredWorkspaceSharingFactory.create(workspace__name="workspace1")
        instance_2 = factories.IgnoredWorkspaceSharingFactory.create(workspace__name="workspace2")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"workspace__name__icontains": "workspace"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)
        self.assertIn(instance_1, response.context_data["table"].data)
        self.assertIn(instance_2, response.context_data["table"].data)

    def test_view_with_filter_email_return_no_object(self):
        factories.IgnoredWorkspaceSharingFactory.create(ignored_email="foo@test.com")
        factories.IgnoredWorkspaceSharingFactory.create(ignored_email="bar")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"ignored_email__icontains": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_filter_email_returns_one_object_exact(self):
        instance = factories.IgnoredWorkspaceSharingFactory.create(ignored_email="foo@test.com")
        factories.IgnoredWorkspaceSharingFactory.create(ignored_email="bar@test.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"ignored_email__icontains": "foo@test.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_email_returns_one_object_case_insensitive(self):
        instance = factories.IgnoredWorkspaceSharingFactory.create(ignored_email="Foo@test.com")
        factories.IgnoredWorkspaceSharingFactory.create(ignored_email="bar@test.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"ignored_email__icontains": "foo@test.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_email_returns_one_object_case_contains(self):
        instance = factories.IgnoredWorkspaceSharingFactory.create(ignored_email="foo@test.com")
        factories.IgnoredWorkspaceSharingFactory.create(ignored_email="bar@test.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"ignored_email__icontains": "oo"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)

    def test_view_with_filter_email_returns_multiple_objects(self):
        instance_1 = factories.IgnoredWorkspaceSharingFactory.create(ignored_email="foo1@test.com")
        instance_2 = factories.IgnoredWorkspaceSharingFactory.create(ignored_email="foo2@test.com")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"ignored_email__icontains": "foo"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)
        self.assertIn(instance_1, response.context_data["table"].data)
        self.assertIn(instance_2, response.context_data["table"].data)

    def test_view_with_filter_workspace_name_and_email(self):
        factories.IgnoredWorkspaceSharingFactory.create(workspace__name="abc", ignored_email="foo@test.com")
        instance = factories.IgnoredWorkspaceSharingFactory.create(workspace__name="def", ignored_email="foo@test.com")
        factories.IgnoredWorkspaceSharingFactory.create(workspace__name="def", ignored_email="bar@test.com")
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(), {"workspace__name__icontains": "def", "ignored_email__icontains": "foo"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(instance, response.context_data["table"].data)
