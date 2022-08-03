"""Contains default adapter for workspaces."""

from abc import ABC, abstractproperty

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from . import forms, models, tables


class BaseWorkspaceAdapter(ABC):
    """Base class to inherit when customizing the workspace adapter."""

    @abstractproperty
    def workspace_data_type(self):
        """String specifying the type of the workspace data object.

        This will be added to the :class:`anvil_consortium_manager.models.Workspace` `workspace_data_type` field."""
        ...

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

    def get_workspace_data_type(self):
        """Return the workspace data type specified in the adapter."""
        if not self.workspace_data_type:
            raise ImproperlyConfigured("Set `workspace_data_type`.")
        return self.workspace_data_type

    def get_list_table_class(self):
        """Return the table class to use for the WorkspaceList view."""
        if not self.list_table_class:
            raise ImproperlyConfigured("Set `list_table_class`.")
        return self.list_table_class

    def get_workspace_data_model(self):
        """Return the `workspace_data_model`."""
        if not self.workspace_data_model:
            raise ImproperlyConfigured("Set `workspace_data_model`.")
        elif not issubclass(self.workspace_data_model, models.BaseWorkspaceData):
            raise ImproperlyConfigured(
                "`workspace_data_model` must be a subclass of `BaseWorkspaceData`."
            )
        return self.workspace_data_model

    def get_workspace_data_form_class(self):
        """Return the form used to create `workspace_data_model`.

        This could be expanded to build a form from the workspace_data_model specified.
        """
        if not self.workspace_data_form_class:
            raise ImproperlyConfigured("Set `workspace_data_form_class`.")
        # Make sure it has the "workspace" field.
        if "workspace" not in self.workspace_data_form_class().fields:
            raise ImproperlyConfigured(
                "`workspace_data_form_class` must have a field for workspace."
            )
        return self.workspace_data_form_class


class DefaultWorkspaceAdapter(BaseWorkspaceAdapter):
    """Default adapter for use with the app."""

    workspace_data_type = "default_workspace_data"
    workspace_data_model = models.DefaultWorkspaceData
    workspace_data_form_class = forms.DefaultWorkspaceDataForm
    list_table_class = tables.WorkspaceTable


def get_adapter():
    try:
        adapter_class = import_string(settings.ANVIL_ADAPTER)
    except AttributeError:
        # Use the default adapter.
        adapter_class = DefaultWorkspaceAdapter
    adapter = adapter_class()
    if not isinstance(adapter, BaseWorkspaceAdapter):
        raise ImproperlyConfigured(
            "ANVIL_ADAPTER must inherit from `BaseWorkspaceAdapter`."
        )
    return adapter


class WorkspaceAdapterRegistry:
    """Registry to store workspace adapters for different model types."""

    def __init__(self):
        """Initialize the registry."""
        self._registry = {}  # Stores the adapters for each model type.

    def register(self, adapter):
        """Register an adapter."""
        pass


workspace_adapter_registry = WorkspaceAdapterRegistry()
