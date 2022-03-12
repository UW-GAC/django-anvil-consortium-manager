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
        fields = ("pk", "email", "is_service_account")


class GroupTable(tables.Table):
    name = tables.LinkColumn(
        "anvil_project_manager:groups:detail", args=[tables.utils.A("pk")]
    )

    class Meta:
        model = models.Group
        fields = ("pk", "name", "is_managed_by_app")


class WorkspaceTable(tables.Table):
    pk = tables.LinkColumn(
        "anvil_project_manager:workspaces:detail", args=[tables.utils.A("pk")]
    )

    class Meta:
        model = models.Workspace
        fields = ("pk", "billing_project", "name")


class GroupGroupMembershipTable(tables.Table):
    pk = tables.LinkColumn(
        "anvil_project_manager:group_group_membership:detail",
        args=[tables.utils.A("pk")],
    )
    parent_group = tables.RelatedLinkColumn(accessor="parent_group")
    child_group = tables.RelatedLinkColumn(accessor="child_group")
    role = tables.Column()

    class Meta:
        models = models.GroupAccountMembership
        fields = ("pk", "parent_group", "child_group", "role")


class GroupAccountMembershipTable(tables.Table):
    pk = tables.LinkColumn(
        "anvil_project_manager:group_account_membership:detail",
        args=[tables.utils.A("pk")],
    )
    account = tables.LinkColumn(
        "anvil_project_manager:accounts:detail",
        args=[tables.utils.A("account__pk")],
    )
    is_service_account = tables.BooleanColumn(accessor="account__is_service_account")
    group = tables.LinkColumn(
        "anvil_project_manager:groups:detail", args=[tables.utils.A("group__pk")]
    )
    role = tables.Column()

    class Meta:
        models = models.GroupAccountMembership
        fields = ("pk", "account", "is_service_account", "group", "role")


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
