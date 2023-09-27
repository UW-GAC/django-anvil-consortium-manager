"""Forms classes for the example_site app."""

from django import forms

from anvil_consortium_manager.forms import WorkspaceCreateForm

from . import models


class TestWorkspaceDataForm(forms.ModelForm):
    """Form for a TestWorkspaceData object."""

    class Meta:
        model = models.TestWorkspaceData
        fields = (
            "study_name",
            "workspace",
        )


class TestWorkspaceForm(WorkspaceCreateForm):
    pass
