from anvil_consortium_manager.adapters.account import BaseAccountAdapter
from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter

from . import filters, forms, models, tables


class TestWorkspaceAdapter(BaseWorkspaceAdapter):
    """Test adapter for workspaces."""

    name = "Test workspace"
    type = "test"
    description = "Workspace type for testing"
    list_table_class = tables.TestWorkspaceDataTable
    workspace_form_class = forms.TestWorkspaceForm
    workspace_data_model = models.TestWorkspaceData
    workspace_data_form_class = forms.TestWorkspaceDataForm
    workspace_detail_template_name = "test_workspace_detail.html"

    def get_autocomplete_queryset(self, queryset, q, forwarded={}):
        billing_project = forwarded.get("billing_project", None)
        if billing_project:
            queryset = queryset.filter(workspace__billing_project=billing_project)

        if q:
            queryset = queryset.filter(workspace__name=q)
        return queryset


class TestAccountAdapter(BaseAccountAdapter):
    """Test adapter for accounts."""

    list_table_class = tables.TestAccountTable
    list_filterset_class = filters.TestAccountListFilter

    def get_autocomplete_queryset(self, queryset, q):
        if q:
            queryset = queryset.filter(email__startswith=q)
        return queryset

    def get_autocomplete_label(self, account):
        return "TEST {}".format(account.email)
