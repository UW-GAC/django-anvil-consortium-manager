from django.db import models

from anvil_consortium_manager.models import BaseWorkspaceData, DefaultWorkspaceData, ManagedGroup, Workspace


# Create your models here.
class TestWorkspaceData(BaseWorkspaceData):
    """Custom model to hold additional data about a Workspace."""

    study_name = models.CharField(max_length=255, unique=True)


class ProtectedManagedGroup(models.Model):  # noqa: DJ008
    """Model to test having a protected foreign key to ManagedGroup."""

    group = models.ForeignKey(ManagedGroup, on_delete=models.PROTECT)


class ProtectedWorkspace(models.Model):  # noqa: DJ008
    """Model to test having a protected foreign key to Workspace."""

    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)


class ProtectedWorkspaceData(models.Model):  # noqa: DJ008
    """Model to test having a protected foreign key to DefaultWorkspaceData."""

    workspace_data = models.ForeignKey(DefaultWorkspaceData, on_delete=models.PROTECT)


class TestForeignKeyWorkspaceData(BaseWorkspaceData):
    """Custom model with a second fk to Workspace."""

    other_workspace = models.ForeignKey(Workspace, related_name="test_foreign_key_workspaces", on_delete=models.PROTECT)
