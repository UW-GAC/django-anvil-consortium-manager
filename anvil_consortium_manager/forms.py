"""Forms classes for the anvil_consortium_manager app."""

from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError

from . import models


class BillingProjectImportForm(forms.ModelForm):
    """Form to import a BillingProject from AnVIL"""

    class Meta:
        model = models.BillingProject
        fields = (
            "name",
            "note",
        )

    def clean_name(self):
        value = self.cleaned_data["name"]
        if models.BillingProject.objects.filter(name__iexact=value).exists():
            raise ValidationError("BillingProject with this Name already exists.")
        return value


class BillingProjectUpdateForm(forms.ModelForm):
    """Form to update a billing project."""

    class Meta:
        model = models.BillingProject
        fields = ("note",)


class AccountImportForm(forms.ModelForm):
    """Form to import an Account from AnVIL."""

    class Meta:
        model = models.Account
        fields = (
            "email",
            "is_service_account",
            "note",
        )

    def clean_email(self):
        value = self.cleaned_data["email"]
        if models.Account.objects.filter(email__iexact=value).exists():
            raise ValidationError("Account with this Email already exists.")
        return value


class AccountUpdateForm(forms.ModelForm):
    """Form to update an Account."""

    class Meta:
        model = models.Account
        fields = ("note",)


class UserEmailEntryForm(forms.Form):
    """Form for user to enter their email attempting to link their AnVIL account."""

    email = forms.EmailField(
        label="Email", help_text="Enter the email associated with your AnVIL account."
    )


class ManagedGroupCreateForm(forms.ModelForm):
    """Form to create a ManagedGroup on AnVIL."""

    class Meta:
        model = models.ManagedGroup
        fields = (
            "name",
            "note",
        )
        help_texts = {"name": "Name of the group to create on AnVIL."}

    def clean_name(self):
        value = self.cleaned_data["name"]
        if models.ManagedGroup.objects.filter(name__iexact=value).exists():
            raise ValidationError("Managed Group with this Name already exists.")
        return value


class ManagedGroupUpdateForm(forms.ModelForm):
    """Form to update information about a ManagedGroup."""

    class Meta:
        model = models.ManagedGroup
        fields = ("note",)


class WorkspaceCreateForm(forms.ModelForm):
    """Form to create a new workspace on AnVIL."""

    # Only allow billing groups where we can create a workspace.
    billing_project = forms.ModelChoiceField(
        queryset=models.BillingProject.objects.filter(has_app_as_user=True),
        widget=autocomplete.ModelSelect2(
            url="anvil_consortium_manager:billing_projects:autocomplete",
            attrs={"data-theme": "bootstrap-5"},
        ),
        help_text="""Select the billing project in which the workspace should be created.
                  Only billing projects where this app is a user are shown.""",
    )

    class Meta:
        model = models.Workspace
        fields = (
            "billing_project",
            "name",
            "authorization_domains",
            "note",
        )
        widgets = {
            "billing_project": autocomplete.ModelSelect2(
                url="anvil_consortium_manager:billing_projects:autocomplete",
                attrs={"data-theme": "bootstrap-5"},
            ),
            "authorization_domains": autocomplete.ModelSelect2Multiple(
                url="anvil_consortium_manager:managed_groups:autocomplete",
                attrs={"data-theme": "bootstrap-5"},
            ),
        }
        help_texts = {
            "billing_project": """Enter the billing project in which the workspace should be created.
                               Only billing projects that have this app as a user are shown.""",
            "name": "Enter the name of the workspace to create.",
            "authorization_domains": """Select one or more authorization domains for this workspace.
                        These cannot be changed after creation.""",
        }

    def clean(self):
        # Check for the same case insensitive name in the same billing project.
        billing_project = self.cleaned_data.get("billing_project", None)
        name = self.cleaned_data.get("name", None)
        if (
            billing_project
            and name
            and models.Workspace.objects.filter(
                billing_project=billing_project,
                name__iexact=name,
            ).exists()
        ):
            # The workspace already exists - raise a Validation error.
            raise ValidationError(
                "Workspace with this Billing Project and Name already exists."
            )
        return self.cleaned_data


class WorkspaceUpdateForm(forms.ModelForm):
    """Form to update information about a Workspace."""

    class Meta:
        model = models.Workspace
        fields = ("note",)


class WorkspaceImportForm(forms.Form):
    """Form to import a workspace from AnVIL -- new version."""

    title = "Import a workspace"
    workspace = forms.ChoiceField()
    note = forms.CharField(
        widget=forms.Textarea, help_text="Additional notes.", required=False
    )

    def __init__(self, workspace_choices=[], *args, **kwargs):
        """Initialize form with a set of possible workspace choices."""
        super().__init__(*args, **kwargs)
        self.fields["workspace"] = forms.ChoiceField(
            choices=[("", "---------")] + workspace_choices,
            help_text="""Select the workspace to import from AnVIL.
                    If necessary, a record for the workspace's billing project will also be created in this app.
                    Only workspaces where this app is an owner are shown.""",
        )


class WorkspaceCloneForm(forms.ModelForm):
    """Form to create a new workspace on AnVIL by cloning an existing workspace."""

    # Only allow billing groups where we can create a workspace.
    billing_project = forms.ModelChoiceField(
        queryset=models.BillingProject.objects.filter(has_app_as_user=True),
        widget=autocomplete.ModelSelect2(
            url="anvil_consortium_manager:billing_projects:autocomplete",
            attrs={"data-theme": "bootstrap-5"},
        ),
        help_text="""Select the billing project in which the workspace should be created.
                  Only billing projects where this app is a user are shown.""",
    )

    class Meta:
        model = models.Workspace
        fields = (
            "billing_project",
            "name",
            "authorization_domains",
            "note",
        )
        widgets = {
            "billing_project": autocomplete.ModelSelect2(
                url="anvil_consortium_manager:billing_projects:autocomplete",
                attrs={"data-theme": "bootstrap-5"},
            ),
            "authorization_domains": autocomplete.ModelSelect2Multiple(
                url="anvil_consortium_manager:managed_groups:autocomplete",
                attrs={"data-theme": "bootstrap-5"},
            ),
        }
        help_texts = {
            "authorization_domains": """Select the authorization domain(s) to use for this workspace.
                                     This cannot be changed after creation.""",
        }

    def __init__(self, workspace_to_clone, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Save this so we can modify the authorization domains to include this workspace's auth domain(s).
        self.workspace_to_clone = workspace_to_clone
        # Add the list of required auth domains to the help text.
        if self.workspace_to_clone.authorization_domains.exists():
            auth_domain_names = (
                self.workspace_to_clone.authorization_domains.values_list(
                    "name", flat=True
                )
            )
            print(auth_domain_names)
            extra_text = " You must also include the authorization domain(s) from the original workspace ({}).".format(
                ", ".join(auth_domain_names)
            )
            self.fields["authorization_domains"].help_text = (
                self.fields["authorization_domains"].help_text + extra_text
            )

    def clean_authorization_domains(self):
        """Verify that all authorization domains from the original workspace are selected."""
        authorization_domains = self.cleaned_data["authorization_domains"]
        required_authorization_domains = (
            self.workspace_to_clone.authorization_domains.all()
        )
        missing = [
            g for g in required_authorization_domains if g not in authorization_domains
        ]
        if missing:
            msg = "Must contain all original workspace authorization domains: {}".format(
                # ", ".join([g.name for g in self.workspace_to_clone.authorization_domains.all()])
                ", ".join(required_authorization_domains.values_list("name", flat=True))
            )
            raise ValidationError(msg)
        return authorization_domains

    def clean(self):
        # Check for the same case insensitive name in the same billing project.
        billing_project = self.cleaned_data.get("billing_project", None)
        name = self.cleaned_data.get("name", None)
        if (
            billing_project
            and name
            and models.Workspace.objects.filter(
                billing_project=billing_project,
                name__iexact=name,
            ).exists()
        ):
            # The workspace already exists - raise a Validation error.
            raise ValidationError(
                "Workspace with this Billing Project and Name already exists."
            )
        return self.cleaned_data


class DefaultWorkspaceDataForm(forms.ModelForm):
    """Default (empty) form for the workspace data object."""

    class Meta:
        model = models.DefaultWorkspaceData
        fields = ("workspace",)


class GroupGroupMembershipForm(forms.ModelForm):
    """Form for the GroupGroupMembership model."""

    parent_group = forms.ModelChoiceField(
        queryset=models.ManagedGroup.objects.filter(is_managed_by_app=True),
        widget=autocomplete.ModelSelect2(
            url="anvil_consortium_manager:managed_groups:autocomplete",
            attrs={"data-theme": "bootstrap-5"},
        ),
        help_text="Select the group to add the child group to. Only groups that are managed by this app are shown.",
    )

    class Meta:
        model = models.GroupGroupMembership
        fields = ("parent_group", "child_group", "role")
        widgets = {
            "child_group": autocomplete.ModelSelect2(
                url="anvil_consortium_manager:managed_groups:autocomplete",
                attrs={"data-theme": "bootstrap-5"},
            ),
        }
        help_texts = {
            "child_group": "This group will be a member of the parent group.",
            "role": """Select the role that the child group should have in the parent group.
                       Admin can see group membership, add or remove members, and delete the group.""",
        }


class GroupAccountMembershipForm(forms.ModelForm):
    """Form for the GroupAccountMembership model."""

    account = forms.ModelChoiceField(
        queryset=models.Account.objects.active(),
        help_text="Only active accounts can be added to a group.",
        widget=autocomplete.ModelSelect2(
            url="anvil_consortium_manager:accounts:autocomplete",
            attrs={"data-theme": "bootstrap-5"},
        ),
    )
    group = forms.ModelChoiceField(
        queryset=models.ManagedGroup.objects.filter(is_managed_by_app=True),
        help_text="Only groups managed by this app can be selected.",
        widget=autocomplete.ModelSelect2(
            url="anvil_consortium_manager:managed_groups:autocomplete",
            attrs={
                "data-theme": "bootstrap-5",
            },
        ),
    )

    class Meta:
        model = models.GroupAccountMembership
        fields = ("group", "account", "role")
        help_texts = {
            "group": "Select the group to add this accoun to. Only groups that are managed by the app are shown.",
            "account": "Select the account to add to this group.",
            "role": """Select the role that the account should have in the group.
                       Admin can see group membership, add or remove members, and delete the group.""",
        }


class WorkspaceGroupSharingForm(forms.ModelForm):
    """Form for the WorkspaceGroupSharing model."""

    class Meta:
        model = models.WorkspaceGroupSharing
        fields = ("workspace", "group", "access", "can_compute")

        widgets = {
            "workspace": autocomplete.ModelSelect2(
                url="anvil_consortium_manager:workspaces:autocomplete",
                attrs={"data-theme": "bootstrap-5"},
            ),
            "group": autocomplete.ModelSelect2(
                url="anvil_consortium_manager:managed_groups:autocomplete",
                attrs={"data-theme": "bootstrap-5"},
            ),
        }
