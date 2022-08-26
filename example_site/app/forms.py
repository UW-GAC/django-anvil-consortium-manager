"""Forms classes for the example_site app."""

from django import forms

from . import models


class ExampleWorkspaceDataForm(forms.ModelForm):
    """Form for an ExampleWorkspaceData object."""

    class Meta:
        model = models.ExampleWorkspaceData
        fields = ("study_name", "consent_code", "workspace")
        help_texts = {
            "study_name": "Enter the name of the study associated with this workspace.",
            "consent_code": "Enter the consent code associated with the data in this workspace (e.g., GRU)",
        }
