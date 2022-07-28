from django.db import models

from anvil_consortium_manager.models import BaseWorkspaceData


# Create your models here.
class TestWorkspaceData(BaseWorkspaceData):
    """Custom model to hold additional data about a Workspace."""

    study_name = models.CharField(max_length=16, unique=True)
