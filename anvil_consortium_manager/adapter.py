"""Contains default adapter for workspaces."""

from abc import ABC, abstractproperty

from django.core.exceptions import ImproperlyConfigured

from . import forms, models, tables


class BaseWorkspaceAdapter(ABC):
    """Base class to inherit when customizing the workspace adapter."""

    @abstractproperty
    def type(self):
        """String specifying the workspace type.

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

    def get_type(self):
        """Return the workspace data type specified in the adapter."""
        if not self.type:
            raise ImproperlyConfigured("Set `type`.")
        return self.type

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

    type = "default"
    workspace_data_model = models.DefaultWorkspaceData
    workspace_data_form_class = forms.DefaultWorkspaceDataForm
    list_table_class = tables.WorkspaceTable


class AdapterAlreadyRegisteredError(Exception):
    """Exception raised when an adapter or its type is already registered."""


class AdapterNotRegisteredError(Exception):
    """Exception raised when an adapter is not registered."""


class WorkspaceAdapterRegistry:
    """Registry to store workspace adapters for different model types."""

    def __init__(self):
        """Initialize the registry."""
        self._registry = {}  # Stores the adapters for each model type.

    def register(self, adapter_class):
        """Register an adapter class using its type."""
        # Make sure the adapter has the correct subclass.
        if not issubclass(adapter_class, BaseWorkspaceAdapter):
            raise ImproperlyConfigured(
                "`adapter_class` must inherit from `BaseWorkspaceAdapter`."
            )
        # Make sure that an adapter for this type is not already registered.
        adapter = adapter_class()
        type = adapter.get_type()
        if type in self._registry:
            if self._registry[type] is adapter_class:
                raise AdapterAlreadyRegisteredError(
                    "adapter {} already exists in registry.".format(adapter_class)
                )
            else:
                raise AdapterAlreadyRegisteredError(
                    "type `{}` already exists in registry.".format(type)
                )
        # Add the adapter to the registry.
        self._registry[type] = adapter_class

    def unregister(self, adapter_class):
        """Unregister an adapter class."""
        if not issubclass(adapter_class, BaseWorkspaceAdapter):
            raise ImproperlyConfigured(
                "`adapter_class` must inherit from `BaseWorkspaceAdapter`."
            )
        type = adapter_class().type
        if type in self._registry:
            # Check that the registered adapter is the same class and raise an exception if not.
            registered_adapter = self._registry[type]
            if registered_adapter is not adapter_class:
                raise AdapterNotRegisteredError(
                    "adapter {} has not been registered yet.".format(adapter_class)
                )
            else:
                del self._registry[type]
        else:
            raise AdapterNotRegisteredError(
                "adapter {} has not been registered yet.".format(adapter_class)
            )

    def get_adapter(self, type):
        print(self._registry.keys())
        adapter_class = self._registry[type]
        return adapter_class()


# Initalize a global variable for the registry for use throughout the app.
# Adapters will be added to the registry in the AppConfig for this app via a setting.
workspace_adapter_registry = WorkspaceAdapterRegistry()
