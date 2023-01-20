import responses
from django.core.exceptions import ValidationError
from django.test import TestCase
from faker import Faker

from .. import anvil_api, anvil_audit, exceptions, models
from ..adapters.default import DefaultWorkspaceAdapter
from . import factories
from .utils import AnVILAPIMockTestMixin

fake = Faker()


class BillingProjectAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.object = factories.BillingProjectFactory()
        self.url = (
            self.api_client.rawls_entry_point + "/api/billing/v2/" + self.object.name
        )

    def test_anvil_exists_does_exist(self):
        responses.add(responses.GET, self.url, status=200)
        self.assertIs(self.object.anvil_exists(), True)
        responses.assert_call_count(self.url, 1)

    def test_anvil_exists_does_not_exist(self):
        responses.add(
            responses.GET, self.url, status=404, json={"message": "mock message"}
        )
        self.assertIs(self.object.anvil_exists(), False)
        responses.assert_call_count(self.url, 1)


class BillingProjectAnVILImportAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the BillingProject.anvil_import method."""

    def get_api_url(self, billing_project_name):
        return (
            self.api_client.rawls_entry_point
            + "/api/billing/v2/"
            + billing_project_name
        )

    def get_api_json_response(self):
        return {
            "roles": ["User"],
        }

    def test_can_import_billing_project_where_we_are_users(self):
        """A BillingProject is created if there if we are users of the billing project on AnVIL."""
        billing_project_name = "test-billing-project"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name),
            status=200,
            json=self.get_api_json_response(),
        )
        billing_project = models.BillingProject.anvil_import(
            billing_project_name, note="test note"
        )
        # Check values.
        self.assertEqual(billing_project.name, billing_project_name)
        self.assertEqual(billing_project.note, "test note")
        # Check that it was saved.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        # Make sure it's the workspace returned.
        models.BillingProject.objects.get(pk=billing_project.pk)

    def test_cannot_import_billing_project_where_we_are_not_users(self):
        """No BillingProjects are created if there if we are not users of the billing project."""
        billing_project_name = "test-billing-project"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name),
            status=404,
            json={"message": "other error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            models.BillingProject.anvil_import(billing_project_name)
        # Check no objects were saved.
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_billing_project_already_exists_in_db(self):
        """No new BillingProjects are created when the billing project already exists in the database."""
        billing_project = factories.BillingProjectFactory.create()
        # No API calls should be made.
        with self.assertRaises(exceptions.AnVILAlreadyImported):
            models.BillingProject.anvil_import(billing_project.name)
        # Check that it was not saved.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        self.assertEqual(
            models.BillingProject.objects.get(pk=billing_project.pk), billing_project
        )

    def test_anvil_import_api_internal_error(self):
        """No BillingProjects are created if there is an internal error from the AnVIL API."""
        billing_project_name = "test-billing-project"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name),
            status=500,  # error response code.
            json={"message": "error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            models.BillingProject.anvil_import(billing_project_name)
        # Check that no objects were saved.
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_api_error_other(self):
        """No BillingProjects are created if there is some other error from the AnVIL API."""
        billing_project_name = "test-billing-project"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name),
            status=499,  # error response code.
            json={"message": "error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            models.BillingProject.anvil_import(billing_project_name)
        # Check that no objects were saved.
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_invalid_billing_project_name(self):
        """No BillingProjects are created if the billing project name is invalid."""
        # No API calls should be made.
        with self.assertRaises(ValidationError):
            models.BillingProject.anvil_import("test billing project")
        # Check that no objects were saved.
        self.assertEqual(models.BillingProject.objects.count(), 0)


class BillingProjectAnVILAuditAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the BillingProject.anvil_audit method."""

    def get_api_url(self, billing_project_name):
        return (
            self.api_client.rawls_entry_point
            + "/api/billing/v2/"
            + billing_project_name
        )

    def get_api_json_response(self):
        return {
            "roles": ["User"],
        }

    def test_anvil_audit_no_billing_projects(self):
        """anvil_audit works correct if there are no billing projects in the app."""
        audit_results = models.BillingProject.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.BillingProjectAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_one_billing_project_no_errors(self):
        """anvil_audit works correct if one billing project exists in the app and in AnVIL."""
        billing_project = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url = self.get_api_url(billing_project.name)
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = models.BillingProject.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.BillingProjectAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), {billing_project})
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_one_billing_project_not_on_anvil(self):
        """anvil_audit raises exception with one billing project exists in the app but not on AnVIL."""
        billing_project = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url = self.get_api_url(billing_project.name)
        responses.add(
            responses.GET,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        audit_results = models.BillingProject.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.BillingProjectAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {billing_project: [audit_results.ERROR_NOT_IN_ANVIL]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_two_billing_projects_no_errors(self):
        """anvil_audit returns None if there are two billing projects and both exist on AnVIL."""
        billing_project_1 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        responses.add(
            responses.GET,
            api_url_1,
            status=200,
            json=self.get_api_json_response(),
        )
        billing_project_2 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        responses.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = models.BillingProject.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.BillingProjectAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(
            audit_results.get_verified(), {billing_project_1, billing_project_2}
        )
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url_1, 1)
        responses.assert_call_count(api_url_2, 1)

    def test_anvil_audit_two_billing_projects_first_not_on_anvil(self):
        """anvil_audit raises exception if two billing projects exist in the app but the first is not on AnVIL."""
        billing_project_1 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        responses.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        billing_project_2 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        responses.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = models.BillingProject.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.BillingProjectAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), {billing_project_2})
        self.assertEqual(
            audit_results.get_errors(),
            {billing_project_1: [audit_results.ERROR_NOT_IN_ANVIL]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url_1, 1)
        responses.assert_call_count(api_url_2, 1)

    def test_anvil_audit_two_billing_projects_both_missing(self):
        """anvil_audit raises exception if there are two billing projects that exist in the app but not in AnVIL."""
        billing_project_1 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        responses.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        billing_project_2 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        responses.add(
            responses.GET,
            api_url_2,
            status=404,
            json={"message": "other error"},
        )
        audit_results = models.BillingProject.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.BillingProjectAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {
                billing_project_1: [audit_results.ERROR_NOT_IN_ANVIL],
                billing_project_2: [audit_results.ERROR_NOT_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url_1, 1)
        responses.assert_call_count(api_url_2, 1)

    def test_anvil_audit_ignore_not_has_app_has_user(self):
        """anvil_audit does not check AnVIL about billing projects that do not have the app as a user."""
        factories.BillingProjectFactory.create(has_app_as_user=False)
        # No API calls made.
        audit_results = models.BillingProject.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.BillingProjectAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())


class UserEmailEntryAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the UserEmailEntry model that call the AnVIL API."""

    def setUp(self):
        super().setUp()
        self.object = factories.UserEmailEntryFactory.create()
        self.api_url = (
            self.api_client.sam_entry_point + "/api/users/v1/" + self.object.email
        )

    def get_api_user_json_response(self, email):
        id = fake.bothify(text="#" * 21)
        return {
            "googleSubjectId": id,
            "userEmail": email,
            "userSubjectId": id,
        }

    def test_anvil_account_exists_does_exist(self):
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.get_api_user_json_response(self.object.email),
        )
        self.assertIs(self.object.anvil_account_exists(), True)
        responses.assert_call_count(self.api_url, 1)

    def test_anvil_account_exists_does_not_exist(self):
        responses.add(
            responses.GET, self.api_url, status=404, json={"message": "mock message"}
        )
        self.assertIs(self.object.anvil_account_exists(), False)
        responses.assert_call_count(self.api_url, 1)

    def test_anvil_account_exists_associated_with_group(self):
        responses.add(responses.GET, self.api_url, status=204)
        self.assertIs(self.object.anvil_account_exists(), False)
        responses.assert_call_count(self.api_url, 1)


class AccountAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.object = factories.AccountFactory.create()
        self.api_url = (
            self.api_client.sam_entry_point + "/api/users/v1/" + self.object.email
        )

    def get_api_remove_from_group_url(self, group_name):
        return (
            self.api_client.firecloud_entry_point
            + "/api/groups/"
            + group_name
            + "/MEMBER/"
            + self.object.email
        )

    def get_api_user_json_response(self, email):
        id = fake.bothify(text="#" * 21)
        return {
            "googleSubjectId": id,
            "userEmail": email,
            "userSubjectId": id,
        }

    def test_anvil_exists_does_exist(self):
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.get_api_user_json_response(self.object.email),
        )
        self.assertIs(self.object.anvil_exists(), True)
        responses.assert_call_count(self.api_url, 1)

    def test_anvil_exists_does_not_exist(self):
        responses.add(
            responses.GET, self.api_url, status=404, json={"message": "mock message"}
        )
        self.assertIs(self.object.anvil_exists(), False)
        responses.assert_call_count(self.api_url, 1)

    def test_anvil_exists_email_is_group(self):
        responses.add(responses.GET, self.api_url, status=204)
        self.assertIs(self.object.anvil_exists(), False)
        responses.assert_call_count(self.api_url, 1)

    def test_anvil_remove_from_groups_in_no_groups(self):
        """anvil_remove_from_groups succeeds if the account is not in any groups."""
        # Make sure it doesn't fail and that there are no API calls.
        self.object.anvil_remove_from_groups()

    def test_anvil_remove_from_groups_in_one_group(self):
        """anvil_remove_from_groups succeeds if the account is in one group."""
        membership = factories.GroupAccountMembershipFactory.create(account=self.object)
        group = membership.group
        remove_from_group_url = self.get_api_remove_from_group_url(group.name)
        responses.add(responses.DELETE, remove_from_group_url, status=204)
        self.object.anvil_remove_from_groups()
        # The membership was removed.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        responses.assert_call_count(remove_from_group_url, 1)

    def test_anvil_remove_from_groups_in_two_groups(self):
        """anvil_remove_from_groups succeeds if the account is in two groups."""
        memberships = factories.GroupAccountMembershipFactory.create_batch(
            2, account=self.object
        )
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(group_1.name)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(group_2.name)
        responses.add(responses.DELETE, remove_from_group_url_1, status=204)
        responses.add(responses.DELETE, remove_from_group_url_2, status=204)
        self.object.anvil_remove_from_groups()
        # The membership was removed.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        responses.assert_call_count(remove_from_group_url_1, 1)
        responses.assert_call_count(remove_from_group_url_2, 1)

    def test_anvil_remove_from_groups_api_failure(self):
        """anvil_remove_from_groups does not remove group memberships if any API call failed."""
        factories.GroupAccountMembershipFactory.create_batch(2, account=self.object)
        group_1 = self.object.groupaccountmembership_set.all()[0].group
        group_2 = self.object.groupaccountmembership_set.all()[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(group_1.name)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(group_2.name)
        responses.add(responses.DELETE, remove_from_group_url_1, status=204)
        responses.add(
            responses.DELETE,
            remove_from_group_url_2,
            status=409,
            json={"message": "api error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_remove_from_groups()
        # No memberships were removed.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        responses.assert_call_count(remove_from_group_url_1, 1)
        responses.assert_call_count(remove_from_group_url_2, 1)

    def test_deactivate_no_groups(self):
        """deactivate properly sets the status field if the account is not in any groups."""
        # Make sure it doesn't fail and that there are no API calls.
        self.object.deactivate()
        self.object.refresh_from_db()
        self.assertEqual(self.object.status, self.object.INACTIVE_STATUS)

    def test_deactivate_one_group(self):
        """deactivate succeeds if the account is in one group."""
        membership = factories.GroupAccountMembershipFactory.create(account=self.object)
        group = membership.group
        remove_from_group_url = self.get_api_remove_from_group_url(group.name)
        responses.add(responses.DELETE, remove_from_group_url, status=204)
        self.object.deactivate()
        self.object.refresh_from_db()
        self.assertEqual(self.object.status, self.object.INACTIVE_STATUS)
        # The membership was not removed from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        # The URL was called.
        responses.assert_call_count(remove_from_group_url, 1)

    def test_deactivate_two_groups(self):
        """deactivate succeeds if the account is in two groups."""
        memberships = factories.GroupAccountMembershipFactory.create_batch(
            2, account=self.object
        )
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(group_1.name)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(group_2.name)
        responses.add(responses.DELETE, remove_from_group_url_1, status=204)
        responses.add(responses.DELETE, remove_from_group_url_2, status=204)
        self.object.deactivate()
        self.object.refresh_from_db()
        self.assertEqual(self.object.status, self.object.INACTIVE_STATUS)
        # The memberships were not removed.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        # API was called.
        responses.assert_call_count(remove_from_group_url_1, 1)
        responses.assert_call_count(remove_from_group_url_2, 1)

    def test_reactivate_no_groups(self):
        """reactivate properly sets the status field if the account is not in any groups."""
        # Make sure it doesn't fail and that there are no API calls.
        self.object.status = self.object.INACTIVE_STATUS
        self.object.save()
        self.object.reactivate()
        self.object.refresh_from_db()
        self.assertEqual(self.object.status, self.object.ACTIVE_STATUS)

    def test_reactivate_one_group(self):
        """reactivate succeeds if the account is in one group."""
        self.object.status = self.object.INACTIVE_STATUS
        self.object.save()
        membership = factories.GroupAccountMembershipFactory.create(account=self.object)
        group = membership.group
        add_to_group_url = self.get_api_remove_from_group_url(group.name)
        responses.add(responses.PUT, add_to_group_url, status=204)
        self.object.reactivate()
        self.object.refresh_from_db()
        self.assertEqual(self.object.status, self.object.ACTIVE_STATUS)
        # The membership was not removed from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        # The URL was called.
        responses.assert_call_count(add_to_group_url, 1)

    def test_reactivate_two_groups(self):
        """reactivate succeeds if the account is in two groups."""
        self.object.status = self.object.INACTIVE_STATUS
        self.object.save()
        memberships = factories.GroupAccountMembershipFactory.create_batch(
            2, account=self.object
        )
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        add_to_group_url_1 = self.get_api_remove_from_group_url(group_1.name)
        add_to_group_url_2 = self.get_api_remove_from_group_url(group_2.name)
        responses.add(responses.PUT, add_to_group_url_1, status=204)
        responses.add(responses.PUT, add_to_group_url_2, status=204)
        self.object.reactivate()
        self.object.refresh_from_db()
        self.assertEqual(self.object.status, self.object.ACTIVE_STATUS)
        # The memberships were not removed.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        # API was called.
        responses.assert_call_count(add_to_group_url_1, 1)
        responses.assert_call_count(add_to_group_url_2, 1)


class AccountAnVILAuditAnVILAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the Account.anvil_audit method."""

    def get_api_url(self, email):
        return self.api_client.sam_entry_point + "/api/users/v1/" + email

    def get_api_json_response(self, email):
        id = fake.bothify(text="#" * 21)
        return {
            "googleSubjectId": id,
            "userEmail": email,
            "userSubjectId": id,
        }

    def test_anvil_audit_no_accounts(self):
        """anvil_audit works correct if there are no Accounts in the app."""
        audit_results = models.Account.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.AccountAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_one_account_no_errors(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(account.email)
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=self.get_api_json_response(account.email),
        )
        audit_results = models.Account.anvil_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), {account})
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_one_account_not_on_anvil(self):
        """anvil_audit raises exception if one billing project exists in the app but not on AnVIL."""
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(account.email)
        responses.add(
            responses.GET,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        audit_results = models.Account.anvil_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(), {account: [audit_results.ERROR_NOT_IN_ANVIL]}
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_two_accounts_no_errors(self):
        """anvil_audit returns None if if two accounts exist in both the app and AnVIL."""
        account_1 = factories.AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        responses.add(
            responses.GET,
            api_url_1,
            status=200,
            json=self.get_api_json_response(account_1.email),
        )
        account_2 = factories.AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        responses.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(account_2.email),
        )
        audit_results = models.Account.anvil_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([account_1, account_2]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url_1, 1)
        responses.assert_call_count(api_url_2, 1)

    def test_anvil_audit_two_accounts_first_not_on_anvil(self):
        """anvil_audit raises exception if two accounts exist in the app but the first is not not on AnVIL."""
        account_1 = factories.AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        responses.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        account_2 = factories.AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        responses.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(account_2.email),
        )
        audit_results = models.Account.anvil_audit()
        self.assertEqual(audit_results.get_verified(), set([account_2]))
        self.assertFalse(audit_results.ok())
        self.assertEqual(
            audit_results.get_errors(), {account_1: [audit_results.ERROR_NOT_IN_ANVIL]}
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url_1, 1)
        responses.assert_call_count(api_url_2, 1)

    def test_anvil_audit_two_accounts_both_missing(self):
        """anvil_audit raises exception if there are two accounts that exist in the app but not in AnVIL."""
        account_1 = factories.AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        responses.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        account_2 = factories.AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        responses.add(
            responses.GET,
            api_url_2,
            status=404,
            json={"message": "other error"},
        )
        audit_results = models.Account.anvil_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {
                account_1: [audit_results.ERROR_NOT_IN_ANVIL],
                account_2: [audit_results.ERROR_NOT_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url_1, 1)
        responses.assert_call_count(api_url_2, 1)

    def test_anvil_audit_deactivated_account(self):
        """anvil_audit does not check AnVIL about accounts that are deactivated."""
        account = factories.AccountFactory.create()
        account.deactivate()
        # No API calls made.
        audit_results = models.Account.anvil_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())


class ManagedGroupAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        self.object = factories.ManagedGroupFactory()
        self.api_url_exists = (
            self.api_client.sam_entry_point + "/api/groups/v1/" + self.object.name
        )
        self.api_url_create = (
            self.api_client.sam_entry_point + "/api/groups/v1/" + self.object.name
        )
        self.api_url_delete = (
            self.api_client.sam_entry_point + "/api/groups/v1/" + self.object.name
        )

    def test_anvil_exists_does_exist(self):
        responses.add(
            responses.GET, self.api_url_exists, status=200, json=self.object.get_email()
        )
        self.assertIs(self.object.anvil_exists(), True)
        responses.assert_call_count(self.api_url_exists, 1)

    def test_anvil_exists_does_not_exist(self):
        responses.add(
            responses.GET,
            self.api_url_exists,
            status=404,
            json={"message": "mock message"},
        )
        self.assertIs(self.object.anvil_exists(), False)
        responses.assert_call_count(self.api_url_exists, 1)

    def test_anvil_exists_internal_error(self):
        responses.add(
            responses.GET,
            self.api_url_exists,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_exists()
        responses.assert_call_count(self.api_url_exists, 1)

    def test_anvil_create_successful(self):
        responses.add(
            responses.POST,
            self.api_url_create,
            status=201,
            json={"message": "mock message"},
        )
        self.object.anvil_create()
        responses.assert_call_count(self.api_url_create, 1)

    def test_anvil_create_already_exists(self):
        """Returns documented response code when a group already exists."""
        responses.add(
            responses.POST,
            self.api_url_create,
            status=409,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_create()
        responses.assert_call_count(self.api_url_create, 1)

    def test_anvil_create_internal_error(
        self,
    ):
        responses.add(
            responses.POST,
            self.api_url_create,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()
        responses.assert_call_count(self.api_url_create, 1)

    def test_anvil_create_other(self):
        responses.add(
            responses.POST,
            self.api_url_create,
            status=499,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        responses.assert_call_count(self.api_url_create, 1)

    def test_anvil_delete_existing(self):
        responses.add(
            responses.DELETE,
            self.api_url_delete,
            status=204,
            json={"message": "mock message"},
        )
        self.object.anvil_delete()
        responses.assert_call_count(self.api_url_delete, 1)

    def test_anvil_delete_forbidden(self):
        responses.add(
            responses.DELETE,
            self.api_url_delete,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()
        responses.assert_call_count(self.api_url_delete, 1)

    def test_anvil_delete_not_found(self):
        responses.add(
            responses.DELETE,
            self.api_url_delete,
            status=404,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        responses.assert_call_count(self.api_url_delete, 1)

    def test_anvil_delete_in_use(self):
        responses.add(
            responses.DELETE,
            self.api_url_delete,
            status=409,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_delete()
        responses.assert_call_count(self.api_url_delete, 1)

    def test_anvil_delete_other(self):
        responses.add(
            responses.DELETE,
            self.api_url_delete,
            status=499,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        responses.assert_call_count(self.api_url_delete, 1)


class ManagedGroupAnVILImportAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests forthe ManagedGroup.anvil_import method."""

    def get_api_url(self):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1"

    def get_api_json_response(self, group_details):
        """Return json data about groups in the API format."""
        json_data = []
        for group_name, role in group_details:
            json_data.append(
                {
                    "groupEmail": group_name + "@firecloud.org",
                    "groupName": group_name,
                    "role": role,
                }
            )
        return json_data

    def test_anvil_import_admin_on_anvil(self):
        group_name = "test-group"
        responses.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=self.get_api_json_response(
                [
                    ("other-member-group", "Member"),
                    ("other-admin-group", "Admin"),
                    (group_name, "Admin"),
                ]
            ),
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.is_managed_by_app, True)
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)

    def test_anvil_import_admin_on_anvil_lowercase(self):
        group_name = "test-group"
        responses.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=self.get_api_json_response(
                [
                    ("other-member-group", "member"),
                    ("other-admin-group", "admin"),
                    (group_name, "admin"),
                ]
            ),
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.is_managed_by_app, True)
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)

    def test_anvil_import_member_on_anviL(self):
        group_name = "test-group"
        responses.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=self.get_api_json_response(
                [
                    ("other-member-group", "Member"),
                    ("other-admin-group", "Admin"),
                    (group_name, "Member"),
                ]
            ),
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.is_managed_by_app, False)
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)

    def test_anvil_import_member_on_anvil_lowercase(self):
        group_name = "test-group"
        responses.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=self.get_api_json_response(
                [
                    ("other-member-group", "member"),
                    ("other-admin-group", "admin"),
                    (group_name, "member"),
                ]
            ),
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.is_managed_by_app, False)
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)

    def test_anvil_import_not_member_or_admin(self):
        group_name = "test-group"
        responses.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            # Specify a different group so that we're not part of the group being imported.
            json=self.get_api_json_response(
                [
                    ("other-member-group", "Member"),
                    ("other-admin-group", "Admin"),
                    ("different-group", "Member"),
                ]
            ),
        )
        with self.assertRaises(exceptions.AnVILNotGroupMemberError):
            models.ManagedGroup.anvil_import(group_name)
        # Check that no group was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)

    def test_anvil_import_group_already_exists_in_django_db(self):
        group = factories.ManagedGroupFactory.create()
        with self.assertRaises(ValidationError):
            models.ManagedGroup.anvil_import(group.name)
        # Check that no new group was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)

    def test_anvil_import_invalid_group_name(self):
        group = factories.ManagedGroupFactory.create(name="an invalid name")
        with self.assertRaises(ValidationError):
            models.ManagedGroup.anvil_import(group.name)
        # Check that no new group was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)

    def test_anvil_import_api_internal_error(self):
        group_name = "test-group"
        responses.add(
            responses.GET,
            self.get_api_url(),
            status=500,
            json={"message": "api error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            models.ManagedGroup.anvil_import(group_name)
        # No object was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)


class ManagedGroupAnVILAuditAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests forthe ManagedGroup.anvil_audit method."""

    def setUp(self):
        super().setUp()
        # Set the auth session service account email here, since the anvil_audit_membership function will need it.
        anvil_api.AnVILAPIClient().auth_session.credentials.service_account_email = (
            fake.email()
        )

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
        return (
            self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member"
        )

    def get_api_url_admins(self, group_name):
        """Return the API url being called by the method."""
        return (
            self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/admin"
        )

    def get_api_json_response_admins(self, emails=[]):
        """Return json data about groups in the API format."""
        return [
            anvil_api.AnVILAPIClient().auth_session.credentials.service_account_email
        ] + emails

    def get_api_json_response_members(self, emails=[]):
        """Return json data about groups in the API format."""
        return emails

    def test_anvil_audit_no_groups(self):
        """anvil_audit works correct if there are no ManagedGroups in the app."""
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_one_group_managed_by_app_no_errors(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json(group.name, "admin")],
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([group]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)
        responses.assert_call_count(api_url_members, 1)
        responses.assert_call_count(api_url_admins, 1)

    def test_anvil_audit_one_group_managed_by_app_lowercase_role(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json(group.name, "admin")],
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([group]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)
        responses.assert_call_count(api_url_members, 1)
        responses.assert_call_count(api_url_admins, 1)

    def test_anvil_audit_one_group_not_managed_by_app_no_errors(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json(group.name, "Member")],
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([group]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_one_group_not_managed_by_app_no_errors_lowercase_role(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json(group.name, "member")],
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([group]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_one_group_not_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app but not on AnVIL."""
        group = factories.ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(), {group: [audit_results.ERROR_NOT_IN_ANVIL]}
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_one_group_admin_in_app_member_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app as an admin but the role on AnVIL is member."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json(group.name, "member")],
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(), {group: [audit_results.ERROR_DIFFERENT_ROLE]}
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_one_group_member_in_app_admin_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app as an member but the role on AnVIL is admin."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json(group.name, "admin")],
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(), {group: [audit_results.ERROR_DIFFERENT_ROLE]}
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_two_groups_no_errors(self):
        """anvil_audit works correctly if if two groups exist in both the app and AnVIL."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_group_json(group_1.name, "admin"),
                self.get_api_group_json(group_2.name, "member"),
            ],
        )
        api_url_members = self.get_api_url_members(group_1.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group_1.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([group_1, group_2]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)
        responses.assert_call_count(api_url_members, 1)
        responses.assert_call_count(api_url_admins, 1)

    def test_anvil_audit_two_groups_json_response_order_does_not_matter(self):
        """Order of groups in the json response does not matter."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_group_json(group_2.name, "member"),
                self.get_api_group_json(group_1.name, "admin"),
            ],
        )
        api_url_members = self.get_api_url_members(group_1.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group_1.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([group_1, group_2]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)
        responses.assert_call_count(api_url_members, 1)
        responses.assert_call_count(api_url_admins, 1)

    def test_anvil_audit_two_groups_first_not_on_anvil(self):
        """anvil_audit raises exception if two groups exist in the app but the first is not not on AnVIL."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json(group_2.name, "admin")],
        )
        api_url_members = self.get_api_url_members(group_2.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group_2.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([group_2]))
        self.assertEqual(
            audit_results.get_errors(), {group_1: [audit_results.ERROR_NOT_IN_ANVIL]}
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)
        responses.assert_call_count(api_url_members, 1)
        responses.assert_call_count(api_url_admins, 1)

    def test_anvil_audit_two_accounts_both_missing(self):
        """anvil_audit raises exception if there are two groups that exist in the app but not in AnVIL."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {
                group_1: [audit_results.ERROR_NOT_IN_ANVIL],
                group_2: [audit_results.ERROR_NOT_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_one_group_member_missing_in_app(self):
        """anvil_audit works correctly if the service account is a member of a group not in the app."""
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json("test-group", "member")],
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set(["test-group"]))
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_one_group_admin_missing_in_app(self):
        """anvil_audit works correctly if the service account is an admin of a group not in the app."""
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json("test-group", "Admin")],
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set(["test-group"]))
        responses.assert_call_count(api_url, 1)

    def test_anvil_audit_two_groups_missing_in_app(self):
        """anvil_audit works correctly if there are two groups in AnVIL that aren't in the app."""
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_group_json("test-group-admin", "Admin"),
                self.get_api_group_json("test-group-member", "Member"),
            ],
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(),
            set(["test-group-admin", "test-group-member"]),
        )
        responses.assert_call_count(api_url, 1)

    def test_fails_membership_audit(self):
        """Error is reported when a group fails the membership audit."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group)
        api_url = self.get_api_groups_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_group_json(group.name, "Admin")],
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = models.ManagedGroup.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.ManagedGroupAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(), {group: [audit_results.ERROR_GROUP_MEMBERSHIP]}
        )
        self.assertEqual(audit_results.get_not_in_app(), set())


class ManagedGroupMembershipAnVILAuditAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests forthe ManagedGroup.anvil_audit method."""

    def setUp(self):
        super().setUp()
        # Set the auth session service account email here, since the anvil_audit_membership function will need it.
        self.service_account_email = fake.email()
        anvil_api.AnVILAPIClient().auth_session.credentials.service_account_email = (
            self.service_account_email
        )

    def get_api_url_members(self, group_name):
        """Return the API url being called by the method."""
        return (
            self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member"
        )

    def get_api_url_admins(self, group_name):
        """Return the API url being called by the method."""
        return (
            self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/admin"
        )

    def get_api_json_response_admins(self, emails=[]):
        """Return json data about groups in the API format."""
        return [self.service_account_email] + emails

    def get_api_json_response_members(self, emails=[]):
        """Return json data about groups in the API format."""
        return emails

    def test_no_members(self):
        """anvil_audit works correctly if this group has no members."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_account_members(self):
        """anvil_audit works correctly if this group has one account member."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[membership.account.email]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([membership]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_account_members(self):
        """anvil_audit works correctly if this group has two account members."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupAccountMembershipFactory.create(group=group)
        membership_2 = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(
                emails=[membership_1.account.email, membership_2.account.email]
            ),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(
            audit_results.get_verified(), set([membership_1, membership_2])
        )
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_account_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has one account member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {membership: [audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_account_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has two account member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupAccountMembershipFactory.create(group=group)
        membership_2 = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {
                membership_1: [audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL],
                membership_2: [audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_account_members_not_in_app(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=["test-member@example.com"]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(), set(["MEMBER: test-member@example.com"])
        )

    def test_two_account_members_not_in_app(self):
        """anvil_audit works correctly if this group has two account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(
                emails=["test-member-1@example.com", "test-member-2@example.com"]
            ),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(),
            set(
                [
                    "MEMBER: test-member-1@example.com",
                    "MEMBER: test-member-2@example.com",
                ]
            ),
        )

    def test_one_account_members_case_insensitive(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, account__email="tEsT-mEmBeR@example.com"
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=["Test-Member@example.com"]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([membership]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set([]))

    def test_one_account_admin(self):
        """anvil_audit works correctly if this group has one account admin."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[membership.account.email]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([membership]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_account_admin(self):
        """anvil_audit works correctly if this group has two account members."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        membership_2 = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(
                emails=[membership_1.account.email, membership_2.account.email]
            ),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(
            audit_results.get_verified(), set([membership_1, membership_2])
        )
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_account_admin_not_in_anvil(self):
        """anvil_audit works correctly if this group has one account member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {membership: [audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_account_admins_not_in_anvil(self):
        """anvil_audit works correctly if this group has two account member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        membership_2 = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {
                membership_1: [audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL],
                membership_2: [audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_account_admin_not_in_app(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=["test-admin@example.com"]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(), set(["ADMIN: test-admin@example.com"])
        )

    def test_two_account_admin_not_in_app(self):
        """anvil_audit works correctly if this group has two account admin not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(
                emails=["test-admin-1@example.com", "test-admin-2@example.com"]
            ),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(),
            set(["ADMIN: test-admin-1@example.com", "ADMIN: test-admin-2@example.com"]),
        )

    def test_one_account_admin_case_insensitive(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group,
            account__email="tEsT-aDmIn@example.com",
            role=models.GroupAccountMembership.ADMIN,
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=["Test-Admin@example.com"]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([membership]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set([]))

    def test_account_different_role_member_in_app_admin_in_anvil(self):
        """anvil_audit works correctly if an account has a different role in AnVIL."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.MEMBER
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[membership.account.email]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {membership: [audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL]},
        )
        self.assertEqual(
            audit_results.get_not_in_app(), set(["ADMIN: " + membership.account.email])
        )

    def test_one_group_members(self):
        """anvil_audit works correctly if this group has one group member."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(
                emails=[membership.child_group.get_email()]
            ),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([membership]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_group_members(self):
        """anvil_audit works correctly if this group has two account members."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        membership_2 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(
                emails=[
                    membership_1.child_group.get_email(),
                    membership_2.child_group.get_email(),
                ]
            ),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(
            audit_results.get_verified(), set([membership_1, membership_2])
        )
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_group_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has one group member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {membership: [audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_group_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has two group member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        membership_2 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {
                membership_1: [audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL],
                membership_2: [audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_group_members_not_in_app(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(
                emails=["test-member@firecloud.org"]
            ),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(), set(["MEMBER: test-member@firecloud.org"])
        )

    def test_two_group_members_not_in_app(self):
        """anvil_audit works correctly if this group has two group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(
                emails=["test-member-1@firecloud.org", "test-member-2@firecloud.org"]
            ),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(),
            set(
                [
                    "MEMBER: test-member-1@firecloud.org",
                    "MEMBER: test-member-2@firecloud.org",
                ]
            ),
        )

    def test_one_group_members_case_insensitive(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, child_group__name="tEsT-mEmBeR"
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(
                emails=["Test-Member@firecloud.org"]
            ),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([membership]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set([]))

    def test_one_group_admin(self):
        """anvil_audit works correctly if this group has one group admin."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(
                emails=[membership.child_group.get_email()]
            ),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([membership]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_group_admin(self):
        """anvil_audit works correctly if this group has two group admin."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        membership_2 = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(
                emails=[
                    membership_1.child_group.get_email(),
                    membership_2.child_group.get_email(),
                ]
            ),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(
            audit_results.get_verified(), set([membership_1, membership_2])
        )
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_group_admin_not_in_anvil(self):
        """anvil_audit works correctly if this group has one group member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {membership: [audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_group_admins_not_in_anvil(self):
        """anvil_audit works correctly if this group has two group member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        membership_2 = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {
                membership_1: [audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL],
                membership_2: [audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_group_admin_not_in_app(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=["test-admin@firecloud.org"]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(), set(["ADMIN: test-admin@firecloud.org"])
        )

    def test_two_group_admin_not_in_app(self):
        """anvil_audit works correctly if this group has two group admin not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(
                emails=["test-admin-1@firecloud.org", "test-admin-2@firecloud.org"]
            ),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(),
            set(
                [
                    "ADMIN: test-admin-1@firecloud.org",
                    "ADMIN: test-admin-2@firecloud.org",
                ]
            ),
        )

    def test_one_group_admin_case_insensitive(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group,
            child_group__name="tEsT-aDmIn",
            role=models.GroupGroupMembership.ADMIN,
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=["Test-Admin@firecloud.org"]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([membership]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set([]))

    def test_group_different_role_member_in_app_admin_in_anvil(self):
        """anvil_audit works correctly if an group has a different role in AnVIL."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.MEMBER
        )
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(emails=[]),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(
                emails=[membership.child_group.get_email()]
            ),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {membership: [audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL]},
        )
        self.assertEqual(
            audit_results.get_not_in_app(),
            set(["ADMIN: " + membership.child_group.get_email()]),
        )

    def test_service_account_is_both_admin_and_member(self):
        """No errors are reported when the service account is both a member and an admin of a group."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        responses.add(
            responses.GET,
            api_url_members,
            status=200,
            json=self.get_api_json_response_members(
                emails=[self.service_account_email]
            ),
        )
        api_url_admins = self.get_api_url_admins(group.name)
        responses.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=self.get_api_json_response_admins(emails=[]),
        )
        audit_results = group.anvil_audit_membership()
        self.assertIsInstance(
            audit_results, anvil_audit.ManagedGroupMembershipAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())


class WorkspaceAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        self.object = factories.WorkspaceFactory()
        self.url_create = self.api_client.rawls_entry_point + "/api/workspaces"
        self.url_workspace = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + self.object.billing_project.name
            + "/"
            + self.object.name
        )

    def test_anvil_exists_does_exist(self):
        responses.add(responses.GET, self.url_workspace, status=200)
        self.assertIs(self.object.anvil_exists(), True)
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_exists_does_not_exist(self):
        responses.add(
            responses.GET,
            self.url_workspace,
            status=404,
            json={"message": "mock message"},
        )
        self.assertIs(self.object.anvil_exists(), False)
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_exists_forbidden(self):
        responses.add(
            responses.GET,
            self.url_workspace,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_exists()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_exists_internal_error(self):
        responses.add(
            responses.GET,
            self.url_workspace,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_exists()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_create_successful(self):
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=201,
            match=[responses.matchers.json_params_matcher(json)],
        )
        self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_bad_request(self):
        """Returns documented response code when workspace already exists."""
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=400,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_forbidden(self):
        """Returns documented response code when a workspace can't be created."""
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=403,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_404(self):
        """Returns documented response code when a workspace can't be created."""
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=404,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_already_exists(self):
        """Returns documented response code when a workspace already exists."""
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=409,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_422(self):
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=422,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_internal_error(self):
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=500,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_other(self):
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=404,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_one_auth_domain_success(self):
        """Returns documented response code when trying to create a workspace with a valid auth domain."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.object.authorization_domains.add(auth_domain)
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
            "authorizationDomain": [{"membersGroupName": auth_domain.name}],
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=201,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_two_auth_domains_success(self):
        """Returns documented response code when trying to create a workspace with two valid auth domains."""
        auth_domain_1 = factories.ManagedGroupFactory.create(name="auth1")
        auth_domain_2 = factories.ManagedGroupFactory.create(name="auth2")
        self.object.authorization_domains.add(auth_domain_1)
        self.object.authorization_domains.add(auth_domain_2)
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
            "authorizationDomain": [
                {"membersGroupName": auth_domain_1.name},
                {"membersGroupName": auth_domain_2.name},
            ],
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=201,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_create_one_auth_domain_error(self):
        """Returns documented response code when trying to create a workspace with a valid auth domain."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.object.authorization_domains.add(auth_domain)
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
            "authorizationDomain": [{"membersGroupName": auth_domain.name}],
        }
        responses.add(
            responses.POST,
            self.url_create,
            status=400,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.object.anvil_create()
        responses.assert_call_count(self.url_create, 1)

    def test_anvil_delete_existing(self):
        responses.add(responses.DELETE, self.url_workspace, status=202)
        self.object.anvil_delete()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_delete_forbidden(self):
        responses.add(
            responses.DELETE,
            self.url_workspace,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_delete_not_found(self):
        responses.add(
            responses.DELETE,
            self.url_workspace,
            status=404,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_delete_in_use(self):
        responses.add(
            responses.DELETE,
            self.url_workspace,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()
        responses.assert_call_count(self.url_workspace, 1)

    def test_anvil_delete_other(self):
        responses.add(
            responses.DELETE,
            self.url_workspace,
            status=499,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        responses.assert_call_count(self.url_workspace, 1)


class WorkspaceAnVILCloneTest(AnVILAPIMockTestMixin, TestCase):
    """Tests of the Workspace.anvil_clone method."""

    def setUp(self):
        super().setUp()
        self.workspace = factories.WorkspaceFactory.create()

    def get_api_url(self, billing_project_name, workspace_name):
        return (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
            + "/clone"
        )

    def get_api_json_response(self, billing_project_name, workspace_name):
        """Return a pared down version of the json response from the AnVIL API with only fields we need."""
        json_data = {
            "name": workspace_name,
            "namespace": billing_project_name,
        }
        return json_data

    def test_can_clone_workspace_no_auth_domain(self):
        """Can clone a workspace with no auth domains."""
        billing_project = factories.BillingProjectFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=201,  # successful response code.
            json=self.get_api_json_response(billing_project.name, "test-workspace"),
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                    }
                )
            ],
        )
        self.workspace.anvil_clone(billing_project, "test-workspace")
        # No new workspaces were created in the app.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace, models.Workspace.objects.all())

    def test_can_clone_workspace_one_auth_domain(self):
        """Can clone a workspace with one auth domain."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.workspace.authorization_domains.add(auth_domain)
        billing_project = factories.BillingProjectFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=201,  # successful response code.
            json=self.get_api_json_response(billing_project.name, "test-workspace"),
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                        "authorizationDomain": [{"membersGroupName": auth_domain.name}],
                    }
                )
            ],
        )
        self.workspace.anvil_clone(billing_project, "test-workspace")

    def test_can_clone_workspace_two_auth_domains(self):
        """Can clone a workspace with two auth domains."""
        auth_domain_1 = factories.ManagedGroupFactory.create()
        auth_domain_2 = factories.ManagedGroupFactory.create()
        self.workspace.authorization_domains.add(auth_domain_1, auth_domain_2)
        billing_project = factories.BillingProjectFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=201,  # successful response code.
            json=self.get_api_json_response(billing_project.name, "test-workspace"),
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                        "authorizationDomain": [
                            {"membersGroupName": auth_domain_1.name},
                            {"membersGroupName": auth_domain_2.name},
                        ],
                    }
                )
            ],
        )
        self.workspace.anvil_clone(billing_project, "test-workspace")

    def test_can_clone_workspace_add_one_auth_domain(self):
        """Can clone a workspace and add one auth domain."""
        auth_domain = factories.ManagedGroupFactory.create()
        billing_project = factories.BillingProjectFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=201,  # successful response code.
            json=self.get_api_json_response(billing_project.name, "test-workspace"),
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                        "authorizationDomain": [{"membersGroupName": auth_domain.name}],
                    }
                )
            ],
        )
        # import ipdb; ipdb.set_trace()
        self.workspace.anvil_clone(
            billing_project,
            "test-workspace",
            authorization_domains=[auth_domain],
        )

    def test_can_clone_workspace_add_two_auth_domains(self):
        """Can clone a workspace and add one auth domain."""
        auth_domain_1 = factories.ManagedGroupFactory.create()
        auth_domain_2 = factories.ManagedGroupFactory.create()
        billing_project = factories.BillingProjectFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=201,  # successful response code.
            json=self.get_api_json_response(billing_project.name, "test-workspace"),
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                        "authorizationDomain": [
                            {"membersGroupName": auth_domain_1.name},
                            {"membersGroupName": auth_domain_2.name},
                        ],
                    }
                )
            ],
        )
        self.workspace.anvil_clone(
            billing_project,
            "test-workspace",
            authorization_domains=[auth_domain_1, auth_domain_2],
        )

    def test_can_clone_workspace_one_auth_domain_add_one_auth_domain(self):
        """Can clone a workspace with one auth domain and add another auth domain."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.workspace.authorization_domains.add(auth_domain)
        new_auth_domain = factories.ManagedGroupFactory.create()
        billing_project = factories.BillingProjectFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=201,  # successful response code.
            json=self.get_api_json_response(billing_project.name, "test-workspace"),
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                        "authorizationDomain": [
                            {"membersGroupName": auth_domain.name},
                            {"membersGroupName": new_auth_domain.name},
                        ],
                    }
                )
            ],
        )
        self.workspace.anvil_clone(
            billing_project,
            "test-workspace",
            authorization_domains=[new_auth_domain],
        )

    def test_can_clone_workspace_one_auth_domain_add_two_auth_domains(self):
        """Can clone a workspace with one auth domain and add another auth domain."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.workspace.authorization_domains.add(auth_domain)
        new_auth_domain_1 = factories.ManagedGroupFactory.create()
        new_auth_domain_2 = factories.ManagedGroupFactory.create()
        billing_project = factories.BillingProjectFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=201,  # successful response code.
            json=self.get_api_json_response(billing_project.name, "test-workspace"),
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                        "authorizationDomain": [
                            {"membersGroupName": auth_domain.name},
                            {"membersGroupName": new_auth_domain_1.name},
                            {"membersGroupName": new_auth_domain_2.name},
                        ],
                    }
                )
            ],
        )
        self.workspace.anvil_clone(
            billing_project,
            "test-workspace",
            authorization_domains=[new_auth_domain_1, new_auth_domain_2],
        )

    def test_can_clone_workspace_one_auth_domain_add_same_auth_domain(self):
        """Can clone a workspace with one auth domain and add the same auth domain."""
        auth_domain = factories.ManagedGroupFactory.create()
        self.workspace.authorization_domains.add(auth_domain)
        billing_project = factories.BillingProjectFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=201,  # successful response code.
            json=self.get_api_json_response(billing_project.name, "test-workspace"),
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                        "authorizationDomain": [{"membersGroupName": auth_domain.name}],
                    }
                )
            ],
        )
        self.workspace.anvil_clone(
            billing_project,
            "test-workspace",
            authorization_domains=[auth_domain],
        )

    def test_error_cloning_workspace_into_billing_project_where_app_is_not_user(self):
        """Error when cloning a workspace into a billing project where the app is not a user."""
        billing_project = factories.BillingProjectFactory.create(has_app_as_user=False)
        # No API call exected.
        with self.assertRaises(ValueError) as e:
            self.workspace.anvil_clone(billing_project, "test-workspace")
        self.assertIn("has_app_as_user", str(e.exception))
        # No new workspace was created.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace, models.Workspace.objects.all())

    def test_error_workspace_already_exists_in_anvil_but_not_in_app(self):
        """Error when the workspace to be cloned already exists in AnVIL but is not in the app."""
        billing_project = factories.BillingProjectFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=409,  # already exists
            json={"message": "other"},
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                    }
                )
            ],
        )
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.workspace.anvil_clone(billing_project, "test-workspace")
        # No new workspace was created.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace, models.Workspace.objects.all())

    def test_error_workspace_does_not_exist_in_anvil(self):
        """Error the workspace to clone does not exist on AnVIL."""
        billing_project = factories.BillingProjectFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=404,  # already exists
            json={"message": "other"},
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                    }
                )
            ],
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.workspace.anvil_clone(billing_project, "test-workspace")
        # No new workspace was created.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace, models.Workspace.objects.all())

    def test_error_authorization_domain_exists_in_app_but_not_on_anvil(self):
        """Error when the authorization domain exists in the app but not on AnVIL."""
        billing_project = factories.BillingProjectFactory.create()
        new_auth_domain = factories.ManagedGroupFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=404,  # resource not found
            json={"message": "other"},
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                        "authorizationDomain": [
                            {"membersGroupName": new_auth_domain.name}
                        ],
                    }
                )
            ],
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.workspace.anvil_clone(
                billing_project,
                "test-workspace",
                authorization_domains=[new_auth_domain],
            )
        # No new workspace was created.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace, models.Workspace.objects.all())

    def test_other_api_error(self):
        """Error when the response is an error for an unknown reason."""
        billing_project = factories.BillingProjectFactory.create()
        # Add response.
        responses.add(
            responses.POST,
            self.get_api_url(self.workspace.billing_project.name, self.workspace.name),
            status=500,  # other
            json={"message": "other"},
            match=[
                responses.matchers.json_params_matcher(
                    {
                        "namespace": billing_project.name,
                        "name": "test-workspace",
                        "attributes": {},
                    }
                )
            ],
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.workspace.anvil_clone(billing_project, "test-workspace")
        # No new workspace was created.
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertIn(self.workspace, models.Workspace.objects.all())


class WorkspaceAnVILImportAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the Workspace.anvil_import method."""

    def get_billing_project_api_url(self, billing_project_name):
        return (
            self.api_client.rawls_entry_point
            + "/api/billing/v2/"
            + billing_project_name
        )

    def get_api_url(self, billing_project_name, workspace_name):
        return (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
        )

    def get_api_json_response(
        self, billing_project, workspace, access="OWNER", auth_domains=[]
    ):
        """Return a pared down version of the json response from the AnVIL API with only fields we need."""
        json_data = {
            "accessLevel": access,
            "owners": [],
            "workspace": {
                "authorizationDomain": [{"membersGroupName": g} for g in auth_domains],
                "name": workspace,
                "namespace": billing_project,
            },
        }
        return json_data

    def test_anvil_import_billing_project_already_exists_in_django_db(self):
        """Can import a workspace if we are user of the billing project and already exists in Django."""
        """A workspace can be imported from AnVIL if we are owners and if the billing project exists."""
        workspace_name = "test-workspace"
        billing_project = factories.BillingProjectFactory.create()
        # No API call for billing projects.
        responses.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # Check workspace values.
        self.assertEqual(workspace.billing_project, billing_project)
        self.assertEqual(workspace.name, workspace_name)
        # Check that it was saved.
        self.assertEqual(models.Workspace.objects.count(), 1)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)
        # No additional billing projects were created.
        self.assertEqual(models.BillingProject.objects.count(), 1)

    def test_anvil_import_with_note(self):
        """Sets note if specified when importing."""
        workspace_name = "test-workspace"
        billing_project = factories.BillingProjectFactory.create()
        # No API call for billing projects.
        responses.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            DefaultWorkspaceAdapter().get_type(),
            note="test note",
        )
        # Check workspace values.
        self.assertEqual(workspace.billing_project, billing_project)
        self.assertEqual(workspace.name, workspace_name)
        self.assertEqual(workspace.note, "test note")
        # Check that it was saved.
        self.assertEqual(models.Workspace.objects.count(), 1)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)

    def test_anvil_import_billing_project_does_not_exist_in_django_db(self):
        """Can import a workspace if we are user of the billing project but it does not exist in Django yet."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        # Response from checking the billing project.
        responses.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,
        )
        # Response from checking the workspace.
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        workspace = models.Workspace.anvil_import(
            billing_project_name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # A billing project was created.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        billing_project = models.BillingProject.objects.get()
        self.assertEqual(billing_project.name, billing_project_name)
        self.assertEqual(billing_project.has_app_as_user, True)
        # Check workspace values.
        self.assertEqual(workspace.billing_project, billing_project)
        self.assertEqual(workspace.name, workspace_name)
        # Check that it was saved.
        self.assertEqual(models.Workspace.objects.count(), 1)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)

    def test_anvil_import_not_users_of_billing_group(self):
        """Can import a workspace if we are not users of the billing project and it does not exist in Django yet."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        # Response from checking the billing project.
        responses.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=404,  # billing project does not exist.
            json={"message": "other"},
        )
        # Response from checking the workspace.
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        workspace = models.Workspace.anvil_import(
            billing_project_name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # A billing project was created.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        billing_project = models.BillingProject.objects.get()
        self.assertEqual(billing_project.name, billing_project_name)
        self.assertEqual(billing_project.has_app_as_user, False)
        # Check workspace values.
        self.assertEqual(workspace.billing_project, billing_project)
        self.assertEqual(workspace.name, workspace_name)
        # Check that it was saved.
        self.assertEqual(models.Workspace.objects.count(), 1)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)

    def test_anvil_import_not_owners_of_workspace(self):
        """Cannot import a workspace if we are not owners of it and the billing project doesn't exist in Django yet."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        # No billing project API calls.
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(
                billing_project_name, workspace_name, access="READER"
            ),
        )
        with self.assertRaises(exceptions.AnVILNotWorkspaceOwnerError):
            models.Workspace.anvil_import(
                billing_project_name,
                workspace_name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # Check workspace values.
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        # No billing project was created.
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_not_owners_of_workspace_billing_project_exists(self):
        """Cannot import a workspace if we are not owners of the workspace but the billing project exists."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace_name = "test-workspace"
        # No billing project API calls.
        responses.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(
                billing_project.name, workspace_name, access="READER"
            ),
        )
        with self.assertRaises(exceptions.AnVILNotWorkspaceOwnerError):
            models.Workspace.anvil_import(
                billing_project.name,
                workspace_name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # Check workspace values.
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        # Same billing project.
        self.assertEqual(models.BillingProject.objects.latest("pk"), billing_project)

    def test_anvil_import_no_access_to_anvil_workspace(self):
        """A workspace cannot be imported from AnVIL if we do not have access."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        # No API call for billing projects.
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=404,  # successful response code.
            json={
                "message": billing_project_name
                + "/"
                + workspace_name
                + " does not exist or you do not have permission to use it"
            },
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            models.Workspace.anvil_import(
                billing_project_name,
                workspace_name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # Check workspace values.
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_no_access_to_anvil_workspace_billing_project_exist(self):
        """A workspace cannot be imported from AnVIL if we do not have access but the BillingProject is in Django."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace_name = "test-workspace"
        # No API call for billing projects.
        responses.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=404,  # successful response code.
            json={
                "message": billing_project.name
                + "/"
                + workspace_name
                + " does not exist or you do not have permission to use it"
            },
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            models.Workspace.anvil_import(
                billing_project.name,
                workspace_name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # Check workspace values.
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.latest("pk"), billing_project)

    def test_anvil_import_workspace_exists_in_django_db(self):
        """Does not import a workspace if it already exists in Django."""
        workspace = factories.WorkspaceFactory.create()
        # No API calls should be made.
        with self.assertRaises(exceptions.AnVILAlreadyImported):
            models.Workspace.anvil_import(
                workspace.billing_project.name,
                workspace.name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # No additional objects were created.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        self.assertEqual(models.Workspace.objects.count(), 1)

    def test_anvil_import_api_internal_error_workspace_call(self):
        """No workspaces are created if there is an internal error from the AnVIL API for the workspace call."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=500,
            json={"message": "error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            models.Workspace.anvil_import(
                billing_project_name,
                workspace_name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_api_error_other_workspace_call(self):
        """No workspaces are created if there is some other error from the AnVIL API for the workspace call."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=499,
            json={"message": "error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            models.Workspace.anvil_import(
                billing_project_name,
                workspace_name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_api_internal_error_billing_project_call(self):
        """No workspaces are created if there is an internal error from the AnVIL API for the billing project call."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        # Error in billing project call.
        responses.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=500,  # error
            json={"message": "error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            models.Workspace.anvil_import(
                billing_project_name,
                workspace_name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_api_error_other_billing_project_call(self):
        """No workspaces are created if there is another error from the AnVIL API for the billing project call."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        # Error in billing project call.
        responses.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=499,
            json={"message": "error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            models.Workspace.anvil_import(
                billing_project_name,
                workspace_name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_invalid_billing_project_name(self):
        """No workspaces are created if the billing project name is invalid."""
        with self.assertRaises(ValidationError):
            models.Workspace.anvil_import(
                "test billing project",
                "test-workspace",
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_invalid_workspace_name(self):
        """No workspaces are created if the workspace name is invalid."""
        # No API calls.
        with self.assertRaises(ValidationError):
            models.Workspace.anvil_import(
                "test-billing-project",
                "test workspace",
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # # Check that no objects were saved.
        self.assertEqual(models.Workspace.objects.count(), 0)
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_different_billing_project_same_workspace_name(self):
        """Can import a workspace in a different billing project with the same name as another workspace."""
        workspace_name = "test-workspace"
        other_billing_project = factories.BillingProjectFactory.create(
            name="billing-project-1"
        )
        factories.WorkspaceFactory.create(
            billing_project=other_billing_project, name=workspace_name
        )
        billing_project_name = "billing-project-2"
        responses.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,  # successful response code.
        )
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        workspace = models.Workspace.anvil_import(
            billing_project_name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # A billing project was created and that the previous billing project exists.
        self.assertEqual(models.BillingProject.objects.count(), 2)
        billing_project = models.BillingProject.objects.latest("pk")
        self.assertEqual(billing_project.name, billing_project_name)
        # Check workspace.
        self.assertEqual(models.Workspace.objects.count(), 2)
        self.assertEqual(workspace.billing_project, billing_project)
        self.assertEqual(workspace.name, workspace_name)

    def test_anvil_import_same_billing_project_different_workspace_name(self):
        """Can import a workspace in the same billing project with with a different name as another workspace."""
        workspace_name = "test-workspace-2"
        billing_project = factories.BillingProjectFactory.create()
        factories.WorkspaceFactory.create(
            billing_project=billing_project, name="test-workspace-1"
        )
        # No billing project API calls.
        responses.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # No new billing projects were created.
        self.assertEqual(models.BillingProject.objects.count(), 1)
        # Check workspace.
        self.assertEqual(models.Workspace.objects.count(), 2)
        self.assertEqual(workspace.billing_project, billing_project)
        self.assertEqual(workspace.name, workspace_name)

    def test_anvil_import_one_auth_group_member_does_not_exist_in_django(self):
        """Imports an auth group that the app is a member of for a workspace."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace_name = "test-workspace"
        # Response for workspace query.
        workspace_url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
            responses.GET,
            workspace_url,
            status=200,  # successful response code.
            json=self.get_api_json_response(
                billing_project.name, workspace_name, auth_domains=["auth-group"]
            ),
        )
        # Response for group query.
        group_url = self.api_client.sam_entry_point + "/api/groups/v1"
        responses.add(
            responses.GET,
            group_url,
            status=200,
            # Assume we are not members since we didn't create the group ourselves.
            json=[
                {
                    "groupEmail": "auth-group@firecloud.org",
                    "groupName": "auth-group",
                    "role": "Member",
                }
            ],
        )
        # A workspace was created.
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertEqual(workspace.name, workspace_name)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)
        # The group was imported.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        group = models.ManagedGroup.objects.latest("pk")
        self.assertEqual(group.name, "auth-group")
        self.assertEqual(group.is_managed_by_app, False)
        # The group was marked as an auth group of the workspace.
        self.assertEqual(workspace.authorization_domains.count(), 1)
        self.assertEqual(workspace.authorization_domains.get(), group)
        responses.assert_call_count(workspace_url, 1)
        responses.assert_call_count(group_url, 1)

    def test_anvil_import_one_auth_group_exists_in_django(self):
        """Imports a workspace with an auth group that already exists in the app with app as member."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace_name = "test-workspace"
        group = factories.ManagedGroupFactory.create(name="auth-group")
        # Response for workspace query.
        workspace_url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
            responses.GET,
            workspace_url,
            status=200,  # successful response code.
            json=self.get_api_json_response(
                billing_project.name, workspace_name, auth_domains=["auth-group"]
            ),
        )
        # A workspace was created.
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertEqual(workspace.name, workspace_name)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)
        # No new groups were imported.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        chk = models.ManagedGroup.objects.latest("pk")
        self.assertEqual(chk, group)
        # The group was marked as an auth group of the workspace.
        self.assertEqual(workspace.authorization_domains.count(), 1)
        self.assertEqual(workspace.authorization_domains.get(), group)
        responses.assert_call_count(workspace_url, 1)

    def test_anvil_import_one_auth_group_admin_does_not_exist_in_django(self):
        """Imports a workspace with an auth group that the app is a member."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace_name = "test-workspace"
        # Response for workspace query.
        workspace_url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
            responses.GET,
            workspace_url,
            status=200,  # successful response code.
            json=self.get_api_json_response(
                billing_project.name, workspace_name, auth_domains=["auth-group"]
            ),
        )
        # Response for group query.
        group_url = self.api_client.sam_entry_point + "/api/groups/v1"
        responses.add(
            responses.GET,
            group_url,
            status=200,
            # Assume we are not members since we didn't create the group ourselves.
            json=[
                {
                    "groupEmail": "auth-group@firecloud.org",
                    "groupName": "auth-group",
                    "role": "Admin",
                }
            ],
        )
        # A workspace was created.
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertEqual(workspace.name, workspace_name)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)
        # The group was imported.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        group = models.ManagedGroup.objects.latest("pk")
        self.assertEqual(group.name, "auth-group")
        self.assertEqual(group.is_managed_by_app, True)
        # The group was marked as an auth group of the workspace.
        self.assertEqual(workspace.authorization_domains.count(), 1)
        self.assertEqual(workspace.authorization_domains.get(), group)
        responses.assert_call_count(workspace_url, 1)
        responses.assert_call_count(group_url, 1)

    def test_anvil_import_two_auth_groups(self):
        """Imports two auth groups for a workspace."""
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace_name = "test-workspace"
        # Response for workspace query.
        workspace_url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
            responses.GET,
            workspace_url,
            status=200,  # successful response code.
            json=self.get_api_json_response(
                billing_project.name,
                workspace_name,
                auth_domains=["auth-member", "auth-admin"],
            ),
        )
        # Response for group query.
        group_url = self.api_client.sam_entry_point + "/api/groups/v1"
        responses.add(
            responses.GET,
            group_url,
            status=200,
            # Assume we are not members since we didn't create the group ourselves.
            json=[
                {
                    "groupEmail": "auth-member@firecloud.org",
                    "groupName": "auth-member",
                    "role": "Member",
                },
                {
                    "groupEmail": "auth-admin@firecloud.org",
                    "groupName": "auth-admin",
                    "role": "Admin",
                },
            ],
        )
        # A workspace was created.
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertEqual(workspace.name, workspace_name)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)
        # Both groups were imported.
        self.assertEqual(models.ManagedGroup.objects.count(), 2)
        member_group = models.ManagedGroup.objects.get(name="auth-member")
        self.assertEqual(member_group.is_managed_by_app, False)
        admin_group = models.ManagedGroup.objects.get(name="auth-admin")
        self.assertEqual(admin_group.is_managed_by_app, True)
        # The groups were marked as an auth domain of the workspace.
        self.assertEqual(workspace.authorization_domains.count(), 2)
        self.assertIn(member_group, workspace.authorization_domains.all())
        self.assertIn(admin_group, workspace.authorization_domains.all())
        responses.assert_call_count(workspace_url, 1)
        responses.assert_call_count(group_url, 2)

    def test_api_internal_error_group_call(self):
        """Nothing is added when there is an API error on the /api/groups call."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        # Response for billing project query.
        billing_project_url = self.get_billing_project_api_url(billing_project_name)
        responses.add(
            responses.GET, billing_project_url, status=200  # successful response code.
        )
        # Response for workspace query.
        workspace_url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            workspace_url,
            status=200,  # successful response code.
            json=self.get_api_json_response(
                billing_project_name, workspace_name, auth_domains=["auth-group"]
            ),
        )
        # Response for group query.
        group_url = self.api_client.sam_entry_point + "/api/groups/v1"
        responses.add(
            responses.GET,
            group_url,
            status=500,
            # Assume we are not members since we didn't create the group ourselves.
            json={"message": "group error"},
        )
        # A workspace was created.
        with self.assertRaises(anvil_api.AnVILAPIError500):
            models.Workspace.anvil_import(
                billing_project_name,
                workspace_name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # No billing projects were created.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        # No workspaces were imported.
        self.assertEqual(models.Workspace.objects.count(), 0)
        # No groups were imported.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)
        # No auth domains were recorded.
        self.assertEqual(models.WorkspaceAuthorizationDomain.objects.count(), 0)
        responses.assert_call_count(billing_project_url, 1)
        responses.assert_call_count(workspace_url, 1)
        responses.assert_call_count(group_url, 1)


class WorkspaceAnVILAuditAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the Workspace.anvil_audit method."""

    def setUp(self):
        super().setUp()
        self.service_account_email = fake.email()
        anvil_api.AnVILAPIClient().auth_session.credentials.service_account_email = (
            self.service_account_email
        )

    def get_api_url(self):
        return self.api_client.rawls_entry_point + "/api/workspaces"

    def get_api_workspace_json(
        self, billing_project_name, workspace_name, access, auth_domains=[]
    ):
        """Return the json dictionary for a single workspace on AnVIL."""
        return {
            "accessLevel": access,
            "workspace": {
                "name": workspace_name,
                "namespace": billing_project_name,
                "authorizationDomain": [{"membersGroupName": x} for x in auth_domains],
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

    def test_anvil_audit_no_workspaces(self):
        """anvil_audit works correct if there are no Workspaces in the app."""
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        # This does not work with query parameters. I would need to construct the full url to check.
        # responses.assert_call_count(api_url, 1)

    def test_anvil_audit_one_workspace_no_errors(self):
        """anvil_audit works correct if there is one workspace in the app and it exists on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name, workspace.name, "OWNER"
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            workspace.billing_project.name, workspace.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([workspace]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_one_workspace_not_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app but not on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(), {workspace: [audit_results.ERROR_NOT_IN_ANVIL]}
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_one_workspace_owner_in_app_reader_on_anvil(self):
        """anvil_audit raises exception if one workspace exists in the app but the access on AnVIL is READER."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name, workspace.name, "READER"
                )
            ],
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {workspace: [audit_results.ERROR_NOT_OWNER_ON_ANVIL]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_one_workspace_owner_in_app_writer_on_anvil(self):
        """anvil_audit raises exception if one workspace exists in the app but the access on AnVIL is WRITER."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name, workspace.name, "WRITER"
                )
            ],
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {workspace: [audit_results.ERROR_NOT_OWNER_ON_ANVIL]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_two_workspaces_no_errors(self):
        """anvil_audit returns None if if two workspaces exist in both the app and AnVIL."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace_1.billing_project.name, workspace_1.name, "OWNER"
                ),
                self.get_api_workspace_json(
                    workspace_2.billing_project.name, workspace_2.name, "OWNER"
                ),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(
            workspace_1.billing_project.name, workspace_1.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(
            workspace_2.billing_project.name, workspace_2.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([workspace_1, workspace_2]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_two_groups_json_response_order_does_not_matter(self):
        """Order of groups in the json response does not matter."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace_2.billing_project.name, workspace_2.name, "OWNER"
                ),
                self.get_api_workspace_json(
                    workspace_1.billing_project.name, workspace_1.name, "OWNER"
                ),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(
            workspace_1.billing_project.name, workspace_1.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(
            workspace_2.billing_project.name, workspace_2.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([workspace_1, workspace_2]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_two_workspaces_first_not_on_anvil(self):
        """anvil_audit raises exception if two workspaces exist in the app but the first is not not on AnVIL."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace_2.billing_project.name, workspace_2.name, "OWNER"
                ),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(
            workspace_2.billing_project.name, workspace_2.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([workspace_2]))
        self.assertEqual(
            audit_results.get_errors(),
            {workspace_1: [audit_results.ERROR_NOT_IN_ANVIL]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_two_workspaces_first_different_access(self):
        """anvil_audit when if two workspaces exist in the app but access to the first is different on AnVIL."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace_1.billing_project.name, workspace_1.name, "READER"
                ),
                self.get_api_workspace_json(
                    workspace_2.billing_project.name, workspace_2.name, "OWNER"
                ),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(
            workspace_2.billing_project.name, workspace_2.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([workspace_2]))
        self.assertEqual(
            audit_results.get_errors(),
            {workspace_1: [audit_results.ERROR_NOT_OWNER_ON_ANVIL]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_two_workspaces_both_missing_in_anvil(self):
        """anvil_audit when there are two workspaces that exist in the app but not in AnVIL."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[],
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {
                workspace_1: [audit_results.ERROR_NOT_IN_ANVIL],
                workspace_2: [audit_results.ERROR_NOT_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_anvil_audit_one_workspace_missing_in_app(self):
        """anvil_audit returns not_in_app info if a workspace exists on AnVIL but not in the app."""
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp", "test-ws", "OWNER")],
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), {"test-bp/test-ws"})

    def test_anvil_audit_two_workspaces_missing_in_app(self):
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json("test-bp-1", "test-ws-1", "OWNER"),
                self.get_api_workspace_json("test-bp-2", "test-ws-2", "OWNER"),
            ],
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(),
            {"test-bp-1/test-ws-1", "test-bp-2/test-ws-2"},
        )

    def test_different_billing_project(self):
        """A workspace is reported as missing if it has the same name but a different billing project in app."""
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="test-bp-app", name="test-ws"
        )
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp-anvil", "test-ws", "OWNER")],
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(), {workspace: [audit_results.ERROR_NOT_IN_ANVIL]}
        )
        self.assertEqual(audit_results.get_not_in_app(), set(["test-bp-anvil/test-ws"]))

    def test_ignores_workspaces_where_app_is_reader_on_anvil(self):
        """Audit ignores workspaces on AnVIL where app is a READER on AnVIL."""
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp", "test-ws", "READER")],
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_ignores_workspaces_where_app_is_writer_on_anvil(self):
        """Audit ignores workspaces on AnVIL where app is a WRITER on AnVIL."""
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[self.get_api_workspace_json("test-bp", "test-ws", "WRITER")],
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_workspace_one_auth_domain(self):
        """anvil_audit works properly when there is one workspace with one auth domain."""
        auth_domain = factories.WorkspaceAuthorizationDomainFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    auth_domain.workspace.billing_project.name,
                    auth_domain.workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([auth_domain.workspace]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_workspace_two_auth_domains(self):
        """anvil_audit works properly when there is one workspace with two auth domains."""
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.WorkspaceAuthorizationDomainFactory.create(
            workspace=workspace
        )
        auth_domain_2 = factories.WorkspaceAuthorizationDomainFactory.create(
            workspace=workspace
        )
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain_1.group.name, auth_domain_2.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            workspace.billing_project.name, workspace.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertEqual(
            audit_results.get_verified(),
            set([auth_domain_1.workspace, auth_domain_2.workspace]),
        )
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_workspace_two_auth_domains_order_does_not_matter(self):
        """anvil_audit works properly when there is one workspace with two auth domains."""
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.WorkspaceAuthorizationDomainFactory.create(
            workspace=workspace, group__name="aa"
        )
        auth_domain_2 = factories.WorkspaceAuthorizationDomainFactory.create(
            workspace=workspace, group__name="zz"
        )
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain_2.group.name, auth_domain_1.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            workspace.billing_project.name, workspace.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertEqual(
            audit_results.get_verified(),
            set([auth_domain_1.workspace, auth_domain_2.workspace]),
        )
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_workspace_no_auth_domain_in_app_one_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with no auth domain in the app but one on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=["auth-anvil"],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            workspace.billing_project.name, workspace.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {workspace: [audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_workspace_one_auth_domain_in_app_no_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with one auth domain in the app but none on AnVIL."""
        auth_domain = factories.WorkspaceAuthorizationDomainFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    auth_domain.workspace.billing_project.name,
                    auth_domain.workspace.name,
                    "OWNER",
                    auth_domains=[],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {auth_domain.workspace: [audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_workspace_no_auth_domain_in_app_two_auth_domains_on_anvil(self):
        """anvil_audit works properly when there is one workspace with no auth domain in the app but two on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=["auth-domain"],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            workspace.billing_project.name, workspace.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {workspace: [audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_workspace_two_auth_domains_in_app_no_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with two auth domains in the app but none on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            workspace.billing_project.name, workspace.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {workspace: [audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_workspace_two_auth_domains_in_app_one_auth_domain_on_anvil(self):
        """anvil_audit works properly when there is one workspace with two auth domains in the app but one on AnVIL."""
        workspace = factories.WorkspaceFactory.create()
        auth_domain_1 = factories.WorkspaceAuthorizationDomainFactory.create(
            workspace=workspace
        )
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                    auth_domains=[auth_domain_1.group.name],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            workspace.billing_project.name, workspace.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {workspace: [audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_workspace_different_auth_domains(self):
        """anvil_audit works properly when the app and AnVIL have different auth domains for the same workspace."""
        auth_domain = factories.WorkspaceAuthorizationDomainFactory.create(
            group__name="app"
        )
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    auth_domain.workspace.billing_project.name,
                    auth_domain.workspace.name,
                    "OWNER",
                    auth_domains=["anvil"],
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            auth_domain.workspace.billing_project.name, auth_domain.workspace.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {auth_domain.workspace: [audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_workspaces_first_auth_domains_do_not_match(self):
        """anvil_audit works properly when there are two workspaces in the app and the first has auth domain issues."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace_1.billing_project.name,
                    workspace_1.name,
                    "OWNER",
                    auth_domains=["anvil"],
                ),
                self.get_api_workspace_json(
                    workspace_2.billing_project.name,
                    workspace_2.name,
                    "OWNER",
                    auth_domains=[],
                ),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(
            workspace_1.billing_project.name, workspace_1.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(
            workspace_2.billing_project.name, workspace_2.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([workspace_2]))
        self.assertEqual(
            audit_results.get_errors(),
            {workspace_1: [audit_results.ERROR_DIFFERENT_AUTH_DOMAINS]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_workspaces_auth_domains_do_not_match_for_both(self):
        """anvil_audit works properly when there are two workspaces in the app and both have auth domain issues."""
        workspace_1 = factories.WorkspaceFactory.create()
        workspace_2 = factories.WorkspaceFactory.create()
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace_1.billing_project.name,
                    workspace_1.name,
                    "OWNER",
                    auth_domains=["anvil-1"],
                ),
                self.get_api_workspace_json(
                    workspace_2.billing_project.name,
                    workspace_2.name,
                    "OWNER",
                    auth_domains=["anvil-2"],
                ),
            ],
        )
        # Response to check workspace access.
        workspace_acl_url_1 = self.get_api_workspace_acl_url(
            workspace_1.billing_project.name, workspace_1.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url_1,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        # Response to check workspace access.
        workspace_acl_url_2 = self.get_api_workspace_acl_url(
            workspace_2.billing_project.name, workspace_2.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url_2,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {
                workspace_1: [audit_results.ERROR_DIFFERENT_AUTH_DOMAINS],
                workspace_2: [audit_results.ERROR_DIFFERENT_AUTH_DOMAINS],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_workspace_with_two_errors(self):
        """One workspace has two errors: different auth domains and not owner."""
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name, workspace.name, "READER"
                )
            ],
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertIsInstance(audit_results, anvil_audit.WorkspaceAuditResults)
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {
                workspace: [
                    audit_results.ERROR_NOT_OWNER_ON_ANVIL,
                    audit_results.ERROR_DIFFERENT_AUTH_DOMAINS,
                ]
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_fails_sharing_audit(self):
        """anvil_audit works properly when one workspace fails its sharing audit."""
        workspace = factories.WorkspaceFactory.create()
        factories.WorkspaceGroupSharingFactory.create(workspace=workspace)
        # Response for the main call about workspaces.
        api_url = self.get_api_url()
        responses.add(
            responses.GET,
            api_url,
            status=200,
            json=[
                self.get_api_workspace_json(
                    workspace.billing_project.name,
                    workspace.name,
                    "OWNER",
                )
            ],
        )
        # Response to check workspace access.
        workspace_acl_url = self.get_api_workspace_acl_url(
            workspace.billing_project.name, workspace.name
        )
        responses.add(
            responses.GET,
            workspace_acl_url,
            status=200,
            json=self.get_api_workspace_acl_response(),
        )
        audit_results = models.Workspace.anvil_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {workspace: [audit_results.ERROR_WORKSPACE_SHARING]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(workspace_acl_url, 1)


class WorkspaceAnVILAuditSharingAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests forthe Workspace.anvil_audit method."""

    def setUp(self):
        super().setUp()
        # Set the auth session service account email here, since the anvil_audit_membership function will need it.
        self.service_account_email = fake.email()
        anvil_api.AnVILAPIClient().auth_session.credentials.service_account_email = (
            self.service_account_email
        )
        # Set this variable here because it will include the service account.
        # Tests can update it with the update_api_response method.
        self.api_response = {"acl": {}}
        # Create a workspace for use in tests.
        self.workspace = factories.WorkspaceFactory.create()
        self.api_url = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/"
            + self.workspace.billing_project.name
            + "/"
            + self.workspace.name
            + "/acl"
        )

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

    def test_no_access(self):
        """anvil_audit works correctly if this workspace is not shared with any groups."""
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertIsInstance(
            audit_results, anvil_audit.WorkspaceGroupSharingAuditResults
        )
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(self.api_url, 1)

    def test_one_group_reader(self):
        """anvil_audit works correctly if this group has one group member."""
        access = factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        self.update_api_response(access.group.get_email(), access.access)
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([access]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(self.api_url, 1)

    def test_two_group_readers(self):
        """anvil_audit works correctly if this workspace has two group readers."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace
        )
        access_2 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace
        )
        self.update_api_response(access_1.group.get_email(), "READER")
        self.update_api_response(access_2.group.get_email(), "READER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([access_1, access_2]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_group_reader_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has one group reader not in anvil."""
        access = factories.WorkspaceGroupSharingFactory.create(workspace=self.workspace)
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {access: [audit_results.ERROR_NOT_SHARED_IN_ANVIL]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_group_readers_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has two group readers not in anvil."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace
        )
        access_2 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace
        )
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {
                access_1: [audit_results.ERROR_NOT_SHARED_IN_ANVIL],
                access_2: [audit_results.ERROR_NOT_SHARED_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_group_readers_not_in_app(self):
        """anvil_audit works correctly if this workspace has one group reader not in the app."""
        self.update_api_response("test-member@firecloud.org", "READER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(), set(["READER: test-member@firecloud.org"])
        )

    def test_two_group_readers_not_in_app(self):
        """anvil_audit works correctly if this workspace has two group readers not in the app."""
        self.update_api_response("test-member-1@firecloud.org", "READER")
        self.update_api_response("test-member-2@firecloud.org", "READER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(),
            set(
                [
                    "READER: test-member-1@firecloud.org",
                    "READER: test-member-2@firecloud.org",
                ]
            ),
        )

    def test_one_group_members_case_insensitive(self):
        """anvil_audit works correctly if this workspace has one group member not in the app."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, group__name="tEsT-mEmBeR"
        )
        self.update_api_response("Test-Member@firecloud.org", "READER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([access]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set([]))

    def test_one_group_writer(self):
        """anvil_audit works correctly if this workspace has one group writer."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        self.update_api_response(access.group.get_email(), "WRITER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([access]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_group_writers(self):
        """anvil_audit works correctly if this workspace has two group writers."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        access_2 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        self.update_api_response(access_1.group.get_email(), "WRITER")
        self.update_api_response(access_2.group.get_email(), "WRITER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([access_1, access_2]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_group_writer_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has one group writer not in anvil."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {
                access: [audit_results.ERROR_NOT_SHARED_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_group_writers_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has two group writers not in anvil."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        access_2 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {
                access_1: [audit_results.ERROR_NOT_SHARED_IN_ANVIL],
                access_2: [audit_results.ERROR_NOT_SHARED_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_group_writer_not_in_app(self):
        """anvil_audit works correctly if this workspace has one group writer not in the app."""
        self.update_api_response("test-writer@firecloud.org", "WRITER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(), set(["WRITER: test-writer@firecloud.org"])
        )

    def test_two_group_writers_not_in_app(self):
        """anvil_audit works correctly if this workspace has two group writers not in the app."""
        self.update_api_response("test-writer-1@firecloud.org", "WRITER")
        self.update_api_response("test-writer-2@firecloud.org", "WRITER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(),
            set(
                [
                    "WRITER: test-writer-1@firecloud.org",
                    "WRITER: test-writer-2@firecloud.org",
                ]
            ),
        )

    def test_one_group_admin_case_insensitive(self):
        """anvil_audit works correctly if this workspace has one group member not in the app."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            group__name="tEsT-wRiTeR",
            access=models.WorkspaceGroupSharing.WRITER,
        )
        self.update_api_response("Test-Writer@firecloud.org", "WRITER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([access]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set([]))

    def test_one_group_owner(self):
        """anvil_audit works correctly if this workspace has one group owner."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        self.update_api_response(access.group.get_email(), "OWNER", can_share=True)
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([access]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_group_owners(self):
        """anvil_audit works correctly if this workspace has two group owners."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        access_2 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        self.update_api_response(access_1.group.get_email(), "OWNER", can_share=True)
        self.update_api_response(access_2.group.get_email(), "OWNER", can_share=True)
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([access_1, access_2]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_group_owner_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has one group owners not in anvil."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {
                access: [audit_results.ERROR_NOT_SHARED_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_two_group_owners_not_in_anvil(self):
        """anvil_audit works correctly if this workspace has two group owners not in anvil."""
        access_1 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        access_2 = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.OWNER
        )
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {
                access_1: [audit_results.ERROR_NOT_SHARED_IN_ANVIL],
                access_2: [audit_results.ERROR_NOT_SHARED_IN_ANVIL],
            },
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_one_group_owner_not_in_app(self):
        """anvil_audit works correctly if this workspace has one group owner not in the app."""
        self.update_api_response("test-writer@firecloud.org", "OWNER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(), set(["OWNER: test-writer@firecloud.org"])
        )

    def test_two_group_owners_not_in_app(self):
        """anvil_audit works correctly if this workspace has two group owners not in the app."""
        self.update_api_response("test-writer-1@firecloud.org", "OWNER")
        self.update_api_response("test-writer-2@firecloud.org", "OWNER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(
            audit_results.get_not_in_app(),
            set(
                [
                    "OWNER: test-writer-1@firecloud.org",
                    "OWNER: test-writer-2@firecloud.org",
                ]
            ),
        )

    def test_one_group_owner_case_insensitive(self):
        """anvil_audit works correctly with different cases for owner emails."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            group__name="tEsT-oWnEr",
            access=models.WorkspaceGroupSharing.OWNER,
        )
        self.update_api_response("Test-Owner@firecloud.org", "OWNER", can_share=True)
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([access]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set([]))

    def test_group_different_access_reader_in_app_writer_in_anvil(self):
        """anvil_audit works correctly if a group has different access to a workspace in AnVIL."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.READER
        )
        self.update_api_response(access.group.get_email(), "WRITER")
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {access: [audit_results.ERROR_DIFFERENT_ACCESS]},
        )

    def test_group_different_access_reader_in_app_owner_in_anvil(self):
        """anvil_audit works correctly if a group has different access to a workspace in AnVIL."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.READER
        )
        self.update_api_response(
            access.group.get_email(), "OWNER", can_compute=True, can_share=True
        )
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {
                access: [
                    audit_results.ERROR_DIFFERENT_ACCESS,
                    audit_results.ERROR_DIFFERENT_CAN_COMPUTE,
                    audit_results.ERROR_DIFFERENT_CAN_SHARE,
                ]
            },
        )

    def test_group_different_can_compute(self):
        """anvil_audit works correctly if can_compute is different between the app and AnVIL."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        self.update_api_response(access.group.get_email(), "WRITER", can_compute=False)
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {access: [audit_results.ERROR_DIFFERENT_CAN_COMPUTE]},
        )

    def test_group_different_can_share(self):
        """anvil_audit works correctly if can_share is True in AnVIL."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace, access=models.WorkspaceGroupSharing.WRITER
        )
        self.update_api_response(access.group.get_email(), "WRITER", can_share=True)
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(
            audit_results.get_errors(),
            {access: [audit_results.ERROR_DIFFERENT_CAN_SHARE]},
        )

    def test_removes_service_account(self):
        """Removes the service account from acl if it exists."""
        self.update_api_response(
            self.service_account_email, "OWNER", can_compute=True, can_share=True
        )
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())
        responses.assert_call_count(self.api_url, 1)

    def test_group_owner_can_share_true(self):
        """Owners must have can_share=True."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=models.WorkspaceGroupSharing.OWNER,
            can_compute=True,
        )
        self.update_api_response(
            access.group.get_email(), "OWNER", can_compute=True, can_share=True
        )
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertTrue(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set([access]))
        self.assertEqual(audit_results.get_errors(), {})
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_group_writer_can_share_false(self):
        """Writers must have can_share=False."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        self.update_api_response(
            access.group.get_email(), "WRITER", can_compute=True, can_share=True
        )
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {access: [audit_results.ERROR_DIFFERENT_CAN_SHARE]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())

    def test_group_reader_can_share_false(self):
        """Readers must have can_share=False."""
        access = factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace,
            access=models.WorkspaceGroupSharing.READER,
            can_compute=False,
        )
        self.update_api_response(
            access.group.get_email(), "READER", can_compute=False, can_share=True
        )
        responses.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.api_response,
        )
        audit_results = self.workspace.anvil_audit_sharing()
        self.assertFalse(audit_results.ok())
        self.assertEqual(audit_results.get_verified(), set())
        self.assertEqual(
            audit_results.get_errors(),
            {access: [audit_results.ERROR_DIFFERENT_CAN_SHARE]},
        )
        self.assertEqual(audit_results.get_not_in_app(), set())


class GroupGroupMembershipAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        parent_group = factories.ManagedGroupFactory(name="parent-group")
        child_group = factories.ManagedGroupFactory(name="child-group")
        self.object = factories.GroupGroupMembershipFactory(
            parent_group=parent_group,
            child_group=child_group,
            role=models.GroupGroupMembership.MEMBER,
        )
        self.url = (
            self.api_client.firecloud_entry_point
            + "/api/groups/parent-group/MEMBER/child-group@firecloud.org"
        )

    def test_anvil_create_successful(self):
        responses.add(responses.PUT, self.url, status=204)
        self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_403(self):
        responses.add(
            responses.PUT, self.url, status=403, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_404(self):
        responses.add(
            responses.PUT, self.url, status=404, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_500(self):
        responses.add(
            responses.PUT, self.url, status=500, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_other(self):
        responses.add(
            responses.PUT, self.url, status=499, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_successful(self):
        responses.add(responses.DELETE, self.url, status=204)
        self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_403(self):
        responses.add(
            responses.DELETE, self.url, status=403, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_404(self):
        responses.add(
            responses.DELETE, self.url, status=404, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_500(self):
        responses.add(
            responses.DELETE, self.url, status=500, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_other(self):
        responses.add(
            responses.DELETE, self.url, status=499, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)


class GroupAccountMembershipAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        group = factories.ManagedGroupFactory(name="test-group")
        account = factories.AccountFactory(email="test-account@example.com")
        self.object = factories.GroupAccountMembershipFactory(
            group=group, account=account, role=models.GroupAccountMembership.MEMBER
        )
        self.url = (
            self.api_client.firecloud_entry_point
            + "/api/groups/test-group/MEMBER/test-account@example.com"
        )

    def test_anvil_create_successful(self):
        responses.add(responses.PUT, self.url, status=204)
        self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_403(self):
        responses.add(
            responses.PUT, self.url, status=403, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_404(self):
        responses.add(
            responses.PUT, self.url, status=404, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_500(self):
        responses.add(
            responses.PUT, self.url, status=500, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_unsuccessful_other(self):
        responses.add(
            responses.PUT, self.url, status=499, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_successful(self):
        responses.add(
            responses.DELETE, self.url, status=204, json={"message": "mock message"}
        )
        self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_403(self):
        responses.add(
            responses.DELETE, self.url, status=403, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_404(self):
        responses.add(
            responses.DELETE, self.url, status=404, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_500(self):
        responses.add(
            responses.DELETE, self.url, status=500, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_other(self):
        responses.add(
            responses.DELETE, self.url, status=499, json={"message": "mock message"}
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)


class WorkspaceGroupSharingAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        billing_project = factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project=billing_project, name="test-workspace"
        )
        group = factories.ManagedGroupFactory.create(name="test-group")
        self.object = factories.WorkspaceGroupSharingFactory(
            workspace=workspace, group=group, access=models.WorkspaceGroupSharing.READER
        )
        self.url = (
            self.api_client.rawls_entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false"
        )
        self.headers = {"Content-type": "application/json"}
        self.data_add = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.data_delete = [
            {
                "email": "test-group@firecloud.org",
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]

    def get_api_json_response(
        self, invites_sent=[], users_not_found=[], users_updated=[]
    ):
        return {
            "invitesSent": invites_sent,
            "usersNotFound": users_not_found,
            "usersUpdated": users_updated,
        }

    def test_anvil_create_or_update_successful(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_add)],
            json=self.get_api_json_response(users_updated=self.data_add),
        )
        self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_create_can_compute(self):
        """The correct API call is made when creating the object if can_compute is True."""
        self.object.can_compute = True
        self.object.save()
        self.data_add[0]["canCompute"] = True
        responses.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_add)],
            json=self.get_api_json_response(users_updated=self.data_add),
        )
        self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_or_update_unsuccessful_400(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=400,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_or_update_unsuccessful_403(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=403,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_or_update_unsuccessful_workspace_not_found(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=404,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_or_update_unsuccessful_internal_error(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=500,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_or_update_unsuccessful_other(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=499,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_create_or_update_group_not_found_on_anvil(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_add)],
            # Add the full json response.
            json=self.get_api_json_response(users_not_found=self.data_add),
        )
        with self.assertRaises(exceptions.AnVILGroupNotFound):
            self.object.anvil_create_or_update()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_successful(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_delete_can_compute(self):
        """The correct API call is made when deleting an object if can_compute is True."""
        self.object.can_compute = True
        self.object.save()
        self.data_delete[0]["canCompute"] = True
        responses.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_delete)],
            json=self.get_api_json_response(users_updated=self.data_delete),
        )
        self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_400(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=400,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_workspace_not_found(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=404,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_internal_error(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=500,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)

    def test_anvil_delete_unsuccessful_other(self):
        responses.add(
            responses.PATCH,
            self.url,
            status=499,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
        responses.assert_call_count(self.url, 1)
