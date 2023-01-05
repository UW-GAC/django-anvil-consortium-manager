import django_tables2 as tables

from anvil_consortium_manager import models as acm_models


class TestWorkspaceDataTable(tables.Table):

    name = tables.columns.Column(linkify=True)

    class Meta:
        model = acm_models.Workspace
        fields = ("testworkspacedata__study_name", "name")
