"""Contains default adapter for workspaces."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from . import forms, models, tables


class BaseWorkspaceAdapter(object):
    """Base class to inherit when customizing the workspace adapter."""

    list_table_class = None
    """Table class to use in a list of workspaces."""

    workspace_data_model = None
    """Optional model to use for storing extra data about workspaces."""

    workspace_data_form_class = None
    """Optional form for the model specified in ``workspace_data_model``."""

    def get_list_table_class(self):
        """Return the table class to use for the WorkspaceList view."""
        if not self.list_table_class:
            raise ImproperlyConfigured("Set `list_table_class`.")
        return self.list_table_class

    def get_workspace_data_model(self):
        """Return the `workspace_data_model`."""
        if not self.workspace_data_model:
            raise ImproperlyConfigured("Set `workspace_data_model`.")
        return self.workspace_data_model

    def get_workspace_data_form_class(self):
        """Return the form used to create `workspace_data_model`.

        This could be expanded to build a form from the workspace_data_model specified.
        """
        if not self.workspace_data_form_class:
            raise ImproperlyConfigured("Set `workspace_data_form_class`.")
        return self.workspace_data_form_class


class DefaultWorkspaceAdapter(BaseWorkspaceAdapter):
    """Default adapter for use with the app."""

    list_table_class = tables.WorkspaceTable
    workspace_data_model = models.DefaultWorkspaceData
    workspace_data_form_class = forms.DefaultWorkspaceDataForm


def get_adapter():
    adapter = import_string(settings.ANVIL_ADAPTER)()
    return adapter
