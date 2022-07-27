"""Forms classes for the example_site app."""

from django import forms

from . import models


class ExampleWorkspaceDataForm(forms.ModelForm):
    """Form for an ExampleWorkspaceData object."""

    class Meta:
        model = models.ExampleWorkspaceData
        fields = ("study_name", "consent_code", "workspace")
