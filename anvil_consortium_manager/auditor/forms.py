"""Forms classes for the anvil_consortium_manager app."""

from dal import autocomplete, forward
from django import forms

from anvil_consortium_manager.forms import Bootstrap5MediaFormMixin
from anvil_consortium_manager.models import ManagedGroup

from . import models


class IgnoredManagedGroupMembershipForm(Bootstrap5MediaFormMixin, forms.ModelForm):
    """Form for the IgnoredManagedGroupMembership model."""

    group = forms.ModelChoiceField(
        queryset=ManagedGroup.objects.filter(is_managed_by_app=True),
        help_text="Only groups managed by this app can be selected.",
        widget=autocomplete.ModelSelect2(
            url="anvil_consortium_manager:managed_groups:autocomplete",
            attrs={
                "data-theme": "bootstrap-5",
            },
            forward=(forward.Const(True, "only_managed_by_app"),),
        ),
    )

    class Meta:
        model = models.IgnoredManagedGroupMembership
        fields = (
            "group",
            "ignored_email",
            "note",
        )


class IgnoredWorkspaceSharingForm(Bootstrap5MediaFormMixin, forms.ModelForm):
    """Form for the IgnoredWorkspaceSharing model."""

    class Meta:
        model = models.IgnoredWorkspaceSharing
        fields = (
            "workspace",
            "ignored_email",
            "note",
        )
        widgets = {
            "workspace": autocomplete.ModelSelect2(
                url="anvil_consortium_manager:workspaces:autocomplete",
                attrs={"data-theme": "bootstrap-5"},
            ),
        }
