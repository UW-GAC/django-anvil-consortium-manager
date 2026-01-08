from anvil_consortium_manager.adapters.managed_group import BaseManagedGroupAdapter
from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter
from anvil_consortium_manager.forms import WorkspaceForm
from anvil_consortium_manager.models import GroupGroupMembership, WorkspaceGroupSharing
from anvil_consortium_manager.tables import WorkspaceStaffTable, WorkspaceUserTable

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


# TODO: can be mocked
class TestForeignKeyWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for TestForeignKeyWorkspace."""

    name = "Test foreign key workspace"
    type = "test_fk"
    description = "Workspace type for testing"
    list_table_class_staff_view = WorkspaceStaffTable
    list_table_class_view = WorkspaceUserTable
    workspace_form_class = WorkspaceForm
    workspace_data_model = models.TestForeignKeyWorkspaceData
    workspace_data_form_class = forms.TestForeignKeyWorkspaceDataForm
    workspace_detail_template_name = "workspace_detail.html"
    workspace_list_template_name = "workspace_list.html"


# TODO: can be mocked
class TestWorkspaceMethodsAdapter(BaseWorkspaceAdapter):
    """Adapter superclass for testing adapter methods."""

    name = "workspace adapter methods testing"
    type = "methods_tester"
    description = "Workspace type for testing custom adapter methods method"
    list_table_class_staff_view = WorkspaceStaffTable
    list_table_class_view = WorkspaceUserTable
    workspace_form_class = WorkspaceForm
    workspace_data_model = models.TestWorkspaceMethodsData
    workspace_data_form_class = forms.TestWorkspaceMethodsForm
    workspace_detail_template_name = "workspace_detail.html"
    workspace_list_template_name = "workspace_list.html"


# TODO: can be mocked
class TestBeforeWorkspaceCreateAdapter(TestWorkspaceMethodsAdapter):
    """Test adapter for workspaces with custom methods defined."""

    def before_anvil_create(self, workspace):
        # Append a -2 to the name of the workspace.
        workspace.name = workspace.name + "-2"
        workspace.save()


# TODO: can be mocked
class TestAfterWorkspaceCreateAdapter(TestWorkspaceMethodsAdapter):
    """Test adapter for workspaces with custom methods defined."""

    def after_anvil_create(self, workspace):
        # Set the extra field to "FOO"
        workspace.testworkspacemethodsdata.test_field = "FOO"
        workspace.testworkspacemethodsdata.save()


# TODO: can be mocked
class TestAfterWorkspaceImportAdapter(TestWorkspaceMethodsAdapter):
    """Test adapter for workspaces with custom methods defined."""

    def after_anvil_import(self, workspace):
        # Set the extra field.
        workspace.testworkspacemethodsdata.test_field = "imported!"
        workspace.testworkspacemethodsdata.save()


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
