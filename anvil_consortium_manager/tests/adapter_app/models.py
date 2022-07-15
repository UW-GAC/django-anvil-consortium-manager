from django.db import models

from anvil_consortium_manager.models import Workspace


# Create your models here.
class TestWorkspaceData(models.Model):
    """A model to hold additional data about a Workspace."""

    study_name = models.CharField(max_length=16, unique=True)
    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE)

    def __str__(self):
        return self.study_name + " - " + self.workspace.get_full_name()
