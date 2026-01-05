from dataclasses import dataclass
from typing import List

from .. import models


@dataclass(frozen=True)
class GroupGroupMembershipRole:
    child_group_name: str
    role: models.GroupGroupMembership


class GroupGroupMembershipAdapterMixin:
    """Mixin to add membership functionality to ManagedGroups.

    Subclasses must define membership_roles as a list of `GroupGroupMembershipRole` instances.

    Attributes:

    """

    membership_roles: List[GroupGroupMembershipRole] = None

    def get_membership_roles(self):
        """Validate and return the permissions to grant."""
        if self.membership_roles is None:
            raise NotImplementedError(
                "GroupGroupMembershipAdapterMixin: You must membership_roles roles"
                " in the subclass or override get_membership_roles()."
            )
        if not self.membership_roles:
            raise ValueError("GroupGroupMembershipAdapterMixin: membership_roles cannot be empty.")
        return self.membership_roles

    def after_anvil_create(self, group):
        """Add specified group membership roles after group is created."""
        pass
        super().after_anvil_create(group)
        self._add_group_members(group)

    def _add_group_members(self, group):
        """Loop over all roles and add new memberships with the specified role."""
        for membership in self.get_membership_roles():
            self._add_group_member(group, membership.child_group_name, membership.role)

    def _add_group_member(self, group, child_group_name, role):
        """Add specific new membership with the specified role."""
        try:
            child_group = models.ManagedGroup.objects.get(name=child_group_name)
        except models.ManagedGroup.DoesNotExist:
            # Child group does not exist - this is ok.
            # Maybe we should log this.
            return
        try:
            membership = models.GroupGroupMembership.objects.get(
                parent_group=group,
                child_group=child_group,
            )
        except models.GroupGroupMembership.DoesNotExist:
            membership = models.GroupGroupMembership(
                parent_group=group,
                child_group=child_group,
                role=role,
            )
            membership.full_clean()
            membership.save()
            membership.anvil_create()
        else:
            # If the existing sharing record exists, make sure it has the correct permissions.
            if membership.role != role:
                membership.anvil_delete()
                membership.role = role
                membership.full_clean()
                membership.save()
                membership.anvil_create()


@dataclass(frozen=True)
class WorkspaceSharingPermission:
    group_name: str
    access: models.WorkspaceGroupSharing
    can_compute: bool


class WorkspaceSharingAdapterMixin:
    """Mixin to add sharing functionality to workspace adapters.

    Subclasses must define `share_permissions` as a list of WorkspaceSharingPermission

    Attributes:
        share_permissions (List[WorkspaceSharingPermission]): List of permissions to grant to groups.

    Details:
        After a workspace is created or imported, it will be shared with the specified groups
        with the defined access levels and compute permissions.
    """

    share_permissions: List[WorkspaceSharingPermission] = None

    def get_share_permissions(self):
        """Validate and return the permissions to grant."""
        print("get share permissions")
        if self.share_permissions is None:
            raise NotImplementedError(
                "WorkspaceSharingAdapterMixin: You must define share_permissions"
                " in the subclass or override get_share_permissions()."
            )
        if not self.share_permissions:
            raise ValueError("WorkspaceSharingAdapterMixin: share_permissions cannot be empty.")
        return self.share_permissions

    def after_anvil_create(self, workspace):
        """Share the workspace with specified groups after creation."""
        super().after_anvil_create(workspace)
        self._share_workspace_with_groups(workspace)

    def after_anvil_import(self, workspace):
        """Share the workspace with specified groups after import."""
        super().after_anvil_import(workspace)
        self._share_workspace_with_groups(workspace)

    def _share_workspace_with_groups(self, workspace):
        """Loop over all groups and share the workspace with the specified permission for that group."""
        for sharing in self.get_share_permissions():
            self._share_workspace_with_group(workspace, sharing.group_name, sharing.access, sharing.can_compute)

    def _share_workspace_with_group(self, workspace, group_name, access, can_compute):
        """Share the workspace with a specific group."""
        try:
            group = models.ManagedGroup.objects.get(name=group_name)
        except models.ManagedGroup.DoesNotExist:
            return
        try:
            sharing = models.WorkspaceGroupSharing.objects.get(
                workspace=workspace,
                group=group,
            )
        except models.WorkspaceGroupSharing.DoesNotExist:
            sharing = models.WorkspaceGroupSharing(
                workspace=workspace,
                group=group,
                access=access,
                can_compute=can_compute,
            )
            sharing.full_clean()
            sharing.save()
            sharing.anvil_create_or_update()
        else:
            # If the existing sharing record exists, make sure it has the correct permissions.
            if sharing.can_compute != can_compute or sharing.access != access:
                sharing.can_compute = can_compute
                sharing.access = access
                sharing.full_clean()
                sharing.save()
                sharing.anvil_create_or_update()
