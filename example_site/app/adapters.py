from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter
from anvil_consortium_manager.models import ManagedGroup

from . import forms, models, tables


class CustomWorkspaceAdapter(BaseWorkspaceAdapter):
    """Example adapter for workspaces."""

    name = "Custom workspace"
    type = "custom"
    description = "Example custom workspace type for demo app"
    list_table_class_staff_view = tables.CustomWorkspaceDataTable
    list_table_class_view = tables.CustomWorkspaceDataTable
    workspace_form_class = forms.CustomWorkspaceForm
    workspace_data_model = models.CustomWorkspaceData
    workspace_data_form_class = forms.CustomWorkspaceDataForm
    workspace_detail_template_name = "app/custom_workspace_detail.html"

    def before_anvil_create(self, workspace):
        """Add authorization domain to workspace."""
        auth_domain_name = "AUTH_" + workspace.name
        auth_domain = ManagedGroup.objects.create(
            name=auth_domain_name, is_managed_by_app=True, email=auth_domain_name + "@firecloud.org"
        )
        workspace.authorization_domains.add(auth_domain)
        auth_domain.anvil_create()
