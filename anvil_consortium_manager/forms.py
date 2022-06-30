"""Forms classes for the anvil_consortium_manager app."""

from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError

from . import models


class BillingProjectImportForm(forms.ModelForm):
    """Form to import a BillingProject from AnVIL"""

    class Meta:
        model = models.BillingProject
        fields = ("name",)

    def clean_name(self):
        value = self.cleaned_data["name"]
        if models.BillingProject.objects.filter(name__iexact=value).exists():
            raise ValidationError("BillingProject with this Name already exists.")
        return value


class AccountImportForm(forms.ModelForm):
    """Form to import an Account from AnVIL."""

    class Meta:
        model = models.Account
        fields = ("email", "is_service_account")

    def clean_email(self):
        value = self.cleaned_data["email"]
        if models.Account.objects.filter(email__iexact=value).exists():
            raise ValidationError("Account with this Email already exists.")
        return value


class ManagedGroupCreateForm(forms.ModelForm):
    """Form to create a ManagedGroup on AnVIL."""

    class Meta:
        model = models.ManagedGroup
        fields = ("name",)

    def clean_name(self):
        value = self.cleaned_data["name"]
        if models.ManagedGroup.objects.filter(name__iexact=value).exists():
            raise ValidationError("Managed Group with this Name already exists.")
        return value


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
    """Form to import a workspace from AnVIL -- new version."""

    title = "Import a workspace"

    def __init__(self, workspace_choices=[], *args, **kwargs):
        """Initialize form with a set of possible workspace choices."""
        super().__init__(*args, **kwargs)
        self.fields["workspace"] = forms.ChoiceField(
            choices=[("", "---------")] + workspace_choices
        )


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

    account = forms.ModelChoiceField(
        queryset=models.Account.objects.active(),
        help_text="Only active accounts can be added.",
    )
    group = forms.ModelChoiceField(
        queryset=models.ManagedGroup.objects.filter(is_managed_by_app=True),
        help_text="Only groups managed by this app can be selected.",
        widget=autocomplete.ModelSelect2(
            url="anvil_consortium_manager:managed_groups:autocomplete"
        ),
    )

    class Meta:
        model = models.GroupAccountMembership
        fields = ("group", "account", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = models.Account.objects.active()
