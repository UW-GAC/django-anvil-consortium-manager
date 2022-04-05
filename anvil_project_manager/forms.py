"""Forms classes for the anvil_project_manager app."""

from django import forms

from . import models


class WorkspaceCreateForm(forms.ModelForm):
    """Form to create a new workspace on AnVIL."""

    # Only allow billing groups where we can create a workspace.
    billing_project = forms.ModelChoiceField(
        queryset=models.BillingProject.objects.filter(has_app_as_user=True)
    )

    class Meta:
        model = models.Workspace
        fields = ("billing_project", "name", "authorization_domains")


class WorkspaceImportForm(forms.Form):
    """Form to import a workspace from AnVIL."""

    title = "Import a workspace"
    billing_project_name = forms.SlugField()
    workspace_name = forms.SlugField()
    # Consider adding validation to check if the workspace already exists in Django.


class GroupGroupMembershipForm(forms.ModelForm):
    """Form for the GroupGroupMembership model."""

    parent_group = forms.ModelChoiceField(
        queryset=models.ManagedGroup.objects.filter(is_managed_by_app=True)
    )

    class Meta:
        model = models.GroupGroupMembership
        fields = ("parent_group", "child_group", "role")

    #
    # def clean_parent_group(self):
    #     parent_group = self.cleaned_data["parent_group"]
    #     if not parent_group.is_managed_by_app:
    #         raise ValidationError(
    #             self.error_not_admin_of_parent_group, code="not_admin"
    #         )
    #     return parent_group


class GroupAccountMembershipForm(forms.ModelForm):
    """Form for the GroupAccountMembership model."""

    group = forms.ModelChoiceField(
        queryset=models.ManagedGroup.objects.filter(is_managed_by_app=True)
    )

    class Meta:
        model = models.GroupAccountMembership
        fields = ("group", "account", "role")
