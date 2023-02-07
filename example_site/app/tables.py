import django_tables2 as tables

from anvil_consortium_manager import models as acm_models


class ExampleWorkspaceDataTable(tables.Table):

    name = tables.columns.Column(linkify=True)

    class Meta:
        model = acm_models.Workspace
        fields = (
            "exampleworkspacedata__study_name",
            "exampleworkspacedata__consent_code",
            "billing_project",
            "name",
        )
