from django.db import models


class Investigator(models.Model):
    """A model to store information about AnVIL investigators."""


class Group(models.Model):
    """A model to store information about AnVIL groups."""


class Workspace(models.Model):
    """A model to store inromation about AnVIL workspaces."""


class GroupMembership(models.Model):
    """A model to store which investigators are in a group."""


class WorkspaceGroups(models.Model):
    """A model to store which groups have access to a workspace."""
