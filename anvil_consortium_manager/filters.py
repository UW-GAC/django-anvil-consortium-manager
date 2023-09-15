from django_filters import FilterSet

from . import models


class BillingProjectFilter(FilterSet):
    class Meta:
        model = models.BillingProject
        fields = {"name": ["icontains"]}
