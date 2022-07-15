"""Forms classes for the example_site app."""

from django import forms

from . import models


class TestWorkspaceDataForm(forms.ModelForm):
    """Form for a TestWorkspaceData object."""

    class Meta:
        model = models.TestWorkspaceData
        fields = ("study_name",)
