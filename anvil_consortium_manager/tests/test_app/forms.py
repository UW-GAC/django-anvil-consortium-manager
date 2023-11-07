"""Forms classes for the example_site app."""

from django import forms
from django.core.exceptions import ValidationError

from anvil_consortium_manager.forms import WorkspaceForm

from . import models


class TestWorkspaceDataForm(forms.ModelForm):
    """Form for a TestWorkspaceData object."""

    class Meta:
        model = models.TestWorkspaceData
        fields = (
            "study_name",
            "workspace",
        )


class TestWorkspaceForm(WorkspaceForm):
    """Custom form for Workspace."""

    def clean_name(self):
        """Test custom cleaning for workspace name."""
        name = self.cleaned_data.get("name")
        if name and name == "test-fail":
            raise ValidationError("Workspace name cannot be 'test-fail'!")
        return name


class TestForeignKeyWorkspaceDataForm(forms.ModelForm):
    """Form for a TestForeignKeyWorkspace object."""

    class Meta:
        model = models.TestForeignKeyWorkspaceData
        fields = ("other_workspace", "workspace")
