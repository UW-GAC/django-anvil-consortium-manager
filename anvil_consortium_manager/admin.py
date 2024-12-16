"""Admin classes for the anvil_consortium_manager app."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from . import models


@admin.register(models.BillingProject)
class BillingProjectAdmin(SimpleHistoryAdmin):
    """Admin class for the BillingProject model."""

    list_display = ("name",)
    search_fields = ("name",)


@admin.register(models.UserEmailEntry)
class UserEmailEntryAdmin(SimpleHistoryAdmin):
    """Admin class for the UserEmailEntry model."""

    list_display = (
        "email",
        "user",
        "date_verification_email_sent",
        "date_verified",
    )
    list_filter = ()
    search_fields = (
        "email",
        "user",
    )


@admin.register(models.Account)
class AccountAdmin(SimpleHistoryAdmin):
    """Admin class for the Account model."""

    list_display = (
        "email",
        "user",
        "is_service_account",
        "status",
    )
    list_filter = (
        "is_service_account",
        "status",
    )
    search_fields = ("email",)


@admin.register(models.AccountUserArchive)
class AccountUserArchiveAdmin(SimpleHistoryAdmin):
    """Admin class for the AccountUserArchive model."""

    list_display = ("account", "user", "created")


@admin.register(models.ManagedGroup)
class ManagedGroupAdmin(SimpleHistoryAdmin):
    """Admin class for the ManagedGroup model."""

    list_display = ("name", "is_managed_by_app")
    list_filter = ("is_managed_by_app",)
    search_fields = ("name",)


@admin.register(models.Workspace)
class WorkspaceAdmin(SimpleHistoryAdmin):
    """Admin class for the Workspace model."""

    list_display = ("__str__", "billing_project", "is_locked")
    list_filter = (
        "workspace_type",
        "billing_project",
        "is_locked",
    )
    search_fields = ("name",)


@admin.register(models.WorkspaceAuthorizationDomain)
class WorkspaceAuthorizationDomainAccess(SimpleHistoryAdmin):
    """Admin class for the WorkspaceAuthorizationDomain model."""

    list_display = (
        "pk",
        "group",
        "workspace",
    )
    list_filter = (
        "group",
        "workspace",
    )
    search_fields = (
        "group",
        "workspace",
    )


@admin.register(models.GroupGroupMembership)
class GroupGroupMembershipAdmin(SimpleHistoryAdmin):
    """Admin class for the GroupGroupMembership model."""

    list_display = (
        "pk",
        "parent_group",
        "child_group",
        "role",
    )
    list_filter = ("role",)
    search_fields = (
        "parent_group",
        "child_group",
    )


@admin.register(models.GroupAccountMembership)
class GroupAccountMembershipAdmin(SimpleHistoryAdmin):
    """Admin class for the GroupAccountMembership model."""

    list_display = (
        "pk",
        "group",
        "account",
        "account_status",
        "role",
    )
    list_filter = (
        "role",
        "account__status",
    )
    search_fields = (
        "group",
        "account",
    )

    def account_status(self, obj):
        return obj.account.get_status_display()


@admin.register(models.WorkspaceGroupSharing)
class WorkspaceGroupSharingAdmin(SimpleHistoryAdmin):
    """Admin class for the WorkspaceGroupSharing model."""

    list_display = (
        "pk",
        "workspace",
        "group",
        "access",
    )
    list_filter = ("access",)
    search_fields = (
        "account",
        "group",
    )


@admin.register(models.IgnoredAuditManagedGroupMembership)
class IgnoredAuditManagedGroupMembershipAdmin(SimpleHistoryAdmin):
    """Admin class for the IgnoredAuditManagedGroupMembership model."""

    list_display = (
        "pk",
        "group",
        "ignored_email",
        "added_by",
    )
    search_fields = (
        "group",
        "ignored_email",
    )
