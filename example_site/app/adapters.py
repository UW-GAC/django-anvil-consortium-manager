from anvil_consortium_manager.adapter import DefaultWorkspaceAdapter

from . import forms, models, tables


class WorkspaceAdapter(DefaultWorkspaceAdapter):
    """Example adapter for workspaces."""

    list_table_class = tables.WorkspaceDataTable
    workspace_data_model = models.WorkspaceData
    workspace_data_form = forms.WorkspaceDataForm
