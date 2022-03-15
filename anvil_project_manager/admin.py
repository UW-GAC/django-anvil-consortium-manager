"""Admin classes for the anvil_project_manager app."""

from django.contrib import admin

from . import models


@admin.register(models.BillingProject)
class BillingProjectAdmin(admin.ModelAdmin):
    """Admin class for the BillingProject model."""

    list_display = ("name",)
    search_fields = ("name",)


@admin.register(models.Account)
class AccountAdmin(admin.ModelAdmin):
    """Admin class for the Account model."""

    list_display = ("email", "is_service_account")
    list_filter = ("is_service_account",)
    search_fields = ("email",)


@admin.register(models.Group)
class GroupAdmin(admin.ModelAdmin):
    """Admin class for the Group model."""

    list_display = ("name", "is_managed_by_app")
    list_filter = ("is_managed_by_app",)
    search_fields = ("name",)


@admin.register(models.Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    """Admin class for the Workspace model."""

    list_display = (
        "__str__",
        "billing_project",
    )
    list_filter = ("billing_project",)
    search_fields = ("name",)


@admin.register(models.WorkspaceAuthorizationDomain)
class WorkspaceAuthorizationDomainAccess(admin.ModelAdmin):
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
class GroupGroupMembershipAdmin(admin.ModelAdmin):
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
class GroupAccountMembershipAdmin(admin.ModelAdmin):
    """Admin class for the GroupAccountMembership model."""

    list_display = (
        "pk",
        "group",
        "account",
        "role",
    )
    list_filter = ("role",)
    search_fields = (
        "group",
        "account",
    )


@admin.register(models.WorkspaceGroupAccess)
class WorkspaceGroupAccessAdmin(admin.ModelAdmin):
    """Admin class for the WorkspaceGroupAccess model."""

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
