from anvil_consortium_manager.adapters.account import BaseAccountAdapter
from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter

from . import forms, models, tables


class TestWorkspaceAdapter(BaseWorkspaceAdapter):
    """Test adapter for workspaces."""

    name = "Test workspace"
    type = "test"
    description = "Workspace type for testing"
    list_table_class = tables.TestWorkspaceDataTable
    workspace_data_model = models.TestWorkspaceData
    workspace_data_form_class = forms.TestWorkspaceDataForm
    workspace_detail_template_name = "test_workspace_detail.html"

    def get_autocomplete_queryset(self, queryset, q, forwarded={}):
        if q:
            queryset = queryset.filter(workspace__name=q)
        return queryset


class TestAccountAdapter(BaseAccountAdapter):
    """Test adapter for accounts."""

    list_table_class = tables.TestAccountTable

    def get_autocomplete_queryset(self, queryset, q):
        if q:
            queryset = queryset.filter(email__startswith=q)
        return queryset

    def get_autocomplete_label(self, account):
        return "TEST {}".format(account.email)
