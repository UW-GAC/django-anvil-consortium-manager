import django_tables2 as tables

from . import models


class InvestigatorTable(tables.Table):
    email = tables.LinkColumn(
        "anvil_project_manager:investigators:detail", args=[tables.utils.A("pk")]
    )

    class Meta:
        model = models.Investigator
        fields = ("pk", "email")


class GroupTable(tables.Table):
    name = tables.LinkColumn(
        "anvil_project_manager:groups:detail", args=[tables.utils.A("pk")]
    )

    class Meta:
        model = models.Group
        fields = ("pk", "name")


class WorkspaceTable(tables.Table):
    pk = tables.LinkColumn(
        "anvil_project_manager:workspaces:detail", args=[tables.utils.A("pk")]
    )
    authorization_domain = tables.LinkColumn(
        "anvil_project_manager:groups:detail",
        args=[tables.utils.A("authorization_domain__pk")],
    )

    class Meta:
        model = models.Group
        fields = ("pk", "name", "namespace", "authorization_domain")


class GroupMembershipTable(tables.Table):
    investigator = tables.LinkColumn(
        "anvil_project_manager:investigators:detail",
        args=[tables.utils.A("investigator__pk")],
    )
    group = tables.LinkColumn(
        "anvil_project_manager:groups:detail", args=[tables.utils.A("group__pk")]
    )
    role = tables.Column()

    class Meta:
        models = models.GroupMembership
        fields = ("investigator", "group", "role")
