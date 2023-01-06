"""Contains base adapter for accounts."""

from abc import ABC, abstractproperty

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


class BaseAccountAdapter(ABC):
    """Base class to inherit when customizing the account adapter."""

    @abstractproperty
    def list_table_class(self):
        """Table class to use in a list of Accounts."""
        ...

    def get_list_table_class(self):
        """Return the table class to use for the AccountList view."""
        if not self.list_table_class:
            raise ImproperlyConfigured(
                "Set `list_table_class` in `{}`.".format(type(self))
            )
        return self.list_table_class

    def get_autocomplete_queryset(self, queryset, q):
        """Filter the Account `queryset` using the query `q` for use in the autocomplete."""
        queryset = queryset.filter(email__icontains=q)
        return queryset

    def get_autocomplete_label(self, account):
        """Adapter to provide a label for an account in autocomplete views."""
        return str(account)


def get_account_adapter():
    adapter = import_string(settings.ANVIL_ACCOUNT_ADAPTER)
    return adapter
