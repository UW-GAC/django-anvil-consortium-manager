import django_tables2 as tables

from . import models


class BillingProjectTable(tables.Table):
    """Class to display a BillingProject table."""

    name = tables.Column(linkify=True)
    number_workspaces = tables.Column(
        verbose_name="Number of workspaces",
        empty_values=(),
        orderable=False,
        accessor="workspace_set__count",
    )

    class Meta:
        model = models.BillingProject
        fields = ("name", "has_app_as_user")


class AccountTable(tables.Table):
    """Class to display a BillingProject table."""

    email = tables.Column(linkify=True)

    class Meta:
        model = models.Account
        fields = ("email", "is_service_account")


class ManagedGroupTable(tables.Table):
    """Class to display a Group table."""

    name = tables.Column(linkify=True)
    number_groups = tables.Column(
        verbose_name="Number of groups",
        empty_values=(),
        orderable=False,
        accessor="child_memberships__count",
    )
    number_accounts = tables.Column(
        verbose_name="Number of accounts",
        empty_values=(),
        orderable=False,
        accessor="groupaccountmembership_set__count",
    )

    class Meta:
        model = models.ManagedGroup
        fields = ("name", "is_managed_by_app")


class WorkspaceTable(tables.Table):
    """Class to display a Workspace table."""

    name = tables.Column(linkify=True, verbose_name="Workspace")
    billing_project = tables.Column(linkify=True)
    has_authorization_domains = tables.Column(
        accessor="authorization_domains__count", orderable=False
    )
    number_groups = tables.Column(
        verbose_name="Number of groups with access",
        empty_values=(),
        orderable=False,
        accessor="workspacegroupaccess_set__count",
    )

    class Meta:
        model = models.Workspace
        fields = ("name", "billing_project")

    def render_name(self, record):
        """Show the full name (including billing project) for the workspace."""
        return record.__str__()


class GroupGroupMembershipTable(tables.Table):
    """Class to render a GroupGroupMembership table."""

    pk = tables.Column(linkify=True, verbose_name="Details", orderable=False)
    parent_group = tables.Column(linkify=True)
    child_group = tables.Column(linkify=True)
    role = tables.Column()

    class Meta:
        models = models.GroupAccountMembership
        fields = ("pk", "parent_group", "child_group", "role")

    def render_pk(self, record):
        return "See details"


class GroupAccountMembershipTable(tables.Table):
    """Class to render a GroupAccountMembership table."""

    pk = tables.Column(linkify=True, verbose_name="Details", orderable=False)
    account = tables.Column(linkify=True)
    is_service_account = tables.BooleanColumn(accessor="account__is_service_account")
    group = tables.Column(linkify=True)
    role = tables.Column()

    class Meta:
        models = models.GroupAccountMembership
        fields = ("pk", "account", "is_service_account", "group", "role")

    def render_pk(self, record):
        return "See details"


class WorkspaceGroupAccessTable(tables.Table):
    """Class to render a WorkspaceGroupAccess table."""

    pk = tables.Column(linkify=True, verbose_name="Details", orderable=False)
    workspace = tables.Column(linkify=True)
    group = tables.Column(linkify=True)
    access = tables.Column()

    class Meta:
        model = models.WorkspaceGroupAccess
        fields = ("pk", "workspace", "group", "access")

    def render_pk(self, record):
        return "See details"
