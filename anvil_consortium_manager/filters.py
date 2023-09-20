from django_filters import FilterSet

from . import models


class BillingProjectListFilter(FilterSet):
    class Meta:
        model = models.BillingProject
        fields = {"name": ["icontains"]}


class ManagedGroupListFilter(FilterSet):
    class Meta:
        model = models.ManagedGroup
        fields = {"name": ["icontains"]}


class WorkspaceListFilter(FilterSet):
    class Meta:
        model = models.Workspace
        fields = {"name": ["icontains"]}
