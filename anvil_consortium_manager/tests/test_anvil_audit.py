import responses
from django.test import TestCase

from .. import models
from ..audit import audit
from . import api_factories, factories
from .utils import AnVILAPIMockTestMixin


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
        self.assertIsInstance(audit_results, audit.ManagedGroupMembershipAudit)
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
