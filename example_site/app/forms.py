"""Forms classes for the example_site app."""

from django import forms

from . import models


class WorkspaceDataForm(forms.ModelForm):
    """Form for a WorkspaceData object."""

    class Meta:
        model = models.WorkspaceData
        fields = ("study_name", "consent_code")
