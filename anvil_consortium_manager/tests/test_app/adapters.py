from anvil_consortium_manager.adapters.account import BaseAccountAdapter
from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter

from . import forms, models, tables


class TestWorkspaceAdapter(BaseWorkspaceAdapter):
    """Test adapter for workspaces."""

    name = "Test workspace"
    type = "test"
    list_table_class = tables.TestWorkspaceDataTable
    workspace_data_model = models.TestWorkspaceData
    workspace_data_form_class = forms.TestWorkspaceDataForm
    workspace_detail_template_name = "test_workspace_detail.html"


class TestAccountAdapter(BaseAccountAdapter):
    """Test adapter for accounts."""

    list_table_class = tables.TestAccountTable
