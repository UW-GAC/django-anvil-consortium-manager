from anvil_consortium_manager.adapter import DefaultWorkspaceAdapter

from .tables import WorkspaceDataTable


class WorkspaceAdapter(DefaultWorkspaceAdapter):
    """Example adapter for workspaces."""

    list_table_class = WorkspaceDataTable
