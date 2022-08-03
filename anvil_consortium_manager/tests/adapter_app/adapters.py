from anvil_consortium_manager.adapter import DefaultWorkspaceAdapter

from . import forms, models, tables


class TestWorkspaceAdapter(DefaultWorkspaceAdapter):
    """Example adapter for workspaces."""

    workspace_data_type = "test_workspace_adapter"
    list_table_class = tables.TestWorkspaceDataTable
    workspace_data_model = models.TestWorkspaceData
    workspace_data_form_class = forms.TestWorkspaceDataForm
