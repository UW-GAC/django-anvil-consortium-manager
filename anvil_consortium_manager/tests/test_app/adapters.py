from anvil_consortium_manager.adapters.managed_group import BaseManagedGroupAdapter
from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter
from anvil_consortium_manager.models import GroupGroupMembership, WorkspaceGroupSharing

from ...adapters import mixins as adapter_mixins
from ...adapters.default import DefaultManagedGroupAdapter, DefaultWorkspaceAdapter
from . import forms, models, tables


class TestWorkspaceAdapter(BaseWorkspaceAdapter):
    """Test adapter for workspaces."""

    name = "Test workspace"
    type = "test"
    description = "Workspace type for testing"
    list_table_class_staff_view = tables.TestWorkspaceDataStaffTable
    list_table_class_view = tables.TestWorkspaceDataUserTable
    workspace_form_class = forms.TestWorkspaceForm
    workspace_data_model = models.TestWorkspaceData
    workspace_data_form_class = forms.TestWorkspaceDataForm
    workspace_detail_template_name = "test_workspace_detail.html"
    workspace_list_template_name = "test_workspace_list.html"


class TestManagedGroupAdapter(BaseManagedGroupAdapter):
    """Test adapter for ManagedGroups."""

    list_table_class = tables.TestManagedGroupTable


# Cannot easily be mocked due to inheritance.
class TestManagedGroupWithMembershipAdapter(
    adapter_mixins.GroupGroupMembershipAdapterMixin, DefaultManagedGroupAdapter
):
    membership_roles = [
        adapter_mixins.GroupGroupMembershipRole(
            child_group_name="test-member-group",
            role=GroupGroupMembership.RoleChoices.MEMBER,
        )
    ]


# TODO: cannot be mocked due to interitance
class TestWorkspaceWithSharingAdapter(adapter_mixins.WorkspaceSharingAdapterMixin, DefaultWorkspaceAdapter):
    """Test adapter using the WorkspaceSharingAdapterMixin."""

    type = "test_sharing"
    share_permissions = [
        adapter_mixins.WorkspaceSharingPermission(
            group_name="test-sharing-group",
            access=WorkspaceGroupSharing.READER,
            can_compute=False,
        )
    ]
