"""Default adapters for the app."""

from .. import filters, forms, models, tables
from .account import BaseAccountAdapter
from .managed_group import BaseManagedGroupAdapter
from .workspace import BaseWorkspaceAdapter


class DefaultAccountAdapter(BaseAccountAdapter):
    """Default account adapter for use with the app."""

    list_table_class = tables.AccountStaffTable
    list_filterset_class = filters.AccountListFilter


class DefaultManagedGroupAdapter(BaseManagedGroupAdapter):
    """Default adapter to use for ManagedGroups in the app."""

    list_table_class = tables.ManagedGroupStaffTable


class DefaultWorkspaceAdapter(BaseWorkspaceAdapter):
    """Default workspace adapter for use with the app."""

    name = "Workspace"
    type = "workspace"
    description = "Default workspace"
    workspace_form_class = forms.WorkspaceForm
    workspace_data_model = models.DefaultWorkspaceData
    workspace_data_form_class = forms.DefaultWorkspaceDataForm
    list_table_class_staff_view = tables.WorkspaceStaffTable
    list_table_class_view = tables.WorkspaceUserTable
    workspace_detail_template_name = "anvil_consortium_manager/workspace_detail.html"
