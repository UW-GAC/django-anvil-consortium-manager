import django_tables2 as tables

from . import models


class BillingProjectTable(tables.Table):
    name = tables.LinkColumn(
        "anvil_project_manager:billing_projects:detail", args=[tables.utils.A("pk")]
    )

    class Meta:
        model = models.BillingProject
        fields = ("pk", "name")


class AccountTable(tables.Table):
    email = tables.LinkColumn(
        "anvil_project_manager:accounts:detail", args=[tables.utils.A("pk")]
    )

    class Meta:
        model = models.Account
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
    pk = tables.LinkColumn(
        "anvil_project_manager:group_membership:detail", args=[tables.utils.A("pk")]
    )
    account = tables.LinkColumn(
        "anvil_project_manager:accounts:detail",
        args=[tables.utils.A("account__pk")],
    )
    group = tables.LinkColumn(
        "anvil_project_manager:groups:detail", args=[tables.utils.A("group__pk")]
    )
    role = tables.Column()

    class Meta:
        models = models.GroupMembership
        fields = ("pk", "account", "group", "role")


class WorkspaceGroupAccessTable(tables.Table):
    pk = tables.LinkColumn(
        "anvil_project_manager:workspace_group_access:detail",
        args=[tables.utils.A("pk")],
    )
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
        fields = ("pk", "workspace", "group", "access")
