"""Contains base adapter for accounts."""

from abc import ABC, abstractproperty

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from django_filters import FilterSet

from .. import app_settings, models


class BaseAccountAdapter(ABC):
    """Base class to inherit when customizing the account adapter."""

    @abstractproperty
    def list_table_class(self):
        """Table class to use in a list of Accounts."""
        ...

    @abstractproperty
    def list_filterset_class(self):
        """FilterSet subclass to use for Account filtering in the AccountList view."""
        ...

    def get_list_table_class(self):
        """Return the table class to use for the AccountList view."""
        if not self.list_table_class:
            raise ImproperlyConfigured("Set `list_table_class` in `{}`.".format(type(self)))
        if self.list_table_class.Meta.model != models.Account:
            raise ImproperlyConfigured(
                "list_table_class Meta model field must be anvil_consortium_manager.models.Account."
            )
        return self.list_table_class

    def get_list_filterset_class(self):
        """Return the FilterSet subclass to use for Account filtering in the AccountList view."""
        if not self.list_filterset_class:
            raise ImproperlyConfigured("Set `list_filterset_class` in `{}`.".format(type(self)))
        if not issubclass(self.list_filterset_class, FilterSet):
            raise ImproperlyConfigured("list_filterset_class must be a subclass of FilterSet.")
        # Make sure it has the correct model set.
        if self.list_filterset_class.Meta.model != models.Account:
            raise ImproperlyConfigured(
                "list_filterset_class Meta model field must be anvil_consortium_manager.models.Account."
            )
        return self.list_filterset_class

    def get_autocomplete_queryset(self, queryset, q):
        """Filter the Account `queryset` using the query `q` for use in the autocomplete."""
        queryset = queryset.filter(email__icontains=q)
        return queryset

    def get_autocomplete_label(self, account):
        """Adapter to provide a label for an account in autocomplete views."""
        return str(account)


def get_account_adapter():
    adapter = import_string(app_settings.ACCOUNT_ADAPTER)
    return adapter
