"""Forms classes for the anvil_project_manager app."""

from django import forms

from . import models


class WorkspaceCreateForm(forms.ModelForm):
    """Form to create a workspace."""

    # Right now, allow any group to be used as an auth domain.
    # Eventually we may want to have a flag where only certain groups are allowed to be auth domains.
    # When that is implemented, we can change this such that only those groups are shown.
    authorization_domains = forms.ModelMultipleChoiceField(
        models.Group.objects.all(), required=False
    )

    class Meta:
        model = models.Workspace
        fields = ["billing_project", "name"]


class WorkspaceImportForm(forms.Form):
    """Form to import a workspace from AnVIL."""

    title = "Import a workspace"
    billing_project_name = forms.SlugField()
    workspace_name = forms.SlugField()
    # Consider adding validation to check if the workspace already exists in Django.
