from django_filters import FilterSet

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
    class Meta:
        model = models.ManagedGroup
        fields = {"name": ["icontains"]}
        form = forms.FilterForm


class WorkspaceListFilter(FilterSet):
    class Meta:
        model = models.Workspace
        fields = {"name": ["icontains"]}
        form = forms.FilterForm
