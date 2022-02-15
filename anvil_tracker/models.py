from django.db import models
from django.urls import reverse


class Investigator(models.Model):
    """A model to store information about AnVIL investigators."""

    # TODO: Consider using CIEmailField if using postgres.
    email = models.EmailField(unique=True)

    def __str__(self):
        return "{email}".format(email=self.email)

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("anvil_tracker:investigators:detail", kwargs={"pk": self.pk})


class Group(models.Model):
    """A model to store information about AnVIL groups."""

    name = models.SlugField(max_length=64, unique=True)
    name_lower = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return "{name}".format(name=self.name)

    def save(self, *args, **kwargs):
        self.name_lower = self.name.lower()
        return super().save(*args, **kwargs)


class Workspace(models.Model):
    """A model to store inromation about AnVIL workspaces."""

    namespace = models.SlugField(max_length=64)
    name = models.SlugField(max_length=64)
    authorization_domain = models.ForeignKey(
        "Group", on_delete=models.PROTECT, null=True
    )

    def __str__(self):
        return "{namespace}/{name}".format(namespace=self.namespace, name=self.name)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["namespace", "name"], name="unique_workspace"
            )
        ]


class GroupMembership(models.Model):
    """A model to store which investigators are in a group."""

    MEMBER = "MEMBER"
    ADMIN = "ADMIN"

    ROLE_CHOICES = [
        (MEMBER, "Member"),
        (ADMIN, "Admin"),
    ]

    investigator = models.ForeignKey("Investigator", on_delete=models.CASCADE)
    group = models.ForeignKey("Group", on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["investigator", "group"], name="unique_group_membership"
            )
        ]

    def __str__(self):
        return "{investigator} as {role} in {group}".format(
            investigator=self.investigator,
            group=self.group,
            role=self.role,
        )


class WorkspaceGroupAccess(models.Model):
    """A model to store which groups have access to a workspace."""

    OWNER = "OWNER"
    WRITER = "WRITER"
    READER = "READER"

    ACCESS_LEVEL_CHOICES = [
        (OWNER, "Owner"),
        (WRITER, "Writer"),
        (READER, "Reader"),
    ]

    group = models.ForeignKey("Group", on_delete=models.CASCADE)
    workspace = models.ForeignKey("Workspace", on_delete=models.CASCADE)
    access_level = models.CharField(
        max_length=10, choices=ACCESS_LEVEL_CHOICES, default=READER
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "workspace"], name="unique_workspace_group_access"
            )
        ]

    def __str__(self):
        return "{group} with {access} to {workspace}".format(
            group=self.group,
            access=self.access_level,
            workspace=self.workspace,
        )
