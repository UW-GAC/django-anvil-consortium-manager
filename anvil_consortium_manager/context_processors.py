"""Context processors for the anvil_consortium_manager app."""

from .adapters.workspace import workspace_adapter_registry


def workspace_adapter(request):
    """Return the registered workspace types in the context."""
    return {"registered_workspaces": workspace_adapter_registry.get_registered_names()}
