"""Default adapters for the app."""

from .. import forms, models, tables
from .workspace import BaseWorkspaceAdapter


class DefaultWorkspaceAdapter(BaseWorkspaceAdapter):
    """Default adapter for use with the app."""

    name = "Workspace"
    type = "workspace"
    workspace_data_model = models.DefaultWorkspaceData
    workspace_data_form_class = forms.DefaultWorkspaceDataForm
    list_table_class = tables.WorkspaceTable
    workspace_detail_template_name = "anvil_consortium_manager/workspace_detail.html"
