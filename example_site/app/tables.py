import django_tables2 as tables

from anvil_consortium_manager import models as acm_models


class CustomWorkspaceDataTable(tables.Table):
    name = tables.columns.Column(linkify=True)

    class Meta:
        model = acm_models.Workspace
        fields = (
            "customworkspacedata__study_name",
            "customworkspacedata__consent_code",
            "billing_project",
            "name",
        )
