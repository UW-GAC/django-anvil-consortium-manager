import django_tables2 as tables
from django.utils.safestring import mark_safe

from . import models
from .adapters.workspace import workspace_adapter_registry


class BooleanIconColumn(tables.BooleanColumn):
    """A column that displays a boolean value using boostrap icons."""

    def __init__(
        self,
        show_false_icon=False,
        true_color="green",
        false_color="red",
        true_icon="check-circle-fill",
        false_icon="x-circle-fill",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.show_false_icon = show_false_icon
        self.true_color = true_color
        self.false_color = false_color
        self.true_icon = true_icon
        self.false_icon = false_icon

    def render(self, value, record, bound_column):
        value = self._get_bool_value(record, value, bound_column)
        if value:
            rendered_value = mark_safe(
                f"""<i class="bi bi-{self.true_icon} bi-align-center px-2" style="color: {self.true_color};"></i>"""
            )
        else:
            if self.show_false_icon:
                rendered_value = mark_safe(
                    f"""<i class="bi bi-{self.false_icon} bi-align-center px-2" style="color: {self.false_color};"></i>"""  # noqa: E501
                )
            else:
                rendered_value = ""
        return rendered_value


class BillingProjectStaffTable(tables.Table):
    """Class to display a BillingProject table."""

    name = tables.Column(linkify=True)
    number_workspaces = tables.Column(
        verbose_name="Number of workspaces",
        empty_values=(),
        orderable=False,
        accessor="workspace_set__count",
    )
    has_app_as_user = BooleanIconColumn(show_false_icon=True)

    class Meta:
        model = models.BillingProject
        fields = ("name", "has_app_as_user")


class AccountStaffTable(tables.Table):
    """Class to display a BillingProject table."""

    email = tables.Column(linkify=True)
    is_service_account = BooleanIconColumn()

    class Meta:
        model = models.Account
        fields = ("email", "user", "is_service_account", "status")

    def render_user(self, record):
        """If user.get_absolute_url is defined, then include link to it. Otherwise, just show the user."""
        try:
            record.user.get_absolute_url()
            link = """<a href="{url}">{link_text}</a>""".format(
                link_text=str(record), url=record.user.get_absolute_url()
            )
            return mark_safe(link)
        except AttributeError:
            return str(record.user)


class ManagedGroupStaffTable(tables.Table):
    """Class to display a Group table."""

    name = tables.Column(linkify=True)
    number_groups = tables.Column(
        verbose_name="Number of groups",
        # empty_values=(0,),
        orderable=False,
        accessor="child_memberships__count",
    )
    number_accounts = tables.Column(
        verbose_name="Number of accounts",
        orderable=False,
        accessor="groupaccountmembership_set__count",
    )
    is_managed_by_app = BooleanIconColumn(show_false_icon=True)

    class Meta:
        model = models.ManagedGroup
        fields = ("name", "is_managed_by_app")

    def render_number_groups(self, value, record):
        """Render the number of groups as --- for groups not managed by the app."""
        if not record.is_managed_by_app:
            return self.default
        else:
            return value

    def render_number_accounts(self, value, record):
        """Render the number of accounts as --- for groups not managed by the app."""
        if not record.is_managed_by_app:
            return self.default
        else:
            return value


class ManagedGroupUserTable(tables.Table):
    """Class to display a Group table for users with view permission."""

    name = tables.Column()

    class Meta:
        model = models.ManagedGroup
        fields = ("name",)


class WorkspaceStaffTable(tables.Table):
    """Class to display a Workspace table."""

    name = tables.Column(linkify=True, verbose_name="Workspace")
    billing_project = tables.Column(linkify=True)
    workspace_type = tables.Column()
    number_groups = tables.Column(
        verbose_name="Number of groups shared with",
        empty_values=(),
        orderable=False,
        accessor="workspacegroupsharing_set__count",
    )
    created = tables.Column(verbose_name="Date added")

    class Meta:
        model = models.Workspace
        fields = ("name", "billing_project", "workspace_type")
        order_by = ("name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registered_names = workspace_adapter_registry.get_registered_names()

    def render_workspace_type(self, record):
        """Show the name of the workspace specified in the adapter for this workspace type."""
        return self.registered_names[record.workspace_type]


class WorkspaceUserTable(tables.Table):
    """Class to display a Workspace table for users with view permission."""

    name = tables.Column(linkify=True, verbose_name="Workspace")
    billing_project = tables.Column()
    workspace_type = tables.Column()

    class Meta:
        model = models.Workspace
        fields = ("name", "billing_project", "workspace_type")
        order_by = ("name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registered_names = workspace_adapter_registry.get_registered_names()

    def render_workspace_type(self, record):
        """Show the name of the workspace specified in the adapter for this workspace type."""
        return self.registered_names[record.workspace_type]


class GroupGroupMembershipStaffTable(tables.Table):
    """Class to render a GroupGroupMembership table."""

    pk = tables.Column(linkify=True, verbose_name="Details", orderable=False)
    parent_group = tables.Column(linkify=True)
    child_group = tables.Column(linkify=True)
    role = tables.Column()
    last_update = tables.DateTimeColumn(verbose_name="Last update", accessor="modified")

    class Meta:
        models = models.GroupAccountMembership
        fields = ("pk", "parent_group", "child_group", "role")

    def render_pk(self, record):
        return "See details"


class WorkspaceAccessUnknownStaffTable(WorkspaceStaffTable):
    """Class to render a WorkspaceStaffTable but include information about why access is unknown.

    Requires the Workspace objects to be modified to have sharing_unknown and auth_domain_unknown boolean fields."""

    owned_by_app = BooleanIconColumn(
        verbose_name="Owned by app?",
        show_false_icon=True,
        false_icon="x-circle-fill",
    )
    sharing_known = BooleanIconColumn(
        verbose_name="Is shared?",
        show_false_icon=True,
        false_icon="question-circle-fill",
        null=True,
    )
    auth_domain_known = BooleanIconColumn(
        verbose_name="In auth domain?",
        show_false_icon=True,
        false_icon="question-circle-fill",
        null=True,
    )

    class Meta(WorkspaceStaffTable.Meta):
        exclude = (
            "created",
            "number_groups",
        )


class GroupAccountMembershipStaffTable(tables.Table):
    """Class to render a GroupAccountMembership table."""

    pk = tables.Column(linkify=True, verbose_name="Details", orderable=False)
    account = tables.Column(linkify=True)
    is_service_account = BooleanIconColumn(accessor="account__is_service_account")
    status = tables.Column(accessor="account__status")
    group = tables.Column(linkify=True)
    role = tables.Column()
    last_update = tables.DateTimeColumn(verbose_name="Last update", accessor="modified")

    class Meta:
        models = models.GroupAccountMembership
        fields = ("pk", "group", "account", "status", "is_service_account", "role")

    def render_pk(self, record):
        return "See details"


class WorkspaceGroupSharingStaffTable(tables.Table):
    """Class to render a WorkspaceGroupSharing table."""

    pk = tables.Column(linkify=True, verbose_name="Details", orderable=False)
    workspace = tables.Column(linkify=True)
    group = tables.Column(linkify=True)
    access = tables.Column()
    can_compute = BooleanIconColumn(verbose_name="Compute allowed?")
    last_update = tables.DateTimeColumn(verbose_name="Last update", accessor="modified")

    class Meta:
        model = models.WorkspaceGroupSharing
        fields = ("pk", "workspace", "group", "access", "can_compute")

    def render_pk(self, record):
        return "See details"
