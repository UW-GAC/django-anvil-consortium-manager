"""Tests for the context processors for this app."""

from django.http import HttpRequest
from django.test import TestCase

from .. import context_processors
from ..adapter import (
    BaseWorkspaceAdapter,
    DefaultWorkspaceAdapter,
    workspace_adapter_registry,
)


class WorkspaceAdapterTest(TestCase):
    """Tests for the workspace_adapter context processor."""

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)

    def test_no_adapters(self):
        """The context processor returns the correct value when no adapters are registered."""
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)
        context = context_processors.workspace_adapter(HttpRequest())
        self.assertIn("registered_workspaces", context)
        registered_workspaces = context["registered_workspaces"]
        self.assertEqual(len(registered_workspaces), 0)

    def test_one_adapter(self):
        """The context processor returns the correct value when one adapter is registered."""
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)

        class Adapter(BaseWorkspaceAdapter):
            type = "test"
            name = "Test Workspace"
            workspace_data_model = None
            workspace_data_form_class = None
            list_table_class = None

        workspace_adapter_registry.register(Adapter)
        context = context_processors.workspace_adapter(HttpRequest())
        self.assertIn("registered_workspaces", context)
        registered_workspaces = context["registered_workspaces"]
        self.assertEqual(len(registered_workspaces), 1)
        self.assertIn("test", registered_workspaces)
        self.assertEqual(registered_workspaces["test"], "Test Workspace")

    def test_two_adapters(self):
        """The context processor returns the correct value when two adapters are registered."""
        workspace_adapter_registry.unregister(DefaultWorkspaceAdapter)

        class Adapter1(BaseWorkspaceAdapter):
            type = "test1"
            name = "Test 1 Workspace"
            workspace_data_model = None
            workspace_data_form_class = None
            list_table_class = None

        class Adapter2(BaseWorkspaceAdapter):
            type = "test2"
            name = "Test 2 Workspace"
            workspace_data_model = None
            workspace_data_form_class = None
            list_table_class = None

        workspace_adapter_registry.register(Adapter1)
        workspace_adapter_registry.register(Adapter2)
        context = context_processors.workspace_adapter(HttpRequest())
        self.assertIn("registered_workspaces", context)
        registered_workspaces = context["registered_workspaces"]
        self.assertEqual(len(registered_workspaces), 2)
        self.assertIn("test1", registered_workspaces)
        self.assertEqual(registered_workspaces["test1"], "Test 1 Workspace")
        self.assertIn("test2", registered_workspaces)
        self.assertEqual(registered_workspaces["test2"], "Test 2 Workspace")
