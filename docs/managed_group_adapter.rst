.. _managed_group_adapter:

The Managed Group adapter
=========================

The app provides an adapter that you can use to customize behavior for Managed Groups.
You can override this setting by specifying the ``ANVIL_MANAGED_GROUP_ADAPTER`` setting in your ``settings.py`` file.
By default, the app uses :class:`~anvil_consortium_manager.adapters.default.DefaultManagedGroupAdapter`, e.g.,:

.. code-block:: python

        ANVIL_MANAGED_GROUP_ADAPTER = "anvil_consortium_manager.adapters.default.DefaultManagedGroupAdapter"


To customize app behavior for accounts, you must subclass :class:`~anvil_consortium_manager.adapters.account.BaseManagedGroupAdapter`
and set the following attributes:

- ``list_table_class``: an attribute set to the class of the table used to display managed groups in the :class:`~anvil_consortium_manager.views.ManagedGroupList` view to users with StaffView permission. The default adapter uses :class:`anvil_consortium_manager.tables.ManagedGroupStaffTable`.

Optionally, you can override the following methods:

- ``after_anvil_create(self, managed_group)``: a method to perform any actions after creating the Managed Group on AnVIL via the :class:`~anvil_consortium_manager.views.ManagedGroupCreate` view.
