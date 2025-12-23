from dataclasses import dataclass
from typing import List

from .. import models


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
            sharing = models.WorkspaceGroupSharing.objects.create(
                workspace=workspace,
                group=group,
                access=access,
                can_compute=can_compute,
            )
            sharing.save()
            sharing.anvil_create_or_update()
        else:
            # If the existing sharing record exists, make sure it has the correct permissions.
            if sharing.can_compute != can_compute or sharing.access != access:
                sharing.can_compute = can_compute
                sharing.access = access
                sharing.save()
                sharing.anvil_create_or_update()
