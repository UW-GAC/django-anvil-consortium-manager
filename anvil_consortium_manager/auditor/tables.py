import django_tables2 as tables

from . import models


class IgnoredManagedGroupMembershipTable(tables.Table):
    """Class to display a IgnoredManagedGroupMembership table."""

    group = tables.Column(linkify=True)

    class Meta:
        model = models.IgnoredManagedGroupMembership
        fields = (
            "group",
            "ignored_email",
            "added_by",
            "created",
        )
