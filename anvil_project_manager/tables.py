import django_tables2 as tables

from . import models


class BillingProjectTable(tables.Table):
    name = tables.LinkColumn(
        "anvil_project_manager:billing_projects:detail", args=[tables.utils.A("pk")]
    )

    class Meta:
        model = models.BillingProject
        fields = ("pk", "name")


class ResearcherTable(tables.Table):
    email = tables.LinkColumn(
        "anvil_project_manager:researchers:detail", args=[tables.utils.A("pk")]
    )

    class Meta:
        model = models.Researcher
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

    class Meta:
        model = models.Workspace
        fields = ("pk", "billing_project", "name")


class GroupMembershipTable(tables.Table):
    researcher = tables.LinkColumn(
        "anvil_project_manager:researchers:detail",
        args=[tables.utils.A("researcher__pk")],
    )
    group = tables.LinkColumn(
        "anvil_project_manager:groups:detail", args=[tables.utils.A("group__pk")]
    )
    role = tables.Column()

    class Meta:
        models = models.GroupMembership
        fields = ("researcher", "group", "role")


class WorkspaceGroupAccessTable(tables.Table):
    workspace = tables.LinkColumn(
        "anvil_project_manager:workspaces:detail",
        args=[tables.utils.A("workspace__pk")],
    )
    group = tables.LinkColumn(
        "anvil_project_manager:groups:detail", args=[tables.utils.A("group__pk")]
    )
    access = tables.Column()

    class Meta:
        model = models.WorkspaceGroupAccess
        fields = ("workspace", "group", "access")
