"""Admin classes for the anvil_consortium_manager.auditor app."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from . import models


@admin.register(models.IgnoredManagedGroupMembership)
class IgnoredManagedGroupMembershipAdmin(SimpleHistoryAdmin):
    """Admin class for the IgnoredManagedGroupMembership model."""

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
