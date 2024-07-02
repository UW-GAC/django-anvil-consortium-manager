"""Contains default adapter for workspaces."""

from abc import ABC, abstractproperty

from django.core.exceptions import ImproperlyConfigured
from django.forms import ModelForm
from django.utils.module_loading import import_string

from .. import app_settings, models


class BaseWorkspaceAdapter(ABC):
    """Base class to inherit when customizing the workspace adapter."""

    @abstractproperty
    def name(self):
        """String specifying the namee of this type of workspace."""
        ...

    @abstractproperty
    def type(self):
        """String specifying the workspace type.

        This will be added to the :class:`anvil_consortium_manager.models.Workspace` `workspace_type` field."""
        ...

    @abstractproperty
    def description(self):
        """String with a description of the workspace/

        This will be displayed on the workspace landing page."""
        ...

    @abstractproperty
    def list_table_class_staff_view(self):
        """Table class to use in a list of workspaces for users with staff view permission."""
        ...

    @abstractproperty
    def workspace_form_class(self):
        """Custom form to use when creating a Workspace."""
        ...

    @abstractproperty
    def workspace_data_model(self):
        """Model to use for storing extra data about workspaces."""
        ...

    @abstractproperty
    def workspace_data_form_class(self):
        """Form for the model specified in ``workspace_data_model``."""
        ...

    @abstractproperty
    def workspace_detail_template_name(self):
        """path to workspace detail template"""
        ...

    def get_name(self):
        """Return the name specified in the adapter."""
        if not self.name:
            raise ImproperlyConfigured("Set `name`.")
        return self.name

    def get_type(self):
        """Return the workspace data type specified in the adapter."""
        if not self.type:
            raise ImproperlyConfigured("Set `type`.")
        return self.type

    def get_description(self):
        """Return the workspace description specified in the adapter."""
        if not self.description:
            raise ImproperlyConfigured("Set `description`.")
        return self.description

    def get_list_table_class_staff_view(self):
        """Return the table class to use for the WorkspaceListByType view for staff."""
        if not self.list_table_class_staff_view:
            raise ImproperlyConfigured("Set `list_table_class_staff_view` in `{}`.".format(type(self)))
        return self.list_table_class_staff_view

    def get_list_table_class_view(self):
        """Return the table class to use for the WorkspaceListByType view for non-staff users."""
        if not self.list_table_class_view:
            raise ImproperlyConfigured("Set `list_table_class_view` in `{}`.".format(type(self)))
        return self.list_table_class_view

    def get_workspace_form_class(self):
        """Return the form used to create a `Workspace`."""
        if not self.workspace_form_class:
            raise ImproperlyConfigured("Set `workspace_data_form_class`.")
        # Make sure it is a model form
        if not issubclass(self.workspace_form_class, ModelForm):
            raise ImproperlyConfigured("workspace_form_class must be a subclass of ModelForm.")
        # Make sure it has the correct model set.
        if self.workspace_form_class.Meta.model != models.Workspace:
            raise ImproperlyConfigured(
                "workspace_form_class Meta model field must be anvil_consortium_manager.models.Workspace."
            )
        return self.workspace_form_class

    def get_workspace_data_model(self):
        """Return the `workspace_data_model`."""
        if not self.workspace_data_model:
            raise ImproperlyConfigured("Set `workspace_data_model`.")
        elif not issubclass(self.workspace_data_model, models.BaseWorkspaceData):
            raise ImproperlyConfigured("`workspace_data_model` must be a subclass of `BaseWorkspaceData`.")
        return self.workspace_data_model

    def get_workspace_data_form_class(self):
        """Return the form used to create `workspace_data_model`.

        This could be expanded to build a form from the workspace_data_model specified.
        """
        if not self.workspace_data_form_class:
            raise ImproperlyConfigured("Set `workspace_data_form_class`.")
        # Make sure it has the "workspace" field.
        if "workspace" not in self.workspace_data_form_class().fields:
            raise ImproperlyConfigured("`workspace_data_form_class` must have a field for workspace.")
        return self.workspace_data_form_class

    def get_workspace_detail_template_name(self):
        """Return the workspace detail template name specified in the adapter."""
        if not self.workspace_detail_template_name:
            raise ImproperlyConfigured("Set `workspace_detail_template_name`.")
        return self.workspace_detail_template_name

    def get_autocomplete_queryset(self, queryset, q, forwarded=None):
        """Return the queryset after filtering for WorkspaceAutocompleteByType view.

        The default filtering is that the workspace name contains the queryset, case-
        insensitive. If desired, custom autocomplete filtering for a workspace type can
        be implemented by overriding this method."""
        if q:
            queryset = queryset.filter(workspace__name__icontains=q)
        return queryset

    def get_extra_detail_context_data(self, workspace, request):
        """Return the extra context specified in the adapter.

        Args:
            workspace (anvil_consortium_manager.models.Workspace): The workspace for which to get the extra context.
            request (django.http.HttpRequest): The request for the view.

        Returns:
            dict: Extra context to add to or update the workspace detail view.
        """

        return {}

    def before_workspace_create(self, workspace):
        """Custom actions to take after a workspace is created on AnVIL."""
        pass

    def after_workspace_create(self, workspace):
        """Custom actions to take after a workspace is created on AnVIL."""
        pass

    def after_workspace_import(self, workspace):
        """Custom actions to take after a workspace is imported from AnVIL."""
        pass


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
            raise ImproperlyConfigured("`adapter_class` must inherit from `BaseWorkspaceAdapter`.")
        # Make sure that an adapter for this type is not already registered.
        adapter = adapter_class()
        type = adapter.get_type()
        if type in self._registry:
            if self._registry[type] is adapter_class:
                raise AdapterAlreadyRegisteredError("adapter {} already exists in registry.".format(adapter_class))
            else:
                raise AdapterAlreadyRegisteredError("type `{}` already exists in registry.".format(type))
        # Add the adapter to the registry.
        self._registry[type] = adapter_class

    def unregister(self, adapter_class):
        """Unregister an adapter class."""
        if not issubclass(adapter_class, BaseWorkspaceAdapter):
            raise ImproperlyConfigured("`adapter_class` must inherit from `BaseWorkspaceAdapter`.")
        type = adapter_class().type
        if type in self._registry:
            # Check that the registered adapter is the same class and raise an exception if not.
            registered_adapter = self._registry[type]
            if registered_adapter is not adapter_class:
                raise AdapterNotRegisteredError("adapter {} has not been registered yet.".format(adapter_class))
            else:
                del self._registry[type]
        else:
            raise AdapterNotRegisteredError("adapter {} has not been registered yet.".format(adapter_class))

    def get_adapter(self, type):
        """ "Return an instance of the adapter for a given workspace ``type``."""
        adapter_class = self._registry[type]
        return adapter_class()

    def get_registered_adapters(self):
        """Return the registered adapters."""
        return self._registry

    def get_registered_names(self):
        """Return a dictionary of registered adapter names."""
        return {key: value().get_name() for (key, value) in self._registry.items()}

    def populate_from_settings(self):
        """Populate the workspace adapter registry from settings. Called by AppConfig ready() method."""
        adapter_modules = app_settings.WORKSPACE_ADAPTERS
        if len(self._registry):
            msg = "Registry has already been populated."
            raise RuntimeError(msg)
        if not adapter_modules:
            msg = (
                "ANVIL_WORKSPACE_ADAPTERS must specify at least one adapter. Did you mean to use "
                "the default `anvil_consortium_manager.adapters.default.DefaultWorkspaceAdapter`?"
            )
            raise ImproperlyConfigured(msg)
        for adapter_module in adapter_modules:
            adapter = import_string(adapter_module)
            self.register(adapter)


# Initalize a global variable for the registry for use throughout the app.
# Adapters will be added to the registry in the AppConfig for this app via a setting.
workspace_adapter_registry = WorkspaceAdapterRegistry()
"""Global variable to store all registered workspace adapters.

Adapters specified in the ``ANVIL_WORKSPACE_ADAPTERS`` setting will be registered in
the app config's ``.ready()`` method.
"""
