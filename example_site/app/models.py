from django.db import models

from anvil_consortium_manager.models import BaseWorkspaceData


# Create your models here.
class CustomWorkspaceData(BaseWorkspaceData):
    """Example custom model to hold additional data about a Workspace."""

    study_name = models.CharField(max_length=255)
    consent_code = models.CharField(max_length=16)

    def __str__(self):
        return self.study_name + " - " + self.workspace.get_full_name()
