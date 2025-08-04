import responses
from django.core.exceptions import ValidationError
from django.test import TestCase
from faker import Faker

from .. import anvil_api, exceptions, models
from ..adapters.default import DefaultWorkspaceAdapter
from . import api_factories, factories
from .utils import AnVILAPIMockTestMixin

fake = Faker()


class BillingProjectAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.object = factories.BillingProjectFactory()
        self.url = self.api_client.rawls_entry_point + "/api/billing/v2/" + self.object.name

    def test_anvil_exists_does_exist(self):
        self.anvil_response_mock.add(responses.GET, self.url, status=200)
        self.assertIs(self.object.anvil_exists(), True)

    def test_anvil_exists_does_not_exist(self):
        self.anvil_response_mock.add(responses.GET, self.url, status=404, json={"message": "mock message"})
        self.assertIs(self.object.anvil_exists(), False)


class BillingProjectAnVILImportAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the BillingProject.anvil_import method."""

    def get_api_url(self, billing_project_name):
        return self.api_client.rawls_entry_point + "/api/billing/v2/" + billing_project_name

    def get_api_json_response(self):
        return {
            "roles": ["User"],
        }

    def test_can_import_billing_project_where_we_are_users(self):
        """A BillingProject is created if there if we are users of the billing project on AnVIL."""
        billing_project_name = "test-billing-project"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project_name),
            status=200,
            json=self.get_api_json_response(),
        )
        billing_project = models.BillingProject.anvil_import(billing_project_name, note="test note")
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
        self.anvil_response_mock.add(
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
        self.assertEqual(models.BillingProject.objects.get(pk=billing_project.pk), billing_project)

    def test_anvil_import_api_internal_error(self):
        """No BillingProjects are created if there is an internal error from the AnVIL API."""
        billing_project_name = "test-billing-project"
        self.anvil_response_mock.add(
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
        self.anvil_response_mock.add(
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


class UserEmailEntryAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the UserEmailEntry model that call the AnVIL API."""

    def setUp(self):
        super().setUp()
        self.object = factories.UserEmailEntryFactory.create()
        self.api_url = self.api_client.sam_entry_point + "/api/users/v1/" + self.object.email

    def get_api_user_json_response(self, email):
        id = fake.bothify(text="#" * 21)
        return {
            "googleSubjectId": id,
            "userEmail": email,
            "userSubjectId": id,
        }

    def test_anvil_account_exists_does_exist(self):
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.get_api_user_json_response(self.object.email),
        )
        self.assertIs(self.object.anvil_account_exists(), True)

    def test_anvil_account_exists_does_not_exist(self):
        self.anvil_response_mock.add(responses.GET, self.api_url, status=404, json={"message": "mock message"})
        self.assertIs(self.object.anvil_account_exists(), False)

    def test_anvil_account_exists_associated_with_group(self):
        self.anvil_response_mock.add(responses.GET, self.api_url, status=204)
        self.assertIs(self.object.anvil_account_exists(), False)


class AccountAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.object = factories.AccountFactory.create()
        self.api_url = self.api_client.sam_entry_point + "/api/users/v1/" + self.object.email

    def get_api_add_to_group_url(self, group_name):
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member/" + self.object.email

    def get_api_remove_from_group_url(self, group_name):
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member/" + self.object.email

    def get_api_user_json_response(self, email):
        id = fake.bothify(text="#" * 21)
        return {
            "googleSubjectId": id,
            "userEmail": email,
            "userSubjectId": id,
        }

    def test_anvil_exists_does_exist(self):
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url,
            status=200,
            json=self.get_api_user_json_response(self.object.email),
        )
        self.assertIs(self.object.anvil_exists(), True)

    def test_anvil_exists_does_not_exist(self):
        self.anvil_response_mock.add(responses.GET, self.api_url, status=404, json={"message": "mock message"})
        self.assertIs(self.object.anvil_exists(), False)

    def test_anvil_exists_email_is_group(self):
        self.anvil_response_mock.add(responses.GET, self.api_url, status=204)
        self.assertIs(self.object.anvil_exists(), False)

    def test_anvil_remove_from_groups_in_no_groups(self):
        """anvil_remove_from_groups succeeds if the account is not in any groups."""
        # Make sure it doesn't fail and that there are no API calls.
        self.object.anvil_remove_from_groups()

    def test_anvil_remove_from_groups_in_one_group(self):
        """anvil_remove_from_groups succeeds if the account is in one group."""
        membership = factories.GroupAccountMembershipFactory.create(account=self.object)
        group = membership.group
        remove_from_group_url = self.get_api_remove_from_group_url(group.name)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url, status=204)
        self.object.anvil_remove_from_groups()
        # The membership was removed.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_anvil_remove_from_groups_in_two_groups(self):
        """anvil_remove_from_groups succeeds if the account is in two groups."""
        memberships = factories.GroupAccountMembershipFactory.create_batch(2, account=self.object)
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(group_1.name)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(group_2.name)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_1, status=204)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_2, status=204)
        self.object.anvil_remove_from_groups()
        # The membership was removed.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_anvil_remove_from_groups_api_failure(self):
        """anvil_remove_from_groups does not remove group memberships if any API call failed."""
        factories.GroupAccountMembershipFactory.create_batch(2, account=self.object)
        group_1 = self.object.groupaccountmembership_set.all()[0].group
        group_2 = self.object.groupaccountmembership_set.all()[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(group_1.name)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(group_2.name)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_1, status=204)
        self.anvil_response_mock.add(
            responses.DELETE,
            remove_from_group_url_2,
            status=409,
            json={"message": "api error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_remove_from_groups()
        # Only the successful membership was removed.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)

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
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url, status=204)
        self.object.deactivate()
        self.object.refresh_from_db()
        self.assertEqual(self.object.status, self.object.INACTIVE_STATUS)
        # The membership was removed from the app.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_deactivate_two_groups(self):
        """deactivate succeeds if the account is in two groups."""
        memberships = factories.GroupAccountMembershipFactory.create_batch(2, account=self.object)
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(group_1.name)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(group_2.name)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_1, status=204)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_2, status=204)
        self.object.deactivate()
        self.object.refresh_from_db()
        self.assertEqual(self.object.status, self.object.INACTIVE_STATUS)
        # The memberships were removed.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_deactivate_api_failure(self):
        """deactivate does not remove from any groups or set the status if an API call failed."""
        memberships = factories.GroupAccountMembershipFactory.create_batch(2, account=self.object)
        group_1 = memberships[0].group
        group_2 = memberships[1].group
        remove_from_group_url_1 = self.get_api_remove_from_group_url(group_1.name)
        remove_from_group_url_2 = self.get_api_remove_from_group_url(group_2.name)
        self.anvil_response_mock.add(responses.DELETE, remove_from_group_url_1, status=204)
        self.anvil_response_mock.add(
            responses.DELETE,
            remove_from_group_url_2,
            status=409,
            json={"message": "api error"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.deactivate()
        self.object.refresh_from_db()
        self.assertEqual(self.object.status, self.object.ACTIVE_STATUS)
        # Only the one membership was removed.
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)

    def test_reactivate_no_groups(self):
        """reactivate properly sets the status field if the account is not in any groups."""
        # Make sure it doesn't fail and that there are no API calls.
        self.object.status = self.object.INACTIVE_STATUS
        self.object.save()
        self.object.reactivate()
        self.object.refresh_from_db()
        self.assertEqual(self.object.status, self.object.ACTIVE_STATUS)


class ManagedGroupAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        self.object = factories.ManagedGroupFactory()
        self.api_url_exists = self.api_client.sam_entry_point + "/api/groups/v1/" + self.object.name
        self.api_url_create = self.api_client.sam_entry_point + "/api/groups/v1/" + self.object.name
        self.api_url_delete = self.api_client.sam_entry_point + "/api/groups/v1/" + self.object.name

    def test_anvil_exists_does_exist(self):
        self.anvil_response_mock.add(responses.GET, self.api_url_exists, status=200, json=self.object.email)
        self.assertIs(self.object.anvil_exists(), True)

    def test_anvil_exists_does_not_exist(self):
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url_exists,
            status=404,
            json={"message": "mock message"},
        )
        self.assertIs(self.object.anvil_exists(), False)

    def test_anvil_exists_internal_error(self):
        self.anvil_response_mock.add(
            responses.GET,
            self.api_url_exists,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_exists()

    def test_anvil_create_successful(self):
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url_create,
            status=201,
            json={"message": "mock message"},
        )
        self.object.anvil_create()

    def test_anvil_create_already_exists(self):
        """Returns documented response code when a group already exists."""
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url_create,
            status=409,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_create()

    def test_anvil_create_internal_error(
        self,
    ):
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url_create,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()

    def test_anvil_create_other(self):
        self.anvil_response_mock.add(
            responses.POST,
            self.api_url_create,
            status=499,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()

    def test_anvil_delete_existing(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=204,
        )
        self.object.anvil_delete()

    def test_anvil_delete_forbidden(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()

    def test_anvil_delete_not_found(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=404,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()

    def test_anvil_delete_in_use(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=409,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_delete()

    def test_anvil_delete_other(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=499,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()


class ManagedGroupAnVILImportAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    """Tests forthe ManagedGroup.anvil_import method."""

    def get_api_url(self):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1"

    def get_api_url_members(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member"

    def get_api_url_admins(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/admin"

    def test_anvil_import_admin_on_anvil(self):
        group_name = "test-group"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsAdminFactory(groupName=group_name),
                ]
            ).response,
        )
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group_name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group_name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.is_managed_by_app, True)
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)
        # No memberships were imported.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_anvil_import_admin_on_anvil_lowercase(self):
        group_name = "test-group"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsAdminFactory(groupName=group_name),
                ]
            ).response,
        )
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group_name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group_name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.is_managed_by_app, True)
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)

    def test_anvil_import_member_on_anvil(self):
        group_name = "test-group"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsMemberFactory(groupName=group_name),
                ]
            ).response,
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.is_managed_by_app, False)
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)

    def test_anvil_import_member_on_anvil_uppercase(self):
        group_name = "test-group"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsMemberFactory(groupName=group_name, role="Member"),
                ]
            ).response,
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.is_managed_by_app, False)
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)
        # No membership records were created.
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_anvil_import_member_and_admin(self):
        """When the SA is both a member and an admin, store the group as is_managed_by_app=True"""
        group_name = "test-group"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsMemberFactory(groupName=group_name),
                    api_factories.GroupDetailsAdminFactory(groupName=group_name),
                ]
            ).response,
        )
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group_name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group_name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.is_managed_by_app, True)
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)

    def test_anvil_import_member_and_admin_different_order(self):
        """When the SA is both an admin and a member (different order), store the group as is_managed_by_app=True"""
        group_name = "test-group"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsAdminFactory(groupName=group_name),
                    api_factories.GroupDetailsMemberFactory(groupName=group_name),
                ]
            ).response,
        )
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group_name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group_name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.is_managed_by_app, True)
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)

    def test_anvil_import_email_uppercase(self):
        group_name = "Test-Group"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsAdminFactory(groupName=group_name),
                ]
            ).response,
        )
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group_name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group_name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.email, "test-group@firecloud.org")
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)

    def test_anvil_import_not_member_or_admin_group_exists(self):
        group_name = "test-group"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            # Specify a different group so that we're not part of the group being imported.
            json=api_factories.GetGroupsResponseFactory(n_groups=3).response,
        )
        # Response for group email query.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group",
            status=200,
            # Assume we are not members since we didn't create the group ourselves.
            json="foo@example.com",
        )
        group = models.ManagedGroup.anvil_import(group_name)
        # Check values.
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.email, "foo@example.com")
        self.assertEqual(group.is_managed_by_app, False)
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)

    def test_anvil_import_not_member_or_admin_group_does_not_exist(self):
        group_name = "test-group"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            # Specify a different group so that we're not part of the group being imported.
            json=api_factories.GetGroupsResponseFactory(n_groups=3).response,
        )
        # Response for group email query.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group",
            status=404,
            # Assume we are not members since we didn't create the group ourselves.
            json=api_factories.ErrorResponseFactory().response,
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
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
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=500,
            # json={"message": "api error"},
            json=api_factories.ErrorResponseFactory().response,
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            models.ManagedGroup.anvil_import(group_name)
        # No object was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)

    def test_anvil_import_membership_api_internal_error(self):
        group_name = "test-group"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsAdminFactory(groupName=group_name),
                ]
            ).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group_name),
            status=500,
            json=api_factories.ErrorResponseFactory().response,
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            models.ManagedGroup.anvil_import(group_name)
        # No object was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)

    def test_imports_group_and_account_membership(self):
        """Group and account memberships are imported when they exist in the app."""
        child_group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        group_name = "test-group"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsFactory(),
                    api_factories.GroupDetailsAdminFactory(groupName=group_name),
                ]
            ).response,
        )
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group_name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[account.email]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group_name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[child_group.email]).response,
        )
        group = models.ManagedGroup.anvil_import(group_name)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        membership = models.GroupGroupMembership.objects.latest("pk")
        self.assertEqual(membership.parent_group, group)
        self.assertEqual(membership.child_group, child_group)
        self.assertEqual(membership.role, membership.ADMIN)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        membership = models.GroupAccountMembership.objects.latest("pk")
        self.assertEqual(membership.group, group)
        self.assertEqual(membership.account, account)
        self.assertEqual(membership.role, membership.MEMBER)


class ManagedGroupAnVILImportMembershipTest(AnVILAPIMockTestMixin, TestCase):
    def get_api_url(self):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1"

    def get_api_url_members(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/member"

    def get_api_url_admins(self, group_name):
        """Return the API url being called by the method."""
        return self.api_client.sam_entry_point + "/api/groups/v1/" + group_name + "/admin"

    def test_not_managed_by_app(self):
        group = factories.ManagedGroupFactory.create(is_managed_by_app=False)
        with self.assertRaises(exceptions.AnVILNotGroupAdminError) as e:
            group.anvil_import_membership()
        self.assertIn("not managed by app", str(e.exception))

    def test_no_members_or_admin(self):
        """Imports an admin child group when child group is in the app."""
        group = factories.ManagedGroupFactory.create()
        factories.ManagedGroupFactory.create()
        factories.AccountFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_group_admin_exists_in_app(self):
        """Imports an admin child group when child group is in the app."""
        group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[child_group.email]).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        membership = models.GroupGroupMembership.objects.latest("pk")
        self.assertEqual(membership.child_group, child_group)
        self.assertEqual(membership.parent_group, group)
        self.assertEqual(membership.role, membership.ADMIN)

    def test_group_admin_exists_in_app_case_insensitive(self):
        """Imports an admin child group when child group is in the app with a case-insensitive email match."""
        group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create(email="FoO@BaR.com")
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=["fOo@bAR.com"]).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        membership = models.GroupGroupMembership.objects.latest("pk")
        self.assertEqual(membership.child_group, child_group)
        self.assertEqual(membership.parent_group, group)
        self.assertEqual(membership.role, membership.ADMIN)

    def test_group_member_exists_in_app(self):
        """Imports an admin child group when child group is in the app."""
        group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[child_group.email]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        membership = models.GroupGroupMembership.objects.latest("pk")
        self.assertEqual(membership.child_group, child_group)
        self.assertEqual(membership.parent_group, group)
        self.assertEqual(membership.role, membership.MEMBER)

    def test_group_member_exists_in_app_case_insensitive(self):
        """Imports a member child group when child group is in the app with a case-insensitive email match."""
        group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create(email="FoO@bAr.com")
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=["fOo@BaR.com"]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        membership = models.GroupGroupMembership.objects.latest("pk")
        self.assertEqual(membership.child_group, child_group)
        self.assertEqual(membership.parent_group, group)
        self.assertEqual(membership.role, membership.MEMBER)

    def test_group_admin_not_in_app(self):
        """Does not import an admin child group when child group is not in the app."""
        group = factories.ManagedGroupFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=["test@example.com"]).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_group_member_not_in_app(self):
        """Does not import a member child group when child group is not in the app."""
        group = factories.ManagedGroupFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=["test@example.com"]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_same_group_both_admin_and_member(self):
        """Imports group as an admin when it is listed as both a member and admin on AnVIL."""
        group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[child_group.email]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[child_group.email]).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        membership = models.GroupGroupMembership.objects.latest("pk")
        self.assertEqual(membership.child_group, child_group)
        self.assertEqual(membership.parent_group, group)
        self.assertEqual(membership.role, membership.ADMIN)

    def test_one_member_one_admin(self):
        group = factories.ManagedGroupFactory.create()
        child_group_1 = factories.ManagedGroupFactory.create()
        child_group_2 = factories.ManagedGroupFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[child_group_1.email]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[child_group_2.email]).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)
        membership = models.GroupGroupMembership.objects.get(parent_group=group, child_group=child_group_1)
        self.assertEqual(membership.role, membership.MEMBER)
        membership = models.GroupGroupMembership.objects.get(parent_group=group, child_group=child_group_2)
        self.assertEqual(membership.role, membership.ADMIN)

    def test_two_group_admins(self):
        """Imports two admin members that exist in the app."""
        group = factories.ManagedGroupFactory.create()
        child_group_1 = factories.ManagedGroupFactory.create()
        child_group_2 = factories.ManagedGroupFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=[child_group_1.email, child_group_2.email]
            ).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)
        membership = models.GroupGroupMembership.objects.get(parent_group=group, child_group=child_group_1)
        self.assertEqual(membership.role, membership.ADMIN)
        membership = models.GroupGroupMembership.objects.get(parent_group=group, child_group=child_group_2)
        self.assertEqual(membership.role, membership.ADMIN)

    def test_two_group_members(self):
        """Imports two group members that exist in the app"""
        group = factories.ManagedGroupFactory.create()
        child_group_1 = factories.ManagedGroupFactory.create()
        child_group_2 = factories.ManagedGroupFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(
                response=[child_group_1.email, child_group_2.email]
            ).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupGroupMembership.objects.count(), 2)
        membership = models.GroupGroupMembership.objects.get(parent_group=group, child_group=child_group_1)
        self.assertEqual(membership.role, membership.MEMBER)
        membership = models.GroupGroupMembership.objects.get(parent_group=group, child_group=child_group_2)
        self.assertEqual(membership.role, membership.MEMBER)

    def test_account_admin_exists_in_app(self):
        """Imports an admin account when account is in the app."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[account.email]).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        membership = models.GroupAccountMembership.objects.latest("pk")
        self.assertEqual(membership.account, account)
        self.assertEqual(membership.group, group)
        self.assertEqual(membership.role, membership.ADMIN)

    def test_account_admin_exists_in_app_case_insensitive(self):
        """Imports an admin child group when child group is in the app with a case-insensitive email match."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create(email="FoO@BaR.com")
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=["fOo@bAR.com"]).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        membership = models.GroupAccountMembership.objects.latest("pk")
        self.assertEqual(membership.account, account)
        self.assertEqual(membership.group, group)
        self.assertEqual(membership.role, membership.ADMIN)

    def test_account_member_exists_in_app(self):
        """Imports an admin account when account is in the app."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[account.email]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        membership = models.GroupAccountMembership.objects.latest("pk")
        self.assertEqual(membership.account, account)
        self.assertEqual(membership.group, group)
        self.assertEqual(membership.role, membership.MEMBER)

    def test_gaccount_member_exists_in_app_case_insensitive(self):
        """Imports a member account when account is in the app with a case-insensitive email match."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create(email="FoO@bAr.com")
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=["fOo@BaR.com"]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        membership = models.GroupAccountMembership.objects.latest("pk")
        self.assertEqual(membership.account, account)
        self.assertEqual(membership.group, group)
        self.assertEqual(membership.role, membership.MEMBER)

    def test_account_admin_not_in_app(self):
        """Does not import an admin account when caccount is not in the app."""
        group = factories.ManagedGroupFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=["test@example.com"]).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_account_member_not_in_app(self):
        """Does not import a member account when account is not in the app."""
        group = factories.ManagedGroupFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=["test@example.com"]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)

    def test_same_account_both_admin_and_member(self):
        """Imports account as an admin when it is listed as both a member and admin on AnVIL."""
        group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[account.email]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[account.email]).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        membership = models.GroupAccountMembership.objects.latest("pk")
        self.assertEqual(membership.account, account)
        self.assertEqual(membership.group, group)
        self.assertEqual(membership.role, membership.ADMIN)

    def test_account_one_member_one_admin(self):
        group = factories.ManagedGroupFactory.create()
        account_1 = factories.AccountFactory.create()
        account_2 = factories.AccountFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[account_1.email]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(response=[account_2.email]).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        membership = models.GroupAccountMembership.objects.get(group=group, account=account_1)
        self.assertEqual(membership.role, membership.MEMBER)
        membership = models.GroupAccountMembership.objects.get(group=group, account=account_2)
        self.assertEqual(membership.role, membership.ADMIN)

    def test_two_account_admins(self):
        """Imports two admin accounts that exist in the app."""
        group = factories.ManagedGroupFactory.create()
        account_1 = factories.AccountFactory.create()
        account_2 = factories.AccountFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory(
                response=[account_1.email, account_2.email]
            ).response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        membership = models.GroupAccountMembership.objects.get(group=group, account=account_1)
        self.assertEqual(membership.role, membership.ADMIN)
        membership = models.GroupAccountMembership.objects.get(group=group, account=account_2)
        self.assertEqual(membership.role, membership.ADMIN)

    def test_two_account_members(self):
        """Imports two account members that exist in the app"""
        group = factories.ManagedGroupFactory.create()
        account_1 = factories.AccountFactory.create()
        account_2 = factories.AccountFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[account_1.email, account_2.email]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 2)
        membership = models.GroupAccountMembership.objects.get(group=group, account=account_1)
        self.assertEqual(membership.role, membership.MEMBER)
        membership = models.GroupAccountMembership.objects.get(group=group, account=account_2)
        self.assertEqual(membership.role, membership.MEMBER)

    def test_one_account_one_group(self):
        """Imports one account member and one group member that exist in the app."""
        group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory(response=[child_group.email, account.email]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
        )
        group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 1)
        membership = models.GroupAccountMembership.objects.get(group=group, account=account)
        self.assertEqual(membership.role, membership.MEMBER)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 1)
        membership = models.GroupGroupMembership.objects.get(parent_group=group, child_group=child_group)
        self.assertEqual(membership.role, membership.MEMBER)

    def test_api_error_group_member_call(self):
        """Nothing is imported when there is an error in the group membership call."""
        group = factories.ManagedGroupFactory.create()
        # child_group = factories.ManagedGroupFactory.create()
        # account = factories.AccountFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=404,
            json=api_factories.ErrorResponseFactory().response,
        )
        # Member response called before admin response.
        # self.anvil_response_mock.add(
        #     responses.GET,
        #     self.get_api_url_admins(group.name),
        #     status=200,
        #     json=api_factories.GetGroupMembershipAdminResponseFactory(
        #         response=[child_group.email, account.email]
        #     ).response,
        # )
        with self.assertRaises(anvil_api.AnVILAPIError):
            group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_api_error_group_admin_call(self):
        """Nothing is imported when there is an error in the group membership call."""
        group = factories.ManagedGroupFactory.create()
        child_group = factories.ManagedGroupFactory.create()
        account = factories.AccountFactory.create()
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_members(group.name),
            status=200,
            json=api_factories.ErrorResponseFactory(response=[child_group.email, account.email]).response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_admins(group.name),
            status=404,
            json=api_factories.ErrorResponseFactory().response,
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            group.anvil_import_membership()
        self.assertEqual(models.GroupAccountMembership.objects.count(), 0)
        self.assertEqual(models.GroupGroupMembership.objects.count(), 0)

    def test_group_email_different_than_name(self):
        """Email is set using email in response."""
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsMemberFactory(
                        groupName="test",
                        groupEmail="foo@bar.com",
                    ),
                ]
            ).response,
        )
        group = models.ManagedGroup.anvil_import("test")
        # Check values.
        self.assertEqual(group.name, "test")
        self.assertEqual(group.email, "foo@bar.com")
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)

    def test_group_email_different_than_name_lowercase(self):
        """Email is set to lowercase using email in response."""
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(),
            status=200,  # successful response code.
            json=api_factories.GetGroupsResponseFactory(
                response=[
                    api_factories.GroupDetailsMemberFactory(
                        groupName="test",
                        groupEmail="Foo@Bar.com",
                    ),
                ]
            ).response,
        )
        group = models.ManagedGroup.anvil_import("test")
        # Check values.
        self.assertEqual(group.name, "test")
        self.assertEqual(group.email, "foo@bar.com")
        # Check that it was saved.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        # Make sure it's the group that was returned.
        models.ManagedGroup.objects.get(pk=group.pk)


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
        self.anvil_response_mock.add(responses.GET, self.url_workspace, status=200)
        self.assertIs(self.object.anvil_exists(), True)

    def test_anvil_exists_does_not_exist(self):
        self.anvil_response_mock.add(
            responses.GET,
            self.url_workspace,
            status=404,
            json={"message": "mock message"},
        )
        self.assertIs(self.object.anvil_exists(), False)

    def test_anvil_exists_forbidden(self):
        self.anvil_response_mock.add(
            responses.GET,
            self.url_workspace,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_exists()

    def test_anvil_exists_internal_error(self):
        self.anvil_response_mock.add(
            responses.GET,
            self.url_workspace,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_exists()

    def test_anvil_create_successful(self):
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.url_create,
            status=201,
            match=[responses.matchers.json_params_matcher(json)],
        )
        self.object.anvil_create()

    def test_anvil_create_bad_request(self):
        """Returns documented response code when workspace already exists."""
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.url_create,
            status=400,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()

    def test_anvil_create_forbidden(self):
        """Returns documented response code when a workspace can't be created."""
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.url_create,
            status=403,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create()

    def test_anvil_create_404(self):
        """Returns documented response code when a workspace can't be created."""
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.url_create,
            status=404,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create()

    def test_anvil_create_already_exists(self):
        """Returns documented response code when a workspace already exists."""
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.url_create,
            status=409,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.object.anvil_create()

    def test_anvil_create_422(self):
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.url_create,
            status=422,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()

    def test_anvil_create_internal_error(self):
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.url_create,
            status=500,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()

    def test_anvil_create_other(self):
        json = {
            "namespace": self.object.billing_project.name,
            "name": self.object.name,
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            self.url_create,
            status=404,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()

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
        self.anvil_response_mock.add(
            responses.POST,
            self.url_create,
            status=201,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        self.object.anvil_create()

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
        self.anvil_response_mock.add(
            responses.POST,
            self.url_create,
            status=201,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        self.object.anvil_create()

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
        self.anvil_response_mock.add(
            responses.POST,
            self.url_create,
            status=400,
            match=[responses.matchers.json_params_matcher(json)],
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.object.anvil_create()

    def test_anvil_delete_existing(self):
        self.anvil_response_mock.add(responses.DELETE, self.url_workspace, status=202)
        self.object.anvil_delete()

    def test_anvil_delete_forbidden(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.url_workspace,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()

    def test_anvil_delete_not_found(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.url_workspace,
            status=404,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()

    def test_anvil_delete_in_use(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.url_workspace,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()

    def test_anvil_delete_other(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.url_workspace,
            status=499,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()


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
        self.anvil_response_mock.add(
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
                        "copyFilesWithPrefix": "notebooks",
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
        self.anvil_response_mock.add(
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
                        "copyFilesWithPrefix": "notebooks",
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
        self.anvil_response_mock.add(
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
                        "copyFilesWithPrefix": "notebooks",
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
        self.anvil_response_mock.add(
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
                        "copyFilesWithPrefix": "notebooks",
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
        self.anvil_response_mock.add(
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
                        "copyFilesWithPrefix": "notebooks",
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
        self.anvil_response_mock.add(
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
                        "copyFilesWithPrefix": "notebooks",
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
        self.anvil_response_mock.add(
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
                        "copyFilesWithPrefix": "notebooks",
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
        self.anvil_response_mock.add(
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
                        "copyFilesWithPrefix": "notebooks",
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
        self.anvil_response_mock.add(
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
                        "copyFilesWithPrefix": "notebooks",
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
        self.anvil_response_mock.add(
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
                        "copyFilesWithPrefix": "notebooks",
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
        self.anvil_response_mock.add(
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
                        "authorizationDomain": [{"membersGroupName": new_auth_domain.name}],
                        "copyFilesWithPrefix": "notebooks",
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
        self.anvil_response_mock.add(
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
                        "copyFilesWithPrefix": "notebooks",
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

    def setUp(self):
        super().setUp()
        self.api_json_response_acl = {"acl": {}}
        self.add_api_json_response_acl(self.service_account_email, "OWNER", can_compute=True, can_share=True)

    def get_billing_project_api_url(self, billing_project_name):
        return self.api_client.rawls_entry_point + "/api/billing/v2/" + billing_project_name

    def get_api_url(self, billing_project_name, workspace_name):
        return self.api_client.rawls_entry_point + "/api/workspaces/" + billing_project_name + "/" + workspace_name

    def get_api_json_response(
        self,
        billing_project,
        workspace,
        access="OWNER",
        auth_domains=[],
        is_locked=False,
    ):
        """Return a pared down version of the json response from the AnVIL API with only fields we need."""
        json_data = {
            "accessLevel": access,
            "owners": [],
            "workspace": {
                "authorizationDomain": [{"membersGroupName": g} for g in auth_domains],
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

    def test_anvil_import_billing_project_already_exists_in_django_db(self):
        """Can import a workspace if we are user of the billing project and already exists in Django."""
        """A workspace can be imported from AnVIL if we are owners and if the billing project exists."""
        workspace_name = "test-workspace"
        billing_project = factories.BillingProjectFactory.create()
        # No API call for billing projects.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
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
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
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

    def test_anvil_import_locked(self):
        """Sets is_locked to True if workspace is locked when importing."""
        workspace_name = "test-workspace"
        billing_project = factories.BillingProjectFactory.create()
        # No API call for billing projects.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name, is_locked=True),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        workspace = models.Workspace.anvil_import(
            billing_project.name, workspace_name, DefaultWorkspaceAdapter().get_type()
        )
        # Check workspace values.
        self.assertEqual(workspace.billing_project, billing_project)
        self.assertEqual(workspace.name, workspace_name)
        self.assertEqual(workspace.is_locked, True)
        # Check that it was saved.
        self.assertEqual(models.Workspace.objects.count(), 1)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)

    def test_anvil_import_billing_project_does_not_exist_in_django_db(self):
        """Can import a workspace if we are user of the billing project but it does not exist in Django yet."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        # Response from checking the billing project.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,
        )
        # Response from checking the workspace.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
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
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=404,  # billing project does not exist.
            json={"message": "other"},
        )
        # Response from checking the workspace.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
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
        # Response from checking the billing project.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,
        )
        # Response for workspace details.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name, access="READER"),
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
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace_name = "test-workspace"
        # No billing project API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name, access="READER"),
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

    def test_anvil_import_workspace_not_shared(self):
        """A workspace cannot be imported from AnVIL if we do not have access."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        # Response from checking the billing project.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,
        )
        # Response for workspace details.
        self.anvil_response_mock.add(
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
        # Call to check workspace list.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces",
            status=200,  # successful response code.
            json=[],
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
        self.assertEqual(models.BillingProject.objects.count(), 0)

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
        # Response from checking the billing project.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,
        )
        # Response for workspace details.
        self.anvil_response_mock.add(
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
        # Response from checking the billing project.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,
        )
        # Response for workspace details.
        self.anvil_response_mock.add(
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
        # Error in billing project call.
        self.anvil_response_mock.add(
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
        # Error in billing project call.
        self.anvil_response_mock.add(
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
        other_billing_project = factories.BillingProjectFactory.create(name="billing-project-1")
        factories.WorkspaceFactory.create(billing_project=other_billing_project, name=workspace_name)
        billing_project_name = "billing-project-2"
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,  # successful response code.
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
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
        factories.WorkspaceFactory.create(billing_project=billing_project, name="test-workspace-1")
        # No billing project API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
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
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace_name = "test-workspace"
        # Response for workspace query.
        workspace_url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_url,
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name, auth_domains=["auth-group"]),
        )
        # Response for group query.
        group_url = self.api_client.sam_entry_point + "/api/groups/v1"
        self.anvil_response_mock.add(
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
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
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

    def test_anvil_import_one_auth_group_exists_in_django(self):
        """Imports a workspace with an auth group that already exists in the app with app as member."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace_name = "test-workspace"
        group = factories.ManagedGroupFactory.create(name="auth-group")
        # Response for workspace query.
        workspace_url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_url,
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name, auth_domains=["auth-group"]),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
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

    def test_anvil_import_one_auth_group_admin_does_not_exist_in_django(self):
        """Imports a workspace with an auth group that the app is a member."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace_name = "test-workspace"
        # Response for workspace query.
        workspace_url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_url,
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name, auth_domains=["auth-group"]),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        # Response for group query.
        group_url = self.api_client.sam_entry_point + "/api/groups/v1"
        self.anvil_response_mock.add(
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
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/auth-group/member",
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/auth-group/admin",
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
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

    def test_anvil_import_two_auth_groups(self):
        """Imports two auth groups for a workspace."""
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace_name = "test-workspace"
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        # Response for workspace query.
        workspace_url = self.get_api_url(billing_project.name, workspace_name)
        self.anvil_response_mock.add(
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
        self.anvil_response_mock.add(
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
        # Group member/admins API calls.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/auth-admin/member",
            status=200,
            json=api_factories.GetGroupMembershipResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/auth-admin/admin",
            status=200,
            json=api_factories.GetGroupMembershipAdminResponseFactory().response,
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

    def test_can_import_as_owner_but_no_access(self):
        """Can import a workspace when we are an owner but not in the auth domain."""
        billing_project = factories.BillingProjectFactory.create()
        workspace_name = "test-workspace"
        # No API call for billing projects.
        # API call for workspace details.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=404,  # 404 - we can't call this without actually having access.
            json=api_factories.ErrorResponseFactory().response,
        )
        # Call to check workspace list - we will be listed as having "NO ACCESS"
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces",
            status=200,  # successful response code.
            json=[
                {
                    "accessLevel": "NO ACCESS",
                    "owners": [],
                    "workspace": {
                        "authorizationDomain": [{"membersGroupName": "auth-group"}],
                        "name": workspace_name,
                        "namespace": billing_project.name,
                        "isLocked": False,
                    },
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
        # Response for group query to import auth domain.
        # No records returned because we are not part of this group.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1",
            status=200,
            json=[],
        )
        # Response for group email query.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/auth-group",
            status=200,
            # Assume we are not members since we didn't create the group ourselves.
            json="foo@example.com",
        )
        # A workspace was created.
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertEqual(workspace.name, workspace_name)
        self.assertEqual(workspace.billing_project, billing_project)
        # Make sure it's the workspace returned.
        models.Workspace.objects.get(pk=workspace.pk)
        # The authorization domain was imported.
        self.assertEqual(models.ManagedGroup.objects.count(), 1)
        group = models.ManagedGroup.objects.latest("pk")
        self.assertEqual(group.name, "auth-group")
        self.assertEqual(group.is_managed_by_app, False)
        self.assertEqual(group.email, "foo@example.com")
        # The group was marked as an auth group of the workspace.
        self.assertEqual(workspace.authorization_domains.count(), 1)
        self.assertEqual(workspace.authorization_domains.get(), group)

    def test_api_error_group_email(self):
        """An API Error is raised when trying to retrieve the group email."""
        billing_project_name = "test-bp"
        workspace_name = "test-workspace"
        # Response from checking the billing project.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,
        )
        # Workspace details.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=404,  # 404 - we can't call this without actually having access.
            json=api_factories.ErrorResponseFactory().response,
        )
        # Call to check workspace list - we will be listed as having "NO ACCESS"
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces",
            status=200,  # successful response code.
            json=[
                {
                    "accessLevel": "NO ACCESS",
                    "owners": [],
                    "workspace": {
                        "authorizationDomain": [{"membersGroupName": "auth-group"}],
                        "name": workspace_name,
                        "namespace": billing_project_name,
                        "isLocked": False,
                    },
                }
            ],
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        # Response for group query to import auth domain.
        # No records returned because we are not part of this group.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1",
            status=200,
            json=[],
        )
        # Response for group email query.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.sam_entry_point + "/api/groups/v1/auth-group",
            status=404,  # Error response.
            json=api_factories.ErrorResponseFactory().response,
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            models.Workspace.anvil_import(
                billing_project_name,
                workspace_name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # No workspaces were created.
        self.assertEqual(models.Workspace.objects.count(), 0)
        # No billing projects were created.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        # No groups were created.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)

    def test_anvil_import_no_access_not_owner(self):
        """Cannot import a workspace when we are not an owner and not in the auth domain."""
        billing_project_name = "test-bp"
        workspace_name = "test-workspace"
        # Response from checking the billing project.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,
        )
        # Response for workspace details.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=404,  # 404 - we can't call this without actually having access.
            json=api_factories.ErrorResponseFactory().response,
        )
        # Call to check workspace list - we will be listed as having "NO ACCESS"
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces",
            status=200,  # successful response code.
            json=[
                {
                    "accessLevel": "NO ACCESS",
                    "owners": [],
                    "workspace": {
                        "authorizationDomain": [{"membersGroupName": "auth-group"}],
                        "name": workspace_name,
                        "namespace": billing_project_name,
                        "isLocked": False,
                    },
                }
            ],
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project_name, workspace_name),
            status=404,  # workspace is not shared.
            json=api_factories.ErrorResponseFactory().response,
        )
        with self.assertRaises(exceptions.AnVILNotWorkspaceOwnerError):
            models.Workspace.anvil_import(
                billing_project_name,
                workspace_name,
                workspace_type=DefaultWorkspaceAdapter().get_type(),
            )
        # No workspaces were created.
        self.assertEqual(models.Workspace.objects.count(), 0)
        # No billing projects were created.
        self.assertEqual(models.BillingProject.objects.count(), 0)
        # No groups were created.
        self.assertEqual(models.ManagedGroup.objects.count(), 0)

    def test_anvil_import_reader(self):
        """Cannot import a workspace when we are a reader."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        # Response from checking the billing project.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,
        )
        # Response for workspace details.
        self.anvil_response_mock.add(
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
        # Call to check workspace list.
        # We will be listed as a READER.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces",
            status=200,  # successful response code.
            json=[
                {
                    "accessLevel": "READER",
                    "owners": [],
                    "workspace": {
                        "name": workspace_name,
                        "namespace": billing_project_name,
                    },
                }
            ],
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
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_anvil_import_writer(self):
        """Cannot import a workspace when we are a writer."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        # Response from checking the billing project.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,
        )
        # Response for workspace details.
        self.anvil_response_mock.add(
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
        # Call to check workspace list.
        # We will be listed as a READER.
        self.anvil_response_mock.add(
            responses.GET,
            self.api_client.rawls_entry_point + "/api/workspaces",
            status=200,  # successful response code.
            json=[
                {
                    "accessLevel": "WRITER",
                    "owners": [],
                    "workspace": {
                        "name": workspace_name,
                        "namespace": billing_project_name,
                    },
                }
            ],
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
        self.assertEqual(models.BillingProject.objects.count(), 0)

    def test_api_internal_error_group_call(self):
        """Nothing is added when there is an API error on the /api/groups call."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        # Response for billing project query.
        billing_project_url = self.get_billing_project_api_url(billing_project_name)
        self.anvil_response_mock.add(responses.GET, billing_project_url, status=200)  # successful response code.
        # Response for workspace query.
        workspace_url = self.get_api_url(billing_project_name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_url,
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name, auth_domains=["auth-group"]),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project_name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        # Response for group query.
        group_url = self.api_client.sam_entry_point + "/api/groups/v1"
        self.anvil_response_mock.add(
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

    def test_imports_group_sharing_one_group_in_app_reader(self):
        """Imports a WorkspaceGroupSharing record if workspace is shared with a group in the app."""
        workspace_name = "test-workspace"
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create()
        # No API call for billing projects.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.add_api_json_response_acl(group.email, "READER", can_compute=False, can_share=False)
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # Check workspace sharing.
        self.assertEqual(workspace.workspacegroupsharing_set.count(), 1)
        object = workspace.workspacegroupsharing_set.all()[0]
        self.assertEqual(object.workspace, workspace)
        self.assertEqual(object.group, group)
        self.assertEqual(object.access, models.WorkspaceGroupSharing.READER)
        self.assertFalse(object.can_compute)

    def test_imports_group_sharing_one_group_in_app_writer(self):
        workspace_name = "test-workspace"
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create()
        # No API call for billing projects.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.add_api_json_response_acl(group.email, "WRITER", can_compute=False, can_share=False)
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # Check workspace sharing.
        self.assertEqual(workspace.workspacegroupsharing_set.count(), 1)
        object = workspace.workspacegroupsharing_set.all()[0]
        self.assertEqual(object.workspace, workspace)
        self.assertEqual(object.group, group)
        self.assertEqual(object.access, models.WorkspaceGroupSharing.WRITER)
        self.assertFalse(object.can_compute)

    def test_imports_group_sharing_one_group_in_app_owner(self):
        workspace_name = "test-workspace"
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create()
        # No API call for billing projects.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.add_api_json_response_acl(group.email, "OWNER", can_compute=False, can_share=False)
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # Check workspace sharing.
        self.assertEqual(workspace.workspacegroupsharing_set.count(), 1)
        object = workspace.workspacegroupsharing_set.all()[0]
        self.assertEqual(object.workspace, workspace)
        self.assertEqual(object.group, group)
        self.assertEqual(object.access, models.WorkspaceGroupSharing.OWNER)
        self.assertFalse(object.can_compute)

    def test_imports_group_sharing_one_group_in_app_case_insensitive(self):
        workspace_name = "test-workspace"
        group = factories.ManagedGroupFactory.create(name="test-group")
        billing_project = factories.BillingProjectFactory.create()
        # No API call for billing projects.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.add_api_json_response_acl(group.email, "reader", can_compute=False, can_share=False)
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # Check workspace sharing.
        self.assertEqual(workspace.workspacegroupsharing_set.count(), 1)
        object = workspace.workspacegroupsharing_set.all()[0]
        self.assertEqual(object.workspace, workspace)
        self.assertEqual(object.group, group)
        self.assertEqual(object.access, models.WorkspaceGroupSharing.READER)
        self.assertFalse(object.can_compute)

    def test_imports_group_sharing_two_groups_in_app(self):
        workspace_name = "test-workspace"
        group_1 = factories.ManagedGroupFactory.create(name="test-group-1")
        group_2 = factories.ManagedGroupFactory.create(name="test-group-2")
        billing_project = factories.BillingProjectFactory.create()
        # No API call for billing projects.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.add_api_json_response_acl(group_1.email, "READER", can_compute=False, can_share=False)
        self.add_api_json_response_acl(group_2.email, "WRITER", can_compute=False, can_share=False)
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # Check workspace sharing.
        self.assertEqual(workspace.workspacegroupsharing_set.count(), 2)
        object = workspace.workspacegroupsharing_set.all()[0]
        self.assertEqual(object.workspace, workspace)
        self.assertEqual(object.group, group_1)
        self.assertEqual(object.access, models.WorkspaceGroupSharing.READER)
        self.assertFalse(object.can_compute)
        object = workspace.workspacegroupsharing_set.all()[1]
        self.assertEqual(object.workspace, workspace)
        self.assertEqual(object.group, group_2)
        self.assertEqual(object.access, models.WorkspaceGroupSharing.WRITER)
        self.assertFalse(object.can_compute)

    def test_imports_group_sharing_group_not_in_app(self):
        workspace_name = "test-workspace"
        billing_project = factories.BillingProjectFactory.create()
        # No API call for billing projects.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.add_api_json_response_acl("foobar@firecloud.org", "READER", can_compute=False, can_share=False)
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # Check workspace sharing.
        self.assertEqual(workspace.workspacegroupsharing_set.count(), 0)

    def test_imports_group_sharing_shared_with_user(self):
        workspace_name = "test-workspace"
        billing_project = factories.BillingProjectFactory.create()
        # No API call for billing projects.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        # Response for ACL query.
        self.add_api_json_response_acl("test_email@example.com", "READER", can_compute=False, can_share=False)
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project.name, workspace_name),
            status=200,  # successful response code.
            json=self.api_json_response_acl,
        )
        workspace = models.Workspace.anvil_import(
            billing_project.name,
            workspace_name,
            workspace_type=DefaultWorkspaceAdapter().get_type(),
        )
        # Check workspace sharing.
        self.assertEqual(workspace.workspacegroupsharing_set.count(), 0)

    def test_acl_api_error(self):
        """Nothing is added when there is an API error on the workspace ACL call."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        factories.ManagedGroupFactory.create()
        # Response from checking the billing project.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_billing_project_api_url(billing_project_name),
            status=200,
        )
        # Response for workspace details.
        workspace_url = self.get_api_url(billing_project_name, workspace_name)
        self.anvil_response_mock.add(
            responses.GET,
            workspace_url,
            status=200,  # successful response code.
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        # Response for ACL query.
        self.anvil_response_mock.add(
            responses.GET,
            self.get_api_url_acl(billing_project_name, workspace_name),
            status=500,  # successful response code.
            json={"message": "api error"},
        )
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
        # No workspace group sharing objects were created.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)


class GroupGroupMembershipAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        self.parent_group = factories.ManagedGroupFactory(name="parent-group")
        self.child_group = factories.ManagedGroupFactory(name="child-group")
        self.object = factories.GroupGroupMembershipFactory(
            parent_group=self.parent_group,
            child_group=self.child_group,
            role=models.GroupGroupMembership.MEMBER,
        )
        self.api_url_create = (
            self.api_client.sam_entry_point + "/api/groups/v1/parent-group/member/child-group@firecloud.org"
        )
        self.api_url_delete = (
            self.api_client.sam_entry_point + "/api/groups/v1/parent-group/member/child-group@firecloud.org"
        )

    def test_anvil_create_successful(self):
        self.anvil_response_mock.add(responses.PUT, self.api_url_create, status=204)
        self.object.anvil_create()

    def test_anvil_create_successful_different_email(self):
        """Can add a child group to a parent group if the child group email is not default."""
        other_child_membership = factories.GroupGroupMembershipFactory.create(
            child_group__name="test",
            child_group__email="foo@bar.com",
            parent_group=self.parent_group,
        )
        api_url_create = self.api_client.sam_entry_point + "/api/groups/v1/parent-group/member/foo@bar.com"
        self.anvil_response_mock.add(responses.PUT, api_url_create, status=204)
        other_child_membership.anvil_create()

    def test_anvil_create_unsuccessful_403(self):
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url_create,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create()

    def test_anvil_create_unsuccessful_404(self):
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url_create,
            status=404,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create()

    def test_anvil_create_unsuccessful_500(self):
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url_create,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()

    def test_anvil_create_unsuccessful_other(self):
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url_create,
            status=499,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()

    def test_anvil_delete_successful(self):
        self.anvil_response_mock.add(responses.DELETE, self.api_url_delete, status=204)
        self.object.anvil_delete()

    def test_anvil_delete_successful_different_email(self):
        """Can delete a child group from a parent group if the child group email is not default."""
        other_child_membership = factories.GroupGroupMembershipFactory.create(
            child_group__name="test",
            child_group__email="foo@bar.com",
            parent_group=self.parent_group,
        )
        api_url_delete = self.api_client.sam_entry_point + "/api/groups/v1/parent-group/member/foo@bar.com"
        self.anvil_response_mock.add(responses.DELETE, api_url_delete, status=204)
        other_child_membership.anvil_delete()

    def test_anvil_delete_unsuccessful_403(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()

    def test_anvil_delete_unsuccessful_404(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=404,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()

    def test_anvil_delete_unsuccessful_500(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()

    def test_anvil_delete_unsuccessful_other(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=499,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()


class GroupAccountMembershipAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        group = factories.ManagedGroupFactory(name="test-group")
        account = factories.AccountFactory(email="test-account@example.com")
        self.object = factories.GroupAccountMembershipFactory(
            group=group, account=account, role=models.GroupAccountMembership.MEMBER
        )
        self.api_url_create = (
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/member/test-account@example.com"
        )
        self.api_url_delete = (
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/member/test-account@example.com"
        )

    def test_anvil_create_successful(self):
        self.anvil_response_mock.add(responses.PUT, self.api_url_create, status=204)
        self.object.anvil_create()

    def test_anvil_create_unsuccessful_403(self):
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url_create,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create()

    def test_anvil_create_unsuccessful_404(self):
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url_create,
            status=404,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create()

    def test_anvil_create_unsuccessful_500(self):
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url_create,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create()

    def test_anvil_create_unsuccessful_other(self):
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_url_create,
            status=499,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create()

    def test_anvil_delete_successful(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=204,
        )
        self.object.anvil_delete()

    def test_anvil_delete_unsuccessful_403(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=403,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_delete()

    def test_anvil_delete_unsuccessful_404(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=404,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()

    def test_anvil_delete_unsuccessful_500(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=500,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()

    def test_anvil_delete_unsuccessful_other(self):
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_url_delete,
            status=499,
            json={"message": "mock message"},
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()


class WorkspaceGroupSharingAnVILAPIMockTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self, *args, **kwargs):
        super().setUp()
        billing_project = factories.BillingProjectFactory.create(name="test-billing-project")
        workspace = factories.WorkspaceFactory.create(billing_project=billing_project, name="test-workspace")
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

    def get_api_json_response(self, invites_sent=[], users_not_found=[], users_updated=[]):
        return {
            "invitesSent": invites_sent,
            "usersNotFound": users_not_found,
            "usersUpdated": users_updated,
        }

    def test_anvil_create_or_update_successful(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_add)],
            json=self.get_api_json_response(users_updated=self.data_add),
        )
        self.object.anvil_create_or_update()

    def test_create_can_compute(self):
        """The correct API call is made when creating the object if can_compute is True."""
        self.object.can_compute = True
        self.object.save()
        self.data_add[0]["canCompute"] = True
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_add)],
            json=self.get_api_json_response(users_updated=self.data_add),
        )
        self.object.anvil_create_or_update()

    def test_anvil_create_or_update_unsuccessful_400(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=400,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.object.anvil_create_or_update()

    def test_anvil_create_or_update_unsuccessful_403(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=403,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.object.anvil_create_or_update()

    def test_anvil_create_or_update_unsuccessful_workspace_not_found(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=404,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_create_or_update()

    def test_anvil_create_or_update_unsuccessful_internal_error(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=500,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_create_or_update()

    def test_anvil_create_or_update_unsuccessful_other(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=499,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_add)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_create_or_update()

    def test_anvil_create_or_update_group_not_found_on_anvil(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_add)],
            # Add the full json response.
            json=self.get_api_json_response(users_not_found=self.data_add),
        )
        with self.assertRaises(exceptions.AnVILGroupNotFound):
            self.object.anvil_create_or_update()

    def test_anvil_delete_successful(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        self.object.anvil_delete()

    def test_delete_can_compute(self):
        """The correct API call is made when deleting an object if can_compute is True."""
        self.object.can_compute = True
        self.object.save()
        self.data_delete[0]["canCompute"] = True
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=200,
            match=[responses.matchers.json_params_matcher(self.data_delete)],
            json=self.get_api_json_response(users_updated=self.data_delete),
        )
        self.object.anvil_delete()

    def test_anvil_delete_unsuccessful_400(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=400,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.object.anvil_delete()

    def test_anvil_delete_unsuccessful_workspace_not_found(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=404,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.object.anvil_delete()

    def test_anvil_delete_unsuccessful_internal_error(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=500,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.object.anvil_delete()

    def test_anvil_delete_unsuccessful_other(self):
        self.anvil_response_mock.add(
            responses.PATCH,
            self.url,
            status=499,
            json={"message": "mock message"},
            match=[responses.matchers.json_params_matcher(self.data_delete)],
        )
        with self.assertRaises(anvil_api.AnVILAPIError):
            self.object.anvil_delete()
