from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter

from . import forms, models, tables


class CustomWorkspaceAdapter(BaseWorkspaceAdapter):
    """Example adapter for workspaces."""

    name = "Custom workspace"
    type = "custom"
    description = "Example custom workspace type for demo app"
    list_table_class_staff_view = tables.CustomWorkspaceDataTable
    workspace_form_class = forms.CustomWorkspaceForm
    workspace_data_model = models.CustomWorkspaceData
    workspace_data_form_class = forms.CustomWorkspaceDataForm
    workspace_detail_template_name = "app/custom_workspace_detail.html"
