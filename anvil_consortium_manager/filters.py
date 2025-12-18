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
    """Filter for ManagedGroup list view."""

    # Set up choices for the auth domain filter.
    IS_AUTH_DOMAIN = "yes"
    NOT_AUTH_DOMAIN = "no"
    USED_AS_AUTH_DOMAIN_CHOICES = (
        (IS_AUTH_DOMAIN, "Only auth domains"),
        (NOT_AUTH_DOMAIN, "No auth domains"),
    )

    used_as_auth_domain = ChoiceFilter(
        choices=USED_AS_AUTH_DOMAIN_CHOICES,
        method="filter_used_as_auth_domain",
        label="",
        empty_label="All groups",
        help_text="Filter on whether a group is used as an authorization domain.",
        widget=django_form.RadioSelect,
    )

    class Meta:
        model = models.ManagedGroup
        fields = {"name": ["icontains"]}
        form = forms.FilterForm

    def filter_used_as_auth_domain(self, queryset, name, value):
        if value == self.IS_AUTH_DOMAIN:
            queryset = queryset.filter(workspaceauthorizationdomain__isnull=False).distinct()
        elif value == self.NOT_AUTH_DOMAIN:
            queryset = queryset.filter(workspaceauthorizationdomain__isnull=True)
        return queryset


class WorkspaceListFilter(FilterSet):
    class Meta:
        model = models.Workspace
        fields = {"name": ["icontains"]}
        form = forms.FilterForm
