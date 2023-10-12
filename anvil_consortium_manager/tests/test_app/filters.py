from django_filters import FilterSet

from anvil_consortium_manager.forms import FilterForm
from anvil_consortium_manager.models import Account


class TestAccountListFilter(FilterSet):
    """Test filter for Accounts."""

    class Meta:
        model = Account
        fields = {"email": ["icontains"], "is_service_account": ["exact"]}
        form = FilterForm
