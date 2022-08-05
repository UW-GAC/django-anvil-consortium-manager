from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import import_string


class AnVILConsortiumManagerConfig(AppConfig):
    """Configuration for the anvil_consortium_manager app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "anvil_consortium_manager"
    verbose_name = "AnVIL Consortium Manager"

    def ready(self):
        super().ready()
        # Register specified adapters.
        # Import here because importing outside of this method raises the AppRegistryNotReady exception.
        from anvil_consortium_manager.adapter import workspace_adapter_registry

        adapter_modules = settings.ANVIL_WORKSPACE_ADAPTERS
        for adapter_module in adapter_modules:
            adapter = import_string(adapter_module)
            workspace_adapter_registry.register(adapter)
