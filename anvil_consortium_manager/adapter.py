"""Contains default adapter for workspaces."""

from django.conf import settings
from django.utils.module_loading import import_string

from . import tables


class DefaultWorkspaceAdapter(object):
    """Default adapter for workspaces allowing extra data to be stored."""

    list_table_class = None
    """Table class to use in a list of workspaces."""

    def get_list_table_class(self):
        """Returns the table class to use for a list of workspaces."""
        if self.list_table_class:
            return self.list_table_class
        else:
            # Default.
            return tables.WorkspaceTable


def get_adapter():
    adapter = import_string(settings.ANVIL_ADAPTER)()
    return adapter
