"""Contains base adapter for accounts."""

from abc import ABC, abstractproperty

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from .. import app_settings, models


class BaseManagedGroupAdapter(ABC):
    """Base class to inherit when customizing the account adapter."""

    @abstractproperty
    def list_table_class_staff_view(self):
        """Table class to use in a list of ManagedGroups."""
        ...

    @abstractproperty
    def list_table_class_view(self):
        """Table class to use in a list of ManagedGroups."""
        ...

    def get_list_table_class_staff_view(self):
        """Return the table class to use for the ManagedGroupList view for staff view users."""
        # Make sure that ManagedGroup is the model being passed.
        if not self.list_table_class_staff_view:
            raise ImproperlyConfigured("Set `list_table_class_staff_view` in `{}`.".format(type(self)))
        if self.list_table_class_staff_view.Meta.model != models.ManagedGroup:
            raise ImproperlyConfigured("The Meta model for `list_table_class_staff_view` must be ManagedGroup.")
        return self.list_table_class_staff_view

    def get_list_table_class_view(self):
        """Return the table class to use for the ManagedGroupList view for view users."""
        # Make sure that ManagedGroup is the model being passed.
        if not self.list_table_class_view:
            raise ImproperlyConfigured("Set `list_table_class_view` in `{}`.".format(type(self)))
        if self.list_table_class_view.Meta.model != models.ManagedGroup:
            raise ImproperlyConfigured("The Meta model for `list_table_class_view` must be ManagedGroup.")
        return self.list_table_class_view

    def after_anvil_create(self):
        """Custom actions to run after a ManagedGroup is created by the app."""
        pass


def get_managed_group_adapter():
    adapter = import_string(app_settings.MANAGED_GROUP_ADAPTER)
    return adapter
