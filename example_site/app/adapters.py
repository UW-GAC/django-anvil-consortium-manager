from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter

from . import forms, models, tables


class ExampleWorkspaceAdapter(BaseWorkspaceAdapter):
    """Example adapter for workspaces."""

    name = "Example workspace"
    type = "example"
    list_table_class = tables.ExampleWorkspaceDataTable
    workspace_data_model = models.ExampleWorkspaceData
    workspace_data_form_class = forms.ExampleWorkspaceDataForm
    workspace_detail_template_name = "example/workspace_detail.html"

