from django.db import models


class Investigator(models.Model):
    """A model to store information about AnVIL investigators."""

    email = models.EmailField()

    def __str__(self):
        return "{email}".format(email=self.email)


class Group(models.Model):
    """A model to store information about AnVIL groups."""

    name = models.CharField(max_length=64)

    def __str__(self):
        return "{name}".format(name=self.name)


class Workspace(models.Model):
    """A model to store inromation about AnVIL workspaces."""

    namespace = models.CharField(max_length=64)
    name = models.CharField(max_length=64)
    authorization_domain = models.ForeignKey("Group", on_delete=models.PROTECT)

    def __str__(self):
        return "{namespace}/{name}".format(namespace=self.namespace, name=self.name)


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

    def __str__(self):
        return "{investigator} with {role} in {group}".format(
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

    investigator = models.ForeignKey("Investigator", on_delete=models.CASCADE)
    workspace = models.ForeignKey("Workspace", on_delete=models.CASCADE)
    access_level = models.CharField(
        max_length=10, choices=ACCESS_LEVEL_CHOICES, default=READER
    )

    def __str__(self):
        return "{group} with {access} to {workspace}".format(
            group=self.group,
            access=self.role,
            workspace=self.workspace,
        )
