Adapter mixins
==============

The app provides several mixins that you can use to extend the behavior of your custom adapters.
These mixins are located in the ``anvil_consortium_manager.adapters.mixins`` module.
You can use these mixins by subclassing them along with the base adapter class when defining your custom adapter.
For example, to use the ``WorkspaceSharingAdapterMixin`` in a custom workspace adapter, you would do the following:

.. code-block:: python

    from anvil_consortium_manager.adapters.mixins import WorkspaceSharingAdapterMixin
    from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter

    class CustomWorkspaceAdapter(WorkspaceSharingAdapterMixin, BaseWorkspaceAdapter):
        ...

Share workspaces upon creation, import, or cloning
--------------------------------------------------

The :class:`~anvil_consortium_manager.adapters.mixins.WorkspaceSharingAdapterMixin` class adds functionality for sharing workspaces.
It requires you to define the ``share_permissions`` attribute, which should be a list of permissions to grant when sharing a workspace.

For example, to add automatic sharing to the default workspace adapter:

.. code-block:: python

    from anvil_consortium_manager.adapters.mixins import WorkspaceSharingAdapterMixin, WorkspaceSharingPermission
    from anvil_consortium_manager.adapters.default import DefaultWorkspaceAdapter

    class CustomWorkspaceAdapter(WorkspaceSharingAdapterMixin, DefaultWorkspaceAdapter):
        type="custom-workspace-with-sharing"
        share_permissions = [
            WorkspaceSharingPermission(
                # Name of the group to share with.
                group_name="example-group",
                # Role that this group should have.
                access="READER",
                # Whether the group should have compute permission or not.
                can_compute=False,
            ),
        ]

The `example-group` :class:`~anvil_consortium_manager.models.ManagedGroup` will automatically be granted `READER` access (without compute permission) to `custom-workspace-with-sharing` workspaces that are created, imported, or cloned.
If no groups with the name specified by ``group_name`` exist in the app, it will be ignored.
If the `WorkspaceSharingPermission` raises an exception upon validation or in API calls to AnVIL via the
:class:`~anvil_consortium_manager.views.WorkspaceCreate`,
:class:`~anvil_consortium_manager.views.WorkspaceImport`,
or :class:`~anvil_consortium_manager.views.WorkspaceClone` views,
the exception will be logged and the user will be notified.

Add membership upon creation of a Managed Group
-----------------------------------------------

The :class:`~anvil_consortium_manager.adapters.mixins.GroupGroupMembershipAdapterMixin` adds functionality for adding group members.
It requires you to define the ``membership_roles`` attribute, which should be a list of groups that should be added and the roles they should have.

For example, to create a custom Managed Group adapter using this mixin:

.. code-block:: python

    from anvil_consortium_manager.adapters.mixins import GroupGroupMembershipAdapterMixin, GroupGroupMembershipRole
    from anvil_consortium_manager.adapters.default import DefaultManagedGroupAdapter

    class CustomGroupAdapter(GroupGroupMembershipAdapterMixin, DefaultManagedGroupAdapter):
        membership_roles = [
            GroupGroupMembershipAdapterMixin(
                # Name of the group to add as a member.
                child_group_name="example-group",
                # Role that this group should have.
                role="MEMBER",
            ),
        ]

The `example-group` :class:`~anvil_consortium_manager.models.ManagedGroup` will automatically be added as a `MEMBER` to any Managed Groups that are created.
If no groups with the name specified by ``child_group_name`` exist in the app, it will be ignored.
If the `WorkspaceSharingPermission` raises an exception upon validation or in API calls to AnVIL via the
:class:`~anvil_consortium_manager.views.WorkspaceCreate`,
:class:`~anvil_consortium_manager.views.WorkspaceImport`,
or :class:`~anvil_consortium_manager.views.WorkspaceClone` views,
the exception will be logged and the user will be notified.
