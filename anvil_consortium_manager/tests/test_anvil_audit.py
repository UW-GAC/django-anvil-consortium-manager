import responses
from django.test import TestCase
from faker import Faker

from .. import models
from ..audit import audit
from . import api_factories, factories
from .utils import AnVILAPIMockTestMixin

fake = Faker()


class BillingProjectAuditTest(AnVILAPIMockTestMixin, TestCase):
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
        audit_results = audit.BillingProjectAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_billing_project_no_errors(self):
        """anvil_audit works correct if one billing project exists in the app and in AnVIL."""
        billing_project = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url = self.get_api_url(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = audit.BillingProjectAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(billing_project)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_billing_project_not_on_anvil(self):
        """anvil_audit raises exception with one billing project exists in the app but not on AnVIL."""
        billing_project = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url = self.get_api_url(billing_project.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        audit_results = audit.BillingProjectAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(billing_project)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_two_billing_projects_no_errors(self):
        """anvil_audit returns None if there are two billing projects and both exist on AnVIL."""
        billing_project_1 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=200,
            json=self.get_api_json_response(),
        )
        billing_project_2 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = audit.BillingProjectAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(billing_project_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(billing_project_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_billing_projects_first_not_on_anvil(self):
        """anvil_audit raises exception if two billing projects exist in the app but the first is not on AnVIL."""
        billing_project_1 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        billing_project_2 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(),
        )
        audit_results = audit.BillingProjectAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(billing_project_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(billing_project_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_billing_projects_both_missing(self):
        """anvil_audit raises exception if there are two billing projects that exist in the app but not in AnVIL."""
        billing_project_1 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_1 = self.get_api_url(billing_project_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        billing_project_2 = factories.BillingProjectFactory.create(has_app_as_user=True)
        api_url_2 = self.get_api_url(billing_project_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=404,
            json={"message": "other error"},
        )
        audit_results = audit.BillingProjectAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(billing_project_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(billing_project_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_ignore_not_has_app_has_user(self):
        """anvil_audit does not check AnVIL about billing projects that do not have the app as a user."""
        factories.BillingProjectFactory.create(has_app_as_user=False)
        # No API calls made.
        audit_results = audit.BillingProjectAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)


class AccountAuditTest(AnVILAPIMockTestMixin, TestCase):
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
        audit_results = audit.AccountAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_account_no_errors(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(account.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=self.get_api_json_response(account.email),
        )
        audit_results = audit.AccountAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(account)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_account_not_on_anvil(self):
        """anvil_audit raises exception if one billing project exists in the app but not on AnVIL."""
        account = factories.AccountFactory.create()
        api_url = self.get_api_url(account.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=404,
            json={"message": "other error"},
        )
        audit_results = audit.AccountAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(account)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_two_accounts_no_errors(self):
        """anvil_audit returns None if if two accounts exist in both the app and AnVIL."""
        account_1 = factories.AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=200,
            json=self.get_api_json_response(account_1.email),
        )
        account_2 = factories.AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(account_2.email),
        )
        audit_results = audit.AccountAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(account_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(account_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_accounts_first_not_on_anvil(self):
        """anvil_audit raises exception if two accounts exist in the app but the first is not not on AnVIL."""
        account_1 = factories.AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        account_2 = factories.AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=200,
            json=self.get_api_json_response(account_2.email),
        )
        audit_results = audit.AccountAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(account_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(account_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_accounts_both_missing(self):
        """anvil_audit raises exception if there are two accounts that exist in the app but not in AnVIL."""
        account_1 = factories.AccountFactory.create()
        api_url_1 = self.get_api_url(account_1.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_1,
            status=404,
            json={"message": "other error"},
        )
        account_2 = factories.AccountFactory.create()
        api_url_2 = self.get_api_url(account_2.email)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_2,
            status=404,
            json={"message": "other error"},
        )
        audit_results = audit.AccountAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(account_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(account_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_deactivated_account(self):
        """anvil_audit does not check AnVIL about accounts that are deactivated."""
        account = factories.AccountFactory.create()
        account.deactivate()
        # No API calls made.
        audit_results = audit.AccountAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)


class ManagedGroupAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests forthe ManagedGroup.anvil_audit method."""

    def get_api_groups_url(self):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1"

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

    def test_anvil_audit_no_groups(self):
        """anvil_audit works correct if there are no ManagedGroups in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_group_managed_by_app_no_errors(self):
        """anvil_audit works correct if there is one group in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsAdminFactory(groupName=group.name)]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_managed_by_app_lowercase_role(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsAdminFactory(groupName=group.name)]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_not_managed_by_app_no_errors(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsMemberFactory(groupName=group.name)]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_not_managed_by_app_no_errors_uppercase_role(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsFactory(
                        groupName=group.name, role="Member"
                    )
                ]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_not_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app but not on AnVIL."""
        group = factories.ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(n_groups=0).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group.name,
            status=404,
            json=api_factories.ErrorResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_one_group_on_anvil_but_app_not_in_group_not_managed_by_app(
        self,
    ):
        """anvil_audit is correct if the group is not managed by the app."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(n_groups=0).response,
        )
        # Add the response.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group.name,
            status=200,
            json="FOO@BAR.COM",
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_managed_by_app_on_anvil_but_app_not_in_group(self):
        """anvil_audit raises exception if one group exists in the app but not on AnVIL."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(n_groups=0).response,
        )
        # Add the response.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group.name,
            status=200,
            json="FOO@BAR.COM",
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE])
        )

    def test_anvil_audit_one_group_admin_in_app_member_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app as an admin but the role on AnVIL is member."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsMemberFactory(groupName=group.name)]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE])
        )

    def test_anvil_audit_one_group_member_in_app_admin_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app as an member but the role on AnVIL is admin."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsAdminFactory(groupName=group.name)]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE])
        )

    def test_anvil_audit_two_groups_no_errors(self):
        """anvil_audit works correctly if if two groups exist in both the app and AnVIL."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(groupName=group_1.name),
                    api_factories.GroupDetailsMemberFactory(groupName=group_2.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(group_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_groups_json_response_order_does_not_matter(self):
        """Order of groups in the json response does not matter."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsMemberFactory(groupName=group_2.name),
                    api_factories.GroupDetailsAdminFactory(groupName=group_1.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(group_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_groups_first_not_on_anvil(self):
        """anvil_audit raises exception if two groups exist in the app but the first is not not on AnVIL."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(groupName=group_2.name),
                ]
            ).response,
        )
        # Add response for the group that is not in the app.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group_1.name,
            status=404,
            json=api_factories.ErrorResponseFactory().response,
        )
        # Add responses for the group that is in the app.
        api_url_members = self.get_api_url_members(group_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(group_2)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_two_groups_both_missing(self):
        """anvil_audit raises exception if there are two groups that exist in the app but not in AnVIL."""
        group_1 = factories.ManagedGroupFactory.create()
        group_2 = factories.ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory().response,
        )
        # Add response for the group that is not in the app.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group_1.name,
            status=404,
            json=api_factories.ErrorResponseFactory().response,
        )
        # Add response for the group that is not in the app.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group_2.name,
            status=404,
            json=api_factories.ErrorResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(group_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_NOT_IN_ANVIL]))

    def test_anvil_audit_one_group_member_missing_in_app(self):
        """anvil_audit works correctly if the service account is a member of a group not in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsMemberFactory(groupName="test-group")
                ]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-group")

    def test_anvil_audit_one_group_admin_missing_in_app(self):
        """anvil_audit works correctly if the service account is an admin of a group not in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(groupName="test-group")
                ]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-group")

    def test_anvil_audit_two_groups_missing_in_app(self):
        """anvil_audit works correctly if there are two groups in AnVIL that aren't in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(
                        groupName="test-group-admin"
                    ),
                    api_factories.GroupDetailsMemberFactory(
                        groupName="test-group-member"
                    ),
                ]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-group-admin")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "test-group-member")

    def test_fails_membership_audit(self):
        """Error is reported when a group fails the membership audit."""
        group = factories.ManagedGroupFactory.create()
        factories.GroupAccountMembershipFactory.create(group=group)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[api_factories.GroupDetailsAdminFactory(groupName=group.name)]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_GROUP_MEMBERSHIP])
        )

    def test_admin_in_app_both_member_and_admin_on_anvil(self):
        """anvil_audit works correctly when the app is an admin and AnVIL returns both a member and admin record."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(groupName=group.name),
                    api_factories.GroupDetailsMemberFactory(groupName=group.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_admin_in_app_both_member_and_admin_different_order_on_anvil(self):
        """anvil_audit works correctly when the app is an admin and AnVIL returns both a member and admin record."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsMemberFactory(groupName=group.name),
                    api_factories.GroupDetailsAdminFactory(groupName=group.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_member_in_app_both_member_and_admin_on_anvil(self):
        """anvil_audit works correctly when the app is a member and AnVIL returns both a member and admin record."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsMemberFactory(groupName=group.name),
                    api_factories.GroupDetailsAdminFactory(groupName=group.name),
                ]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE])
        )

    def test_member_in_app_both_member_and_admin_different_order_on_anvil(self):
        """anvil_audit works correctly when the app is a member and AnVIL returns both a member and admin record."""
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(groupName=group.name),
                    api_factories.GroupDetailsMemberFactory(groupName=group.name),
                ]
            ).response,
        )
        audit_results = audit.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE])
        )


class ManagedGroupMembershipAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests forthe ManagedGroupMembershipAudit class."""

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

    def test_no_members(self):
        """audit works correctly if this group has no members."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_one_account_members(self):
        """audit works correctly if this group has one account member."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=[membership.account.email]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        model_result = audit_results.get_result_for_model_instance(membership)
        self.assertIsInstance(model_result, audit.ModelInstanceResult)
        self.assertTrue(model_result.ok())
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_two_account_members(self):
        """audit works correctly if this group has two account members."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupAccountMembershipFactory.create(group=group)
        membership_2 = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=[membership_1.account.email, membership_2.account.email]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        model_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertIsInstance(model_result, audit.ModelInstanceResult)
        self.assertTrue(model_result.ok())
        model_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertIsInstance(model_result, audit.ModelInstanceResult)
        self.assertTrue(model_result.ok())
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_one_account_members_not_in_anvil(self):
        """audit works correctly if this group has one account member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        model_result = audit_results.get_result_for_model_instance(membership)
        self.assertIsInstance(model_result, audit.ModelInstanceResult)
        self.assertFalse(model_result.ok())
        self.assertEqual(
            model_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL])
        )
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_two_account_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has two account member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupAccountMembershipFactory.create(group=group)
        membership_2 = factories.GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        model_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertIsInstance(model_result, audit.ModelInstanceResult)
        self.assertFalse(model_result.ok())
        self.assertEqual(
            model_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL])
        )
        model_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertIsInstance(model_result, audit.ModelInstanceResult)
        self.assertFalse(model_result.ok())
        self.assertEqual(
            model_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL])
        )
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_one_account_members_not_in_app(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=["test-member@example.com"]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        # Check individual records.
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(record_result, audit.NotInAppResult)
        self.assertEqual(record_result.record, "MEMBER: test-member@example.com")

    def test_two_account_members_not_in_app(self):
        """anvil_audit works correctly if this group has two account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=["test-member-1@example.com", "test-member-2@example.com"]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        # Check individual records.
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(record_result, audit.NotInAppResult)
        self.assertEqual(record_result.record, "MEMBER: test-member-1@example.com")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertIsInstance(record_result, audit.NotInAppResult)
        self.assertEqual(record_result.record, "MEMBER: test-member-2@example.com")

    def test_one_account_members_case_insensitive(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, account__email="tEsT-mEmBeR@example.com"
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=["Test-Member@example.com"]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_one_account_admin(self):
        """anvil_audit works correctly if this group has one account admin."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=[membership.account.email]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

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
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=[membership_1.account.email, membership_2.account.email]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertTrue(record_result.ok())

    def test_one_account_admin_not_in_anvil(self):
        """anvil_audit works correctly if this group has one account member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL])
        )

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
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL])
        )
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL])
        )

    def test_one_account_admin_not_in_app(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=["test-admin@example.com"]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: test-admin@example.com")

    def test_two_account_admin_not_in_app(self):
        """anvil_audit works correctly if this group has two account admin not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=["test-admin-1@example.com", "test-admin-2@example.com"]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: test-admin-1@example.com")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "ADMIN: test-admin-2@example.com")

    def test_one_account_admin_case_insensitive(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group,
            account__email="tEsT-aDmIn@example.com",
            role=models.GroupAccountMembership.ADMIN,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=["Test-Admin@example.com"]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_account_different_role_member_in_app_admin_in_anvil(self):
        """anvil_audit works correctly if an account has a different role in AnVIL."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupAccountMembershipFactory.create(
            group=group, role=models.GroupAccountMembership.MEMBER
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=[membership.account.email]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL])
        )
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: " + membership.account.email)

    def test_one_group_members(self):
        """anvil_audit works correctly if this group has one group member."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=[membership.child_group.email]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_two_group_members(self):
        """anvil_audit works correctly if this group has two account members."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        membership_2 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=[
                    membership_1.child_group.email,
                    membership_2.child_group.email,
                ]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertTrue(record_result.ok())

    def test_one_group_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has one group member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL])
        )

    def test_two_group_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has two group member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership_1 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        membership_2 = factories.GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL])
        )
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL])
        )

    def test_one_group_members_not_in_app(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=["test-member@firecloud.org"]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "MEMBER: test-member@firecloud.org")

    def test_two_group_members_not_in_app(self):
        """anvil_audit works correctly if this group has two group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=["test-member-1@firecloud.org", "test-member-2@firecloud.org"]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "MEMBER: test-member-1@firecloud.org")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "MEMBER: test-member-2@firecloud.org")

    def test_one_group_members_case_insensitive(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, child_group__name="tEsT-mEmBeR"
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=["Test-Member@firecloud.org"]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_one_group_admin(self):
        """anvil_audit works correctly if this group has one group admin."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=[membership.child_group.email]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

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
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=[
                    membership_1.child_group.email,
                    membership_2.child_group.email,
                ]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertTrue(record_result.ok())

    def test_one_group_admin_not_in_anvil(self):
        """anvil_audit works correctly if this group has one group member not in anvil."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL])
        )

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
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL])
        )
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL])
        )

    def test_one_group_admin_not_in_app(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=["test-admin@firecloud.org"]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: test-admin@firecloud.org")

    def test_two_group_admin_not_in_app(self):
        """anvil_audit works correctly if this group has two group admin not in the app."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=["test-admin-1@firecloud.org", "test-admin-2@firecloud.org"]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: test-admin-1@firecloud.org")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "ADMIN: test-admin-2@firecloud.org")

    def test_one_group_admin_case_insensitive(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group,
            child_group__name="tEsT-aDmIn",
            role=models.GroupGroupMembership.ADMIN,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=["Test-Admin@firecloud.org"]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_group_different_role_member_in_app_admin_in_anvil(self):
        """anvil_audit works correctly if an group has a different role in AnVIL."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.MEMBER
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=[membership.child_group.email]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(
            record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL])
        )
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: " + membership.child_group.email)

    def test_service_account_is_both_admin_and_member(self):
        """No errors are reported when the service account is both a member and an admin of a group."""
        group = factories.ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=[self.service_account_email]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_different_group_member_email(self):
        """anvil_audit works correctly if this group has one group member with a different email."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, child_group__email="foo@bar.com"
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=[membership.child_group.email]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_different_group_member_email_case_insensitive(self):
        """anvil_audit works correctly if this group has one group member with a different email, case insensitive."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, child_group__email="foo@bar.com"
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=["Foo@Bar.com"]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_service_account_is_not_directly_admin(self):
        """Audit works when the service account is not directly an admin of a group (but is via a group admin)."""
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group,
            child_group__email="foo@bar.com",
            role=models.GroupGroupMembership.ADMIN,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            # Use the Membership factory because it doesn't add the service account as a direct admin.
            json=api_factories.GetGroupMembershipResponseFactory(
                response=["foo@bar.com"]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_group_is_both_admin_and_member(self):
        group = factories.ManagedGroupFactory.create()
        membership = factories.GroupGroupMembershipFactory.create(
            parent_group=group, role=models.GroupGroupMembership.ADMIN
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=[membership.child_group.email]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=[membership.child_group.email]
            ).response,
        )
        audit_results = audit.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())
