Adapter mixins
--------------

The app provides several mixins that you can use to extend the behavior of your custom adapters.
These mixins are located in the ``anvil_consortium_manager.adapters.mixins`` module.
You can use these mixins by subclassing them along with the base adapter class when defining your custom adapter.
For example, to use the ``WorkspaceSharingAdapterMixin`` in a custom workspace adapter, you would do the following:

.. code-block:: python

    from anvil_consortium_manager.adapters.mixins import WorkspaceSharingAdapterMixin
    from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter

    class CustomWorkspaceAdapter(WorkspaceSharingAdapterMixin, BaseWorkspaceAdapter):
        ...

The available mixins are:

- :class:`~anvil_consortium_manager.adapters.mixins.WorkspaceSharingAdapterMixin`: This mixin adds functionality for sharing workspaces. It requires you to define the ``share_permissions`` attribute, which should be a list of permissions to grant when sharing a workspace.
- :class:`~anvil_consortium_manager.adapters.mixins.GroupGroupMembershipAdapterMixin`: This mixin adds functionality for adding group members. It requires you to define the ``membership_roles`` attribute, which should be a list of groups that should be added and the roles they should have.
