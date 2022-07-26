"""Contains default adapter for workspaces."""

from abc import ABC, abstractproperty

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from . import forms, models, tables


class BaseWorkspaceAdapter(ABC):
    """Base class to inherit when customizing the workspace adapter."""

    @abstractproperty
    def list_table_class(self):
        """Table class to use in a list of workspaces."""
        ...

    @abstractproperty
    def workspace_data_model(self):
        """Model to use for storing extra data about workspaces."""
        ...

    @abstractproperty
    def workspace_data_form_class(self):
        """Form for the model specified in ``workspace_data_model``."""
        ...

    def get_list_table_class(self):
        """Return the table class to use for the WorkspaceList view."""
        if not self.list_table_class:
            raise ImproperlyConfigured("Set `list_table_class`.")
        return self.list_table_class

    def get_workspace_data_model(self):
        """Return the `workspace_data_model`."""
        if not self.workspace_data_model:
            raise ImproperlyConfigured("Set `workspace_data_model`.")
        elif not issubclass(self.workspace_data_model, models.AbstractWorkspaceData):
            raise ImproperlyConfigured(
                "`workspace_data_model` must be a subclass of `AbstractWorkspaceData`."
            )
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
    try:
        adapter_setting = settings.ANVIL_ADAPTER
    except AttributeError:
        raise ImproperlyConfigured("Set `ANVIL_ADAPTER` in your settings file.")
    adapter = import_string(adapter_setting)()
    if not isinstance(adapter, BaseWorkspaceAdapter):
        raise ImproperlyConfigured(
            "ANVIL_ADAPTER must inherit from `BaseWorkspaceAdapter`."
        )
    return adapter
