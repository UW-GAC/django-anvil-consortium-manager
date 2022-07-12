import django_tables2 as tables

from anvil_consortium_manager import models as acm_models


class WorkspaceDataTable(tables.Table):

    name = tables.columns.Column(linkify=True)

    class Meta:
        model = acm_models.Workspace
        fields = ("workspacedata__study_name", "workspacedata__consent_code", "name")
