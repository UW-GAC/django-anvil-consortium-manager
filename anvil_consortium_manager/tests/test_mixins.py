from unittest.mock import patch

import responses
from django.test import TestCase

from .. import models
from ..adapters import mixins
from ..adapters.default import DefaultWorkspaceAdapter
from . import factories
from .utils import AnVILAPIMockTestMixin


class WorkspaceSharingAdapterMixinTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for WorkspaceSharingAdapterMixin."""

    def setUp(self):
        super().setUp()

        self.group = factories.ManagedGroupFactory.create()
        self.share_permission = mixins.WorkspaceSharingPermission(
            group_name=self.group.name,
            access=models.WorkspaceGroupSharing.READER,
            can_compute=False,
        )

        class TestAdapter(mixins.WorkspaceSharingAdapterMixin, DefaultWorkspaceAdapter):
            share_permissions = [self.share_permission]

        self.adapter = TestAdapter()

    def test_no_share_permissions_set(self):
        class BadTestAdapter(mixins.WorkspaceSharingAdapterMixin, DefaultWorkspaceAdapter):
            pass

        bad_adapter = BadTestAdapter()
        with self.assertRaises(NotImplementedError):
            bad_adapter.get_share_permissions()

    def test_empty_list_share_permissions(self):
        class BadTestAdapter(mixins.WorkspaceSharingAdapterMixin, DefaultWorkspaceAdapter):
            share_permissions = []

        bad_adapter = BadTestAdapter()
        with self.assertRaises(ValueError):
            bad_adapter.get_share_permissions()

    def test_after_anvil_create_reader_can_compute_false(self):
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for workspace owner.
        acls = [
            {
                "email": self.group.email,
                "accessLevel": models.WorkspaceGroupSharing.READER,
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )

        # Run the adapter method.
        self.adapter.after_anvil_create(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, models.WorkspaceGroupSharing.READER)
        self.assertEqual(sharing.can_compute, False)

    def test_after_anvil_create_writer_can_compute_false(self):
        """Test sharing a workspace with a group with WRITER access and can_compute=False."""
        permission = mixins.WorkspaceSharingPermission(
            group_name=self.group.name,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=False,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for workspace owner.
        acls = [
            {
                "email": permission.group_name + "@firecloud.org",
                "accessLevel": permission.access,
                "canShare": False,
                "canCompute": permission.can_compute,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )

        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission]):
            self.adapter.after_anvil_create(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, permission.access)
        self.assertEqual(sharing.can_compute, permission.can_compute)

    def test_after_anvil_create_writer_can_compute_true(self):
        """Test sharing a workspace with a group with WRITER access and can_compute=True."""
        permission = mixins.WorkspaceSharingPermission(
            group_name=self.group.name,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for workspace owner.
        acls = [
            {
                "email": permission.group_name + "@firecloud.org",
                "accessLevel": permission.access,
                "canShare": False,
                "canCompute": permission.can_compute,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )

        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission]):
            self.adapter.after_anvil_create(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, permission.access)
        self.assertEqual(sharing.can_compute, permission.can_compute)

    def test_after_anvil_create_owner_can_compute_false(self):
        """Test sharing a workspace with a group with Owner access and can_compute=False."""
        permission = mixins.WorkspaceSharingPermission(
            group_name=self.group.name,
            access=models.WorkspaceGroupSharing.OWNER,
            can_compute=False,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for workspace owner.
        acls = [
            {
                "email": permission.group_name + "@firecloud.org",
                "accessLevel": permission.access,
                "canShare": False,
                "canCompute": permission.can_compute,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )

        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission]):
            self.adapter.after_anvil_create(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, permission.access)
        self.assertEqual(sharing.can_compute, permission.can_compute)

    def test_after_anvil_create_owner_can_compute_true(self):
        """Test sharing a workspace with a group with Owner access and can_compute=True."""
        permission = mixins.WorkspaceSharingPermission(
            group_name=self.group.name,
            access=models.WorkspaceGroupSharing.OWNER,
            can_compute=True,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for workspace owner.
        acls = [
            {
                "email": permission.group_name + "@firecloud.org",
                "accessLevel": permission.access,
                "canShare": False,
                "canCompute": permission.can_compute,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )

        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission]):
            self.adapter.after_anvil_create(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, permission.access)
        self.assertEqual(sharing.can_compute, permission.can_compute)

    def test_after_anvil_create_group_does_not_exist(self):
        permission = mixins.WorkspaceSharingPermission(
            group_name="nonexistent-group",
            access=models.WorkspaceGroupSharing.READER,
            can_compute=False,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission]):
            self.adapter.after_anvil_create(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_after_anvil_create_multiple_share_permissions(self):
        """Test sharing a workspace with multiple groups."""
        group_reader = factories.ManagedGroupFactory.create()
        group_writer = factories.ManagedGroupFactory.create()
        group_owner = factories.ManagedGroupFactory.create()
        permission_reader = mixins.WorkspaceSharingPermission(
            group_name=group_reader.name,
            access=models.WorkspaceGroupSharing.READER,
            can_compute=False,
        )
        permission_writer = mixins.WorkspaceSharingPermission(
            group_name=group_writer.name,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        permission_owner = mixins.WorkspaceSharingPermission(
            group_name=group_owner.name,
            access=models.WorkspaceGroupSharing.OWNER,
            can_compute=True,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for all permissions.
        acls = [
            {
                "email": permission_reader.group_name + "@firecloud.org",
                "accessLevel": permission_reader.access,
                "canShare": False,
                "canCompute": permission_reader.can_compute,
            },
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        acls = [
            {
                "email": permission_writer.group_name + "@firecloud.org",
                "accessLevel": permission_writer.access,
                "canShare": False,
                "canCompute": permission_writer.can_compute,
            },
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        acls = [
            {
                "email": permission_owner.group_name + "@firecloud.org",
                "accessLevel": permission_owner.access,
                "canShare": False,
                "canCompute": permission_owner.can_compute,
            },
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission_reader, permission_writer, permission_owner]):
            self.adapter.after_anvil_create(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 3)
        sharing = models.WorkspaceGroupSharing.objects.get(group=group_reader)
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, group_reader)
        self.assertEqual(sharing.access, permission_reader.access)
        self.assertEqual(sharing.can_compute, permission_reader.can_compute)

    def test_after_anvil_import_reader_can_compute_false(self):
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for workspace owner.
        acls = [
            {
                "email": self.group.email,
                "accessLevel": models.WorkspaceGroupSharing.READER,
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        # Run the adapter method.
        self.adapter.after_anvil_import(workspace)
        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, models.WorkspaceGroupSharing.READER)
        self.assertEqual(sharing.can_compute, False)

    def test_after_anvil_import_writer_can_compute_false(self):
        """Test sharing a workspace with a group with WRITER access and can_compute=False."""
        permission = mixins.WorkspaceSharingPermission(
            group_name=self.group.name,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=False,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for workspace owner.
        acls = [
            {
                "email": permission.group_name + "@firecloud.org",
                "accessLevel": permission.access,
                "canShare": False,
                "canCompute": permission.can_compute,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )

        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission]):
            self.adapter.after_anvil_import(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, permission.access)
        self.assertEqual(sharing.can_compute, permission.can_compute)

    def test_after_anvil_import_writer_can_compute_true(self):
        """Test sharing a workspace with a group with WRITER access and can_compute=True."""
        permission = mixins.WorkspaceSharingPermission(
            group_name=self.group.name,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for workspace owner.
        acls = [
            {
                "email": permission.group_name + "@firecloud.org",
                "accessLevel": permission.access,
                "canShare": False,
                "canCompute": permission.can_compute,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )

        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission]):
            self.adapter.after_anvil_import(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, permission.access)
        self.assertEqual(sharing.can_compute, permission.can_compute)

    def test_after_anvil_import_owner_can_compute_false(self):
        """Test sharing a workspace with a group with Owner access and can_compute=False."""
        permission = mixins.WorkspaceSharingPermission(
            group_name=self.group.name,
            access=models.WorkspaceGroupSharing.OWNER,
            can_compute=False,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for workspace owner.
        acls = [
            {
                "email": permission.group_name + "@firecloud.org",
                "accessLevel": permission.access,
                "canShare": False,
                "canCompute": permission.can_compute,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )

        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission]):
            self.adapter.after_anvil_import(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, permission.access)
        self.assertEqual(sharing.can_compute, permission.can_compute)

    def test_after_anvil_import_owner_can_compute_true(self):
        """Test sharing a workspace with a group with Owner access and can_compute=True."""
        permission = mixins.WorkspaceSharingPermission(
            group_name=self.group.name,
            access=models.WorkspaceGroupSharing.OWNER,
            can_compute=True,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for workspace owner.
        acls = [
            {
                "email": permission.group_name + "@firecloud.org",
                "accessLevel": permission.access,
                "canShare": False,
                "canCompute": permission.can_compute,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )

        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission]):
            self.adapter.after_anvil_import(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, permission.access)
        self.assertEqual(sharing.can_compute, permission.can_compute)

    def test_after_anvil_import_group_does_not_exist(self):
        permission = mixins.WorkspaceSharingPermission(
            group_name="nonexistent-group",
            access=models.WorkspaceGroupSharing.READER,
            can_compute=False,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission]):
            self.adapter.after_anvil_import(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 0)

    def test_after_anvil_import_already_shared_correct_permissions(self):
        """Workspace is already shared with correct permissions; no API call should be made."""
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        sharing = factories.WorkspaceGroupSharingFactory.create(
            workspace=workspace,
            group=self.group,
            access=models.WorkspaceGroupSharing.READER,
            can_compute=False,
        )
        # Run the adapter method.
        self.adapter.after_anvil_import(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)  # No new objects.
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, models.WorkspaceGroupSharing.READER)
        self.assertEqual(sharing.can_compute, False)

    def test_after_anvil_import_already_shared_wrong_access(self):
        """Workspace is already shared but with wrong access; API call should be made to update."""
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        sharing = factories.WorkspaceGroupSharingFactory.create(
            workspace=workspace,
            group=self.group,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=False,
        )
        # API response for workspace owner.
        acls = [
            {
                "email": self.group.email,
                "accessLevel": models.WorkspaceGroupSharing.READER,
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )

        # Run the adapter method.
        self.adapter.after_anvil_import(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)  # No new objects.
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, models.WorkspaceGroupSharing.READER)
        self.assertEqual(sharing.can_compute, False)

    def test_after_anvil_import_already_shared_wrong_can_compute(self):
        """Workspace is already shared but with wrong access; API call should be made to update."""
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        sharing = factories.WorkspaceGroupSharingFactory.create(
            workspace=workspace,
            group=self.group,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        # API response for workspace owner.
        acls = [
            {
                "email": self.group.email,
                "accessLevel": models.WorkspaceGroupSharing.READER,
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )

        # Run the adapter method.
        self.adapter.after_anvil_import(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 1)  # No new objects.
        sharing = models.WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, self.group)
        self.assertEqual(sharing.access, models.WorkspaceGroupSharing.READER)
        self.assertEqual(sharing.can_compute, False)

    def test_after_anvil_import_multiple_share_permissions(self):
        """Test sharing a workspace with multiple groups."""
        group_reader = factories.ManagedGroupFactory.create()
        group_writer = factories.ManagedGroupFactory.create()
        group_owner = factories.ManagedGroupFactory.create()
        permission_reader = mixins.WorkspaceSharingPermission(
            group_name=group_reader.name,
            access=models.WorkspaceGroupSharing.READER,
            can_compute=False,
        )
        permission_writer = mixins.WorkspaceSharingPermission(
            group_name=group_writer.name,
            access=models.WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        permission_owner = mixins.WorkspaceSharingPermission(
            group_name=group_owner.name,
            access=models.WorkspaceGroupSharing.OWNER,
            can_compute=True,
        )
        workspace = factories.WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for all permissions.
        acls = [
            {
                "email": permission_reader.group_name + "@firecloud.org",
                "accessLevel": permission_reader.access,
                "canShare": False,
                "canCompute": permission_reader.can_compute,
            },
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        acls = [
            {
                "email": permission_writer.group_name + "@firecloud.org",
                "accessLevel": permission_writer.access,
                "canShare": False,
                "canCompute": permission_writer.can_compute,
            },
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        acls = [
            {
                "email": permission_owner.group_name + "@firecloud.org",
                "accessLevel": permission_owner.access,
                "canShare": False,
                "canCompute": permission_owner.can_compute,
            },
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        # Run the adapter method.
        with patch.object(self.adapter, "share_permissions", [permission_reader, permission_writer, permission_owner]):
            self.adapter.after_anvil_import(workspace)

        # Check for WorkspaceGroupSharing.
        self.assertEqual(models.WorkspaceGroupSharing.objects.count(), 3)
        sharing = models.WorkspaceGroupSharing.objects.get(group=group_reader)
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, group_reader)
        self.assertEqual(sharing.access, permission_reader.access)
        self.assertEqual(sharing.can_compute, permission_reader.can_compute)
