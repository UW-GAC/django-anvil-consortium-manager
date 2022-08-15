from django.apps import AppConfig


class AnVILConsortiumManagerConfig(AppConfig):
    """Configuration for the anvil_consortium_manager app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "anvil_consortium_manager"
    verbose_name = "AnVIL Consortium Manager"

    def ready(self):
        super().ready()
        # Register adapters sepcified in settings.
        # Import here because importing outside of this method raises the AppRegistryNotReady exception.
        from anvil_consortium_manager.adapters.workspace import (
            workspace_adapter_registry,
        )

        workspace_adapter_registry.populate_from_settings()
