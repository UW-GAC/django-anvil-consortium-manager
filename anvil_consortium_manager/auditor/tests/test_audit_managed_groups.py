import responses
from django.test import TestCase
from faker import Faker

from anvil_consortium_manager.exceptions import AnVILNotGroupAdminError
from anvil_consortium_manager.models import (
    Account,
    GroupAccountMembership,
    GroupGroupMembership,
)
from anvil_consortium_manager.tests.api_factories import (
    ErrorResponseFactory,
    GetGroupMembershipAdminResponseFactory,
    GetGroupMembershipResponseFactory,
    GetGroupsResponseFactory,
    GroupDetailsAdminFactory,
    GroupDetailsFactory,
    GroupDetailsMemberFactory,
)
from anvil_consortium_manager.tests.factories import (
    GroupAccountMembershipFactory,
    GroupGroupMembershipFactory,
    ManagedGroupFactory,
)
from anvil_consortium_manager.tests.utils import AnVILAPIMockTestMixin

from ..audit import base, managed_groups
from . import factories

fake = Faker()


class ManagedGroupAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests forthe ManagedGroup.anvil_audit method."""

    def get_api_groups_url(self):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1"

    def get_api_url_members(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member"

    def get_api_url_admins(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/admin"

    def test_anvil_audit_no_groups(self):
        """anvil_audit works correct if there are no ManagedGroups in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_group_managed_by_app_no_errors(self):
        """anvil_audit works correct if there is one group in the app and it exists on AnVIL."""
        group = ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsAdminFactory(groupName=group.name)]).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_managed_by_app_lowercase_role(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsAdminFactory(groupName=group.name)]).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_not_managed_by_app_no_errors(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsMemberFactory(groupName=group.name)]).response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_not_managed_by_app_no_errors_uppercase_role(self):
        """anvil_audit works correct if there is one account in the app and it exists on AnVIL."""
        group = ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsFactory(groupName=group.name, role="Member")]).response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_not_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app but not on AnVIL."""
        group = ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(n_groups=0).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group.name,
            status=404,
            json=ErrorResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
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
        group = ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(n_groups=0).response,
        )
        # Add the response.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group.name,
            status=200,
            json="FOO@BAR.COM",
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_anvil_audit_one_group_managed_by_app_on_anvil_but_app_not_in_group(self):
        """anvil_audit raises exception if one group exists in the app but not on AnVIL."""
        group = ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(n_groups=0).response,
        )
        # Add the response.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group.name,
            status=200,
            json="FOO@BAR.COM",
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE]))

    def test_anvil_audit_one_group_admin_in_app_member_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app as an admin but the role on AnVIL is member."""
        group = ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsMemberFactory(groupName=group.name)]).response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE]))

    def test_anvil_audit_one_group_member_in_app_admin_on_anvil(self):
        """anvil_audit raises exception if one group exists in the app as an member but the role on AnVIL is admin."""
        group = ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsAdminFactory(groupName=group.name)]).response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE]))

    def test_anvil_audit_two_groups_no_errors(self):
        """anvil_audit works correctly if if two groups exist in both the app and AnVIL."""
        group_1 = ManagedGroupFactory.create()
        group_2 = ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(
                response=[
                    GroupDetailsAdminFactory(groupName=group_1.name),
                    GroupDetailsMemberFactory(groupName=group_2.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
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
        group_1 = ManagedGroupFactory.create()
        group_2 = ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(
                response=[
                    GroupDetailsMemberFactory(groupName=group_2.name),
                    GroupDetailsAdminFactory(groupName=group_1.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group_1.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
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
        group_1 = ManagedGroupFactory.create()
        group_2 = ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(
                response=[
                    GroupDetailsAdminFactory(groupName=group_2.name),
                ]
            ).response,
        )
        # Add response for the group that is not in the app.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group_1.name,
            status=404,
            json=ErrorResponseFactory().response,
        )
        # Add responses for the group that is in the app.
        api_url_members = self.get_api_url_members(group_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group_2.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
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
        group_1 = ManagedGroupFactory.create()
        group_2 = ManagedGroupFactory.create()
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory().response,
        )
        # Add response for the group that is not in the app.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group_1.name,
            status=404,
            json=ErrorResponseFactory().response,
        )
        # Add response for the group that is not in the app.
        self.anvil_response_mock.add(
            responses.GET,
            "https://sam.dsde-prod.broadinstitute.org/api/groups/v1/" + group_2.name,
            status=404,
            json=ErrorResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
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
        """Groups that the app is a member of are not reported in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsMemberFactory(groupName="test-group")]).response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_anvil_audit_one_group_admin_missing_in_app(self):
        """anvil_audit works correctly if the service account is an admin of a group not in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsAdminFactory(groupName="test-group")]).response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-group")

    def test_anvil_audit_two_groups_admin_missing_in_app(self):
        """anvil_audit works correctly if there are two groups in AnVIL that aren't in the app."""
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(
                response=[
                    GroupDetailsAdminFactory(groupName="test-group-1"),
                    GroupDetailsAdminFactory(groupName="test-group-2"),
                ]
            ).response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "test-group-1")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "test-group-2")

    def test_fails_membership_audit(self):
        """Error is reported when a group fails the membership audit."""
        group = ManagedGroupFactory.create()
        GroupAccountMembershipFactory.create(group=group)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(response=[GroupDetailsAdminFactory(groupName=group.name)]).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_MEMBERSHIP]))

    def test_admin_in_app_both_member_and_admin_on_anvil(self):
        """anvil_audit works correctly when the app is an admin and AnVIL returns both a member and admin record."""
        group = ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(
                response=[
                    GroupDetailsAdminFactory(groupName=group.name),
                    GroupDetailsMemberFactory(groupName=group.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_admin_in_app_both_member_and_admin_different_order_on_anvil(self):
        """anvil_audit works correctly when the app is an admin and AnVIL returns both a member and admin record."""
        group = ManagedGroupFactory.create(is_managed_by_app=True)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(
                response=[
                    GroupDetailsMemberFactory(groupName=group.name),
                    GroupDetailsAdminFactory(groupName=group.name),
                ]
            ).response,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertTrue(record_result.ok())

    def test_member_in_app_both_member_and_admin_on_anvil(self):
        """anvil_audit works correctly when the app is a member and AnVIL returns both a member and admin record."""
        group = ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(
                response=[
                    GroupDetailsMemberFactory(groupName=group.name),
                    GroupDetailsAdminFactory(groupName=group.name),
                ]
            ).response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE]))

    def test_member_in_app_both_member_and_admin_different_order_on_anvil(self):
        """anvil_audit works correctly when the app is a member and AnVIL returns both a member and admin record."""
        group = ManagedGroupFactory.create(is_managed_by_app=False)
        api_url = self.get_api_groups_url()
        self.anvil_response_mock.add(
            responses.GET,
            api_url,
            status=200,
            json=GetGroupsResponseFactory(
                response=[
                    GroupDetailsAdminFactory(groupName=group.name),
                    GroupDetailsMemberFactory(groupName=group.name),
                ]
            ).response,
        )
        audit_results = managed_groups.ManagedGroupAudit()
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(group)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_DIFFERENT_ROLE]))


class ManagedGroupMembershipAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests forthe ManagedGroupMembershipAudit class."""

    def get_api_url_members(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member"

    def get_api_url_admins(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/admin"

    def test_group_not_managed_by_app(self):
        group = ManagedGroupFactory.create(is_managed_by_app=False)
        with self.assertRaises(AnVILNotGroupAdminError):
            managed_groups.ManagedGroupMembershipAudit(group)

    def test_no_members(self):
        """audit works correctly if this group has no members."""
        group = ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)

    def test_one_account_members(self):
        """audit works correctly if this group has one account member."""
        group = ManagedGroupFactory.create()
        membership = GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=[membership.account.email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        model_result = audit_results.get_result_for_model_instance(membership)
        self.assertIsInstance(model_result, base.ModelInstanceResult)
        self.assertTrue(model_result.ok())
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)

    def test_two_account_members(self):
        """audit works correctly if this group has two account members."""
        group = ManagedGroupFactory.create()
        membership_1 = GroupAccountMembershipFactory.create(group=group)
        membership_2 = GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(
                response=[membership_1.account.email, membership_2.account.email]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        model_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertIsInstance(model_result, base.ModelInstanceResult)
        self.assertTrue(model_result.ok())
        model_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertIsInstance(model_result, base.ModelInstanceResult)
        self.assertTrue(model_result.ok())
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)

    def test_one_account_members_not_in_anvil(self):
        """audit works correctly if this group has one account member not in anvil."""
        group = ManagedGroupFactory.create()
        membership = GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        model_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL]))

    def test_two_account_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has two account member not in anvil."""
        group = ManagedGroupFactory.create()
        membership_1 = GroupAccountMembershipFactory.create(group=group)
        membership_2 = GroupAccountMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        model_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertIsInstance(model_result, base.ModelInstanceResult)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL]))
        model_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertIsInstance(model_result, base.ModelInstanceResult)
        self.assertFalse(model_result.ok())
        self.assertEqual(model_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL]))
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)

    def test_one_account_members_not_in_app(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=["test-member@example.com"]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        # Check individual records.
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(record_result, managed_groups.ManagedGroupMembershipNotInAppResult)
        self.assertEqual(record_result.record, "MEMBER: test-member@example.com")
        self.assertEqual(record_result.group, group)
        self.assertEqual(record_result.email, "test-member@example.com")
        self.assertEqual(record_result.role, "MEMBER")

    def test_two_account_members_not_in_app(self):
        """anvil_audit works correctly if this group has two account member not in the app."""
        group = ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(
                response=["test-member-1@example.com", "test-member-2@example.com"]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        # Check individual records.
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(record_result, managed_groups.ManagedGroupMembershipNotInAppResult)
        self.assertEqual(record_result.record, "MEMBER: test-member-1@example.com")
        self.assertEqual(record_result.group, group)
        self.assertEqual(record_result.email, "test-member-1@example.com")
        self.assertEqual(record_result.role, "MEMBER")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertIsInstance(record_result, managed_groups.ManagedGroupMembershipNotInAppResult)
        self.assertEqual(record_result.record, "MEMBER: test-member-2@example.com")
        self.assertEqual(record_result.group, group)
        self.assertEqual(record_result.email, "test-member-2@example.com")
        self.assertEqual(record_result.role, "MEMBER")

    def test_one_account_members_case_insensitive(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = ManagedGroupFactory.create()
        membership = GroupAccountMembershipFactory.create(group=group, account__email="tEsT-mEmBeR@example.com")
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=["Test-Member@example.com"]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_one_account_admin(self):
        """anvil_audit works correctly if this group has one account admin."""
        group = ManagedGroupFactory.create()
        membership = GroupAccountMembershipFactory.create(group=group, role=GroupAccountMembership.ADMIN)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(response=[membership.account.email]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_two_account_admin(self):
        """anvil_audit works correctly if this group has two account members."""
        group = ManagedGroupFactory.create()
        membership_1 = GroupAccountMembershipFactory.create(group=group, role=GroupAccountMembership.ADMIN)
        membership_2 = GroupAccountMembershipFactory.create(group=group, role=GroupAccountMembership.ADMIN)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(
                response=[membership_1.account.email, membership_2.account.email]
            ).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertTrue(record_result.ok())

    def test_one_account_admin_not_in_anvil(self):
        """anvil_audit works correctly if this group has one account member not in anvil."""
        group = ManagedGroupFactory.create()
        membership = GroupAccountMembershipFactory.create(group=group, role=GroupAccountMembership.ADMIN)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL]))

    def test_two_account_admins_not_in_anvil(self):
        """anvil_audit works correctly if this group has two account member not in anvil."""
        group = ManagedGroupFactory.create()
        membership_1 = GroupAccountMembershipFactory.create(group=group, role=GroupAccountMembership.ADMIN)
        membership_2 = GroupAccountMembershipFactory.create(group=group, role=GroupAccountMembership.ADMIN)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL]))

    def test_one_account_admin_not_in_app(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(response=["test-admin@example.com"]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(record_result, managed_groups.ManagedGroupMembershipNotInAppResult)
        self.assertEqual(record_result.record, "ADMIN: test-admin@example.com")
        self.assertEqual(record_result.group, group)
        self.assertEqual(record_result.email, "test-admin@example.com")
        self.assertEqual(record_result.role, "ADMIN")

    def test_two_account_admin_not_in_app(self):
        """anvil_audit works correctly if this group has two account admin not in the app."""
        group = ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(
                response=["test-admin-1@example.com", "test-admin-2@example.com"]
            ).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: test-admin-1@example.com")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "ADMIN: test-admin-2@example.com")

    def test_one_account_admin_case_insensitive(self):
        """anvil_audit works correctly if this group has one account member not in the app."""
        group = ManagedGroupFactory.create()
        membership = GroupAccountMembershipFactory.create(
            group=group,
            account__email="tEsT-aDmIn@example.com",
            role=GroupAccountMembership.ADMIN,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(response=["Test-Admin@example.com"]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_account_different_role_member_in_app_admin_in_anvil(self):
        """anvil_audit works correctly if an account has a different role in AnVIL."""
        group = ManagedGroupFactory.create()
        membership = GroupAccountMembershipFactory.create(group=group, role=GroupAccountMembership.MEMBER)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(response=[membership.account.email]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL]))
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: " + membership.account.email)

    def test_one_group_members(self):
        """anvil_audit works correctly if this group has one group member."""
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=[membership.child_group.email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_two_group_members(self):
        """anvil_audit works correctly if this group has two account members."""
        group = ManagedGroupFactory.create()
        membership_1 = GroupGroupMembershipFactory.create(parent_group=group)
        membership_2 = GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(
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
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertTrue(record_result.ok())

    def test_one_group_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has one group member not in anvil."""
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL]))

    def test_two_group_members_not_in_anvil(self):
        """anvil_audit works correctly if this group has two group member not in anvil."""
        group = ManagedGroupFactory.create()
        membership_1 = GroupGroupMembershipFactory.create(parent_group=group)
        membership_2 = GroupGroupMembershipFactory.create(parent_group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL]))

    def test_one_group_members_not_in_app(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=["test-member@firecloud.org"]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(record_result, managed_groups.ManagedGroupMembershipNotInAppResult)
        self.assertEqual(record_result.record, "MEMBER: test-member@firecloud.org")
        self.assertEqual(record_result.group, group)
        self.assertEqual(record_result.email, "test-member@firecloud.org")
        self.assertEqual(record_result.role, "MEMBER")

    def test_two_group_members_not_in_app(self):
        """anvil_audit works correctly if this group has two group member not in the app."""
        group = ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(
                response=["test-member-1@firecloud.org", "test-member-2@firecloud.org"]
            ).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "MEMBER: test-member-1@firecloud.org")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "MEMBER: test-member-2@firecloud.org")

    def test_one_group_members_ignored(self):
        """anvil_audit works correctly if this group has one ignored group member."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        group = obj.group
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=[obj.ignored_email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertEqual(record_result.model_instance, obj)
        self.assertEqual(record_result.record, "MEMBER: " + obj.ignored_email)

    def test_two_group_members_ignored(self):
        """anvil_audit works correctly if this group has two ignored group members."""
        group = ManagedGroupFactory.create()
        obj_1 = factories.IgnoredManagedGroupMembershipFactory.create(group=group)
        obj_2 = factories.IgnoredManagedGroupMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=[obj_1.ignored_email, obj_2.ignored_email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 2)
        record_results = audit_results.get_ignored_results()
        record_result = [record_result for record_result in record_results if record_result.model_instance == obj_1][0]
        self.assertEqual(record_result.record, "MEMBER: " + obj_1.ignored_email)
        record_result = [record_result for record_result in record_results if record_result.model_instance == obj_2][0]
        self.assertEqual(record_result.record, "MEMBER: " + obj_2.ignored_email)

    def test_ignored_still_reports_records_when_email_not_member_of_group(self):
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        group = obj.group
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertEqual(record_result.model_instance, obj)
        self.assertIsNone(record_result.record)

    def test_one_group_member_ignored_case_insensitive(self):
        obj = factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="foo@bar.com")
        group = obj.group
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=["FoO@bAr.CoM"]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertEqual(record_result.model_instance, obj)
        self.assertEqual(record_result.record, "MEMBER: foo@bar.com")

    def test_one_group_members_case_insensitive(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(parent_group=group, child_group__name="tEsT-mEmBeR")
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=["Test-Member@firecloud.org"]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_one_group_admin(self):
        """anvil_audit works correctly if this group has one group admin."""
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(parent_group=group, role=GroupGroupMembership.ADMIN)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(response=[membership.child_group.email]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_two_group_admin(self):
        """anvil_audit works correctly if this group has two group admin."""
        group = ManagedGroupFactory.create()
        membership_1 = GroupGroupMembershipFactory.create(parent_group=group, role=GroupGroupMembership.ADMIN)
        membership_2 = GroupGroupMembershipFactory.create(parent_group=group, role=GroupGroupMembership.ADMIN)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(
                response=[
                    membership_1.child_group.email,
                    membership_2.child_group.email,
                ]
            ).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 2)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertTrue(record_result.ok())
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertTrue(record_result.ok())

    def test_one_group_admin_not_in_anvil(self):
        """anvil_audit works correctly if this group has one group member not in anvil."""
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(parent_group=group, role=GroupGroupMembership.ADMIN)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL]))

    def test_two_group_admins_not_in_anvil(self):
        """anvil_audit works correctly if this group has two group member not in anvil."""
        group = ManagedGroupFactory.create()
        membership_1 = GroupGroupMembershipFactory.create(parent_group=group, role=GroupGroupMembership.ADMIN)
        membership_2 = GroupGroupMembershipFactory.create(parent_group=group, role=GroupGroupMembership.ADMIN)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 2)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership_1)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL]))
        record_result = audit_results.get_result_for_model_instance(membership_2)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_ADMIN_NOT_IN_ANVIL]))

    def test_one_group_admin_not_in_app(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(response=["test-admin@firecloud.org"]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertIsInstance(record_result, managed_groups.ManagedGroupMembershipNotInAppResult)
        self.assertEqual(record_result.record, "ADMIN: test-admin@firecloud.org")
        self.assertEqual(record_result.group, group)
        self.assertEqual(record_result.email, "test-admin@firecloud.org")
        self.assertEqual(record_result.role, "ADMIN")

    def test_two_group_admin_not_in_app(self):
        """anvil_audit works correctly if this group has two group admin not in the app."""
        group = ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(
                response=["test-admin-1@firecloud.org", "test-admin-2@firecloud.org"]
            ).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 2)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: test-admin-1@firecloud.org")
        record_result = audit_results.get_not_in_app_results()[1]
        self.assertEqual(record_result.record, "ADMIN: test-admin-2@firecloud.org")

    def test_one_group_admin_ignored(self):
        """anvil_audit works correctly if this group has one ignored group member."""
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        group = obj.group
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipResponseFactory(response=[obj.ignored_email]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertEqual(record_result.model_instance, obj)

    def test_two_group_admins_ignored(self):
        group = ManagedGroupFactory.create()
        obj_1 = factories.IgnoredManagedGroupMembershipFactory.create(group=group)
        obj_2 = factories.IgnoredManagedGroupMembershipFactory.create(group=group)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipResponseFactory(response=[obj_1.ignored_email, obj_2.ignored_email]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 2)
        record_results = audit_results.get_ignored_results()
        self.assertIn(obj_1, [record_result.model_instance for record_result in record_results])
        self.assertIn(obj_2, [record_result.model_instance for record_result in record_results])

    def test_one_group_admin_ignored_case_insensitive(self):
        obj = factories.IgnoredManagedGroupMembershipFactory.create(ignored_email="foo@bar.com")
        group = obj.group
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipResponseFactory(response=["FoO@bAr.CoM"]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_ignored_results()[0]
        self.assertEqual(record_result.model_instance, obj)
        self.assertEqual(record_result.record, "ADMIN: foo@bar.com")

    def test_one_group_admin_case_insensitive(self):
        """anvil_audit works correctly if this group has one group member not in the app."""
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(
            parent_group=group,
            child_group__name="tEsT-aDmIn",
            role=GroupGroupMembership.ADMIN,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(response=["Test-Admin@firecloud.org"]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_group_different_role_member_in_app_admin_in_anvil(self):
        """anvil_audit works correctly if an group has a different role in AnVIL."""
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(parent_group=group, role=GroupGroupMembership.MEMBER)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(response=[membership.child_group.email]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(record_result.ok())
        self.assertEqual(record_result.errors, set([audit_results.ERROR_GROUP_MEMBER_NOT_IN_ANVIL]))
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: " + membership.child_group.email)

    def test_service_account_is_both_admin_and_member(self):
        """No errors are reported when the service account is both a member and an admin of a group."""
        group = ManagedGroupFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=[self.service_account_email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)

    def test_different_group_member_email(self):
        """anvil_audit works correctly if this group has one group member with a different email."""
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(parent_group=group, child_group__email="foo@bar.com")
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=[membership.child_group.email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_different_group_member_email_case_insensitive(self):
        """anvil_audit works correctly if this group has one group member with a different email, case insensitive."""
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(parent_group=group, child_group__email="foo@bar.com")
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=["Foo@Bar.com"]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_service_account_is_not_directly_admin(self):
        """Audit works when the service account is not directly an admin of a group (but is via a group admin)."""
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(
            parent_group=group,
            child_group__email="foo@bar.com",
            role=GroupGroupMembership.ADMIN,
        )
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            # Use the Membership factory because it doesn't add the service account as a direct admin.
            json=GetGroupMembershipResponseFactory(response=["foo@bar.com"]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_group_is_both_admin_and_member(self):
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(parent_group=group, role=GroupGroupMembership.ADMIN)
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=[membership.child_group.email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(response=[membership.child_group.email]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertTrue(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 1)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertTrue(record_result.ok())

    def test_deactivated_account_not_member_in_anvil(self):
        """Audit fails if a deactivated account is not in the group on AnVIL."""
        group = ManagedGroupFactory.create()
        # Create an inactive account that is a member of this group.
        membership = GroupAccountMembershipFactory.create(group=group, account__status=Account.INACTIVE_STATUS)
        # The Account is not a member in AnVIL
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        model_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(model_result.ok())
        self.assertEqual(
            model_result.errors,
            set([audit_results.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL, audit_results.ERROR_DEACTIVATED_ACCOUNT]),
        )

    def test_deactivated_account_member_in_anvil(self):
        """Audit is not ok if a deactivated account is in the group on AnVIL."""
        group = ManagedGroupFactory.create()
        # Create an inactive account that is a member of this group.
        membership = GroupAccountMembershipFactory.create(group=group, account__status=Account.INACTIVE_STATUS)
        # The Account is not a member in AnVIL
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory(response=[membership.account.email]).response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertEqual(
            record_result.errors,
            set([audit_results.ERROR_DEACTIVATED_ACCOUNT]),
        )

    def test_deactivated_account_not_admin_in_anvil(self):
        """Audit is not ok if a deactivated account is not in the group on AnVIL."""
        group = ManagedGroupFactory.create()
        # Create an inactive account that is a member of this group.
        membership = GroupAccountMembershipFactory.create(
            group=group,
            account__status=Account.INACTIVE_STATUS,
            role=GroupAccountMembership.ADMIN,
        )
        # The Account is not a member in AnVIL
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        model_result = audit_results.get_result_for_model_instance(membership)
        self.assertFalse(model_result.ok())
        self.assertEqual(
            model_result.errors,
            set([audit_results.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL, audit_results.ERROR_DEACTIVATED_ACCOUNT]),
        )

    def test_deactivated_account_admin_in_anvil(self):
        """Audit is not ok if a deactivated account is in the group on AnVIL."""
        group = ManagedGroupFactory.create()
        # Create an inactive account that is a member of this group.
        membership = GroupAccountMembershipFactory.create(
            group=group,
            account__status=Account.INACTIVE_STATUS,
            role=GroupAccountMembership.ADMIN,
        )
        # The Account is not a member in AnVIL
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipAdminResponseFactory(response=[membership.account.email]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 1)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 0)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)
        record_result = audit_results.get_result_for_model_instance(membership)
        self.assertEqual(
            record_result.errors,
            set([audit_results.ERROR_DEACTIVATED_ACCOUNT]),
        )

    def test_ignored_same_email_different_group(self):
        """This email is ignored for a different group."""
        group = ManagedGroupFactory.create()
        # Create an ignored record for this email, but a different group.
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipResponseFactory(response=[obj.ignored_email]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        self.assertEqual(len(audit_results.get_ignored_results()), 0)

    def test_ignored_different_email_same_group(self):
        """A different email is ignored for a this group."""
        # Create an ignored record for this email, but a different group.
        obj = factories.IgnoredManagedGroupMembershipFactory.create()
        group = obj.group
        api_url_members = self.get_api_url_members(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_members,
            status=200,
            json=GetGroupMembershipAdminResponseFactory().response,
        )
        api_url_admins = self.get_api_url_admins(group.name)
        self.anvil_response_mock.add(
            responses.GET,
            api_url_admins,
            status=200,
            json=GetGroupMembershipResponseFactory(response=["foo@bar.com"]).response,
        )
        audit_results = managed_groups.ManagedGroupMembershipAudit(group)
        audit_results.run_audit()
        self.assertFalse(audit_results.ok())
        self.assertEqual(len(audit_results.get_verified_results()), 0)
        self.assertEqual(len(audit_results.get_error_results()), 0)
        self.assertEqual(len(audit_results.get_not_in_app_results()), 1)
        self.assertEqual(len(audit_results.get_ignored_results()), 1)
        record_result = audit_results.get_not_in_app_results()[0]
        self.assertEqual(record_result.record, "ADMIN: foo@bar.com")
        record_result = audit_results.get_ignored_results()[0]
        self.assertEqual(record_result.model_instance, obj)
        self.assertIsNone(record_result.record)
