from django.db import models

from anvil_consortium_manager.models import BaseWorkspaceData, ManagedGroup


# Create your models here.
class TestWorkspaceData(BaseWorkspaceData):
    """Custom model to hold additional data about a Workspace."""

    study_name = models.CharField(max_length=16, unique=True)


class ProtectedManagedGroup(models.Model):
    """Model to test having a protected foreign key to ManagedGroup."""

    group = models.ForeignKey(ManagedGroup, on_delete=models.PROTECT)
