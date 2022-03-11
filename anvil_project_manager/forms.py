"""Forms classes for the anvil_project_manager app."""

from django import forms


class WorkspaceImportForm(forms.Form):
    """Form to import a workspace from AnVIL."""

    title = "Import a workspace"
    billing_project_name = forms.SlugField()
    workspace_name = forms.SlugField()
    # Consider adding validation to check if the workspace already exists in Django.
