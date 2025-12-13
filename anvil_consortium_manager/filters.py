from django import forms as django_form
from django_filters import ChoiceFilter, FilterSet

from . import forms, models


class AccountListFilter(FilterSet):
    class Meta:
        model = models.Account
        fields = {"email": ["icontains"]}
        form = forms.FilterForm


class BillingProjectListFilter(FilterSet):
    class Meta:
        model = models.BillingProject
        fields = {"name": ["icontains"]}
        form = forms.FilterForm


class ManagedGroupListFilter(FilterSet):
    USED_AS_AUTH_DOMAIN_CHOICES = (
        ("", "Either"),
        ("yes", "Yes"),
        ("no", "No"),
    )

    used_as_auth_domain = ChoiceFilter(
        choices=USED_AS_AUTH_DOMAIN_CHOICES,
        method="filter_used_as_auth_domain",
        label="Used as auth domain?",
        empty_label=None,
        widget=django_form.RadioSelect,
    )

    class Meta:
        model = models.ManagedGroup
        fields = {"name": ["icontains"]}
        form = forms.FilterForm

    def filter_used_as_auth_domain(self, queryset, name, value):
        if value == "yes":
            return queryset.filter(workspaceauthorizationdomain__isnull=False).distinct()

        if value == "no":
            return queryset.filter(workspaceauthorizationdomain__isnull=True)

        return queryset


class WorkspaceListFilter(FilterSet):
    class Meta:
        model = models.Workspace
        fields = {"name": ["icontains"]}
        form = forms.FilterForm
