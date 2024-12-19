from django_filters import FilterSet

from anvil_consortium_manager.forms import FilterForm

from . import models


class IgnoredManagedGroupMembershipFilter(FilterSet):
    class Meta:
        model = models.IgnoredManagedGroupMembership
        fields = {"group__name": ["icontains"], "ignored_email": ["icontains"]}
        form = FilterForm
