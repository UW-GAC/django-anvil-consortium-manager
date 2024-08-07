"""Contains base adapter for accounts."""

from abc import ABC, abstractproperty

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from .. import app_settings, models


class BaseManagedGroupAdapter(ABC):
    """Base class to inherit when customizing the account adapter."""

    @abstractproperty
    def list_table_class(self):
        """Table class to use in a list of ManagedGroups."""
        ...

    def get_list_table_class(self):
        """Return the table class to use for the ManagedGroupList view for staff view users."""
        # Make sure that ManagedGroup is the model being passed.
        if not self.list_table_class:
            raise ImproperlyConfigured("Set `list_table_class` in `{}`.".format(type(self)))
        if self.list_table_class.Meta.model != models.ManagedGroup:
            raise ImproperlyConfigured(
                "list_table_class Meta model field must be anvil_consortium_manager.models.ManagedGroup."
            )
        return self.list_table_class

    def after_anvil_create(self, managed_group):
        """Custom actions to run after a ManagedGroup is created by the app."""
        pass


def get_managed_group_adapter():
    adapter = import_string(app_settings.MANAGED_GROUP_ADAPTER)
    return adapter
