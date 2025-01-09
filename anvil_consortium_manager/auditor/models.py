from django.conf import settings
from django.db import models
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel
from simple_history.models import HistoricalRecords


class IgnoredAuditResult(TimeStampedModel):
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, help_text="User who added the record to this table."
    )
    note = models.TextField(help_text="Note about why this email is being ignored.")

    class Meta:
        abstract = True


class IgnoredManagedGroupMembership(IgnoredAuditResult):
    """A model to store audit records that can be ignored during a ManagedGroupMembership audit.

    Right now this model is intended to track "not in app" records that can be ignored."""

    group = models.ForeignKey(
        "anvil_consortium_manager.ManagedGroup",
        on_delete=models.CASCADE,
        help_text="Group where email should be ignored.",
    )
    ignored_email = models.EmailField(help_text="Email address to ignore.")
    history = HistoricalRecords()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["group", "ignored_email"], name="unique_group_ignored_email")]

    def __str__(self):
        return "{group} membership: ignoring {email}".format(group=self.group, email=self.ignored_email)

    def save(self, *args, **kwargs):
        """Save method to set the email address to lowercase before saving."""
        self.ignored_email = self.ignored_email.lower()
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        """Get the absolute url for this object.

        Returns:
            str: The absolute url for the object."""
        return reverse(
            "anvil_consortium_manager:auditor:managed_groups:membership:by_group:ignored:detail",
            kwargs={
                "slug": self.group.name,
                "email": self.ignored_email,
            },
        )


class IgnoredWorkspaceGroupSharing(IgnoredAuditResult):
    """A model to store audit records that can be ignored during a WorkspaceGroupSharing audit.

    Right now this model is intended to track "not in app" records that can be ignored."""

    workspace = models.ForeignKey(
        "anvil_consortium_manager.Workspace",
        on_delete=models.CASCADE,
        help_text="Workspace where email should be ignored.",
    )
    ignored_email = models.EmailField(help_text="Email address to ignore.")
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "ignored_email"], name="unique_workspace_ignored_email")
        ]

    def __str__(self):
        return "{workspace} sharing: ignoring {email}".format(workspace=self.workspace, email=self.ignored_email)

    def save(self, *args, **kwargs):
        """Save method to set the email address to lowercase before saving."""
        self.ignored_email = self.ignored_email.lower()
        return super().save(*args, **kwargs)

    # def get_absolute_url(self):
    #     """Get the absolute url for this object.

    #     Returns:
    #         str: The absolute url for the object."""
    #     return reverse(
    #         "anvil_consortium_manager:auditor:managed_groups:membership:by_group:ignored:detail",
    #         kwargs={
    #             "slug": self.group.name,
    #             "email": self.ignored_email,
    #         },
    #     )
