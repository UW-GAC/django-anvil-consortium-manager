import django_tables2 as tables

from . import models


class IgnoredManagedGroupMembershipTable(tables.Table):
    """Class to display a IgnoredManagedGroupMembership table."""

    pk = tables.Column(linkify=True, verbose_name="Details", orderable=False)
    group = tables.Column(linkify=True)

    class Meta:
        model = models.IgnoredManagedGroupMembership
        fields = (
            "pk",
            "group",
            "ignored_email",
            "added_by",
            "created",
        )

    def render_pk(self):
        return "See details"
