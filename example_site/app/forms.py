"""Forms classes for the example_site app."""

from django import forms
from django.core.exceptions import ValidationError

from anvil_consortium_manager.forms import WorkspaceCreateForm

from . import models


class CustomWorkspaceForm(WorkspaceCreateForm):
    """Example custom form for creating a Workspace."""

    class Meta(WorkspaceCreateForm.Meta):
        help_texts = {
            "name": "Enter the name of the workspace to create. (Hint: Example workspace names cannot include a 'y'.)",
        }

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if name and "y" in name:
            raise ValidationError("Name cannot include a y.")
        return name


class CustomWorkspaceDataForm(forms.ModelForm):
    """Form for an CustomWorkspaceData object."""

    class Meta:
        model = models.CustomWorkspaceData
        fields = ("study_name", "consent_code", "workspace")
        help_texts = {
            "study_name": "Enter the name of the study associated with this workspace.",
            "consent_code": "Enter the consent code associated with the data in this workspace (e.g., GRU)",
        }
