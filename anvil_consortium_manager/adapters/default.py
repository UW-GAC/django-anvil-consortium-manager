"""Default adapters for the app."""

from .. import forms, models, tables
from .account import BaseAccountAdapter
from .workspace import BaseWorkspaceAdapter


class DefaultAccountAdapter(BaseAccountAdapter):
    """Default account adapter for use with the app."""

    list_table_class = tables.AccountTable


class DefaultWorkspaceAdapter(BaseWorkspaceAdapter):
    """Default workspace adapter for use with the app."""

    name = "Workspace"
    type = "workspace"
    description = "Default workspace"
    workspace_form_class = forms.WorkspaceCreateForm
    workspace_data_model = models.DefaultWorkspaceData
    workspace_data_form_class = forms.DefaultWorkspaceDataForm
    list_table_class = tables.WorkspaceTable
    workspace_detail_template_name = "anvil_consortium_manager/workspace_detail.html"
