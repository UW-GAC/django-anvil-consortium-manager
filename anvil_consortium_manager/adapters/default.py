"""Default adapters for the app."""

from .. import filters, forms, models, tables
from .account import BaseAccountAdapter
from .workspace import BaseWorkspaceAdapter


class DefaultAccountAdapter(BaseAccountAdapter):
    """Default account adapter for use with the app."""

    list_table_class = tables.AccountStaffTable
    list_filterset_class = filters.AccountListFilter


class DefaultWorkspaceAdapter(BaseWorkspaceAdapter):
    """Default workspace adapter for use with the app."""

    name = "Workspace"
    type = "workspace"
    description = "Default workspace"
    workspace_form_class = forms.WorkspaceForm
    workspace_data_model = models.DefaultWorkspaceData
    workspace_data_form_class = forms.DefaultWorkspaceDataForm
    list_table_class_staff_view = tables.WorkspaceStaffTable
    workspace_detail_template_name = "anvil_consortium_manager/workspace_detail.html"
