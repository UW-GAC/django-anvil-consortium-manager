"""Contains default adapter for workspaces."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from extra_views import InlineFormSetFactory

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

    def get_workspace_data_inlines(self):
        """Return the workspace data inline form to be used when creating a workspace."""
        if self.workspace_data_model:
            if self.workspace_data_form:
                # Define a class and then return it.
                class WorkspaceDataFormsetFactory(InlineFormSetFactory):
                    model = self.workspace_data_model
                    form_class = self.workspace_data_form
                    factory_kwargs = {"can_delete": False}

                return [WorkspaceDataFormsetFactory]
            else:
                raise ImproperlyConfigured(
                    "workspace_data_form must be specified if workspace_data_model is specified."
                )
        else:
            return []


def get_adapter():
    adapter = import_string(settings.ANVIL_ADAPTER)()
    return adapter
