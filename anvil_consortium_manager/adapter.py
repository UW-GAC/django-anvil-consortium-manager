"""Contains default adapter for workspaces."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from . import tables


class DefaultWorkspaceAdapter(object):
    """Default adapter for workspaces allowing extra data to be stored."""

    list_table_class = tables.WorkspaceTable
    """Table class to use in a list of workspaces."""

    workspace_data_model = None
    """Optional model to use for storing extra data about workspaces."""

    workspace_data_form = None
    """Optional form for the model specified in ``workspace_data_model``."""

    def get_list_table_class(self):
        return self.list_table_class

    def get_workspace_data_form(self):
        """This could be expanded to build a form from the workspace_data_model specified."""
        if self.workspace_data_model and not self.workspace_data_form:
            raise ImproperlyConfigured(
                "If specifying workspace_data_model, then workspace_data_form must also be set."
            )
        return self.workspace_data_form


def get_adapter():
    adapter = import_string(settings.ANVIL_ADAPTER)()
    return adapter
