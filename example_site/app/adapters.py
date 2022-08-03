from anvil_consortium_manager.adapter import DefaultWorkspaceAdapter

from . import forms, models, tables


class WorkspaceAdapter(DefaultWorkspaceAdapter):
    """Example adapter for workspaces."""

    workspace_data_type = "example_workspace_data"
    list_table_class = tables.ExampleWorkspaceDataTable
    workspace_data_model = models.ExampleWorkspaceData
    workspace_data_form_class = forms.ExampleWorkspaceDataForm
