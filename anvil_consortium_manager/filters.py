from django_filters import FilterSet

from . import models


class BillingProjectListFilter(FilterSet):
    class Meta:
        model = models.BillingProject
        fields = {"name": ["icontains"]}
