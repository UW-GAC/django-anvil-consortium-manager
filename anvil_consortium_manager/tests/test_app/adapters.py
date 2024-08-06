from anvil_consortium_manager.adapters.account import BaseAccountAdapter
from anvil_consortium_manager.adapters.managed_group import BaseManagedGroupAdapter
from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter
from anvil_consortium_manager.forms import WorkspaceForm
from anvil_consortium_manager.tables import WorkspaceStaffTable, WorkspaceUserTable

from . import filters, forms, models, tables


class TestWorkspaceAdapter(BaseWorkspaceAdapter):
    """Test adapter for workspaces."""

    name = "Test workspace"
    type = "test"
    description = "Workspace type for testing"
    list_table_class_staff_view = tables.TestWorkspaceDataStaffTable
    list_table_class_view = tables.TestWorkspaceDataUserTable
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

    def get_extra_detail_context_data(self, workspace, request):
        extra_context = {}
        extra_context["extra_text"] = "Extra text"
        return extra_context


class TestManagedGroupAdapter(BaseManagedGroupAdapter):
    """Test adapter for ManagedGroups."""

    list_table_class_staff_view = tables.TestManagedGroupStaffTable
    list_table_class_view = tables.TestManagedGroupUserTable


class TestAccountAdapter(BaseAccountAdapter):
    """Test adapter for accounts."""

    list_table_class = tables.TestAccountStaffTable
    list_filterset_class = filters.TestAccountListFilter

    def get_autocomplete_queryset(self, queryset, q):
        if q:
            queryset = queryset.filter(email__startswith=q)
        return queryset

    def get_autocomplete_label(self, account):
        return "TEST {}".format(account.email)


class TestForeignKeyWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for TestForeignKeyWorkspace."""

    name = "Test foreign key workspace"
    type = "test_fk"
    description = "Workspace type for testing"
    list_table_class_staff_view = WorkspaceStaffTable
    list_table_class_view = WorkspaceUserTable
    workspace_form_class = WorkspaceForm
    workspace_data_model = models.TestForeignKeyWorkspaceData
    workspace_data_form_class = forms.TestForeignKeyWorkspaceDataForm
    workspace_detail_template_name = "workspace_detail.html"


class TestWorkspaceMethodsAdapter(BaseWorkspaceAdapter):
    """Adapter superclass for testing adapter methods."""

    name = "workspace adapter methods testing"
    type = "methods_tester"
    description = "Workspace type for testing custom adapter methods method"
    list_table_class_staff_view = WorkspaceStaffTable
    list_table_class_view = WorkspaceUserTable
    workspace_form_class = WorkspaceForm
    workspace_data_model = models.TestWorkspaceMethodsData
    workspace_data_form_class = forms.TestWorkspaceMethodsForm
    workspace_detail_template_name = "workspace_detail.html"


class TestBeforeWorkspaceCreateAdapter(TestWorkspaceMethodsAdapter):
    """Test adapter for workspaces with custom methods defined."""

    def before_anvil_create(self, workspace):
        # Append a -2 to the name of the workspace.
        workspace.name = workspace.name + "-2"
        workspace.save()


class TestAfterWorkspaceCreateAdapter(TestWorkspaceMethodsAdapter):
    """Test adapter for workspaces with custom methods defined."""

    def after_anvil_create(self, workspace):
        # Set the extra field to "FOO"
        workspace.testworkspacemethodsdata.test_field = "FOO"
        workspace.testworkspacemethodsdata.save()


class TestAfterWorkspaceImportAdapter(TestWorkspaceMethodsAdapter):
    """Test adapter for workspaces with custom methods defined."""

    def after_anvil_import(self, workspace):
        # Set the extra field.
        workspace.testworkspacemethodsdata.test_field = "imported!"
        workspace.testworkspacemethodsdata.save()
