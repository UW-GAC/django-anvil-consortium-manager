import django_tables2 as tables

from anvil_consortium_manager import models as acm_models


class TestWorkspaceDataTable(tables.Table):
    """Table for testing the Workspace adapter."""

    name = tables.columns.Column(linkify=True)

    class Meta:
        model = acm_models.Workspace
        fields = ("testworkspacedata__study_name", "name")


class TestAccountTable(tables.Table):
    """Table for testing the Account adapter."""

    email = tables.columns.Column(linkify=True)

    class Meta:
        model = acm_models.Account
        fields = ("email",)
