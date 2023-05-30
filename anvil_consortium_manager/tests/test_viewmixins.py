from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase

from .. import viewmixins
from ..adapters.default import DefaultWorkspaceAdapter
from ..adapters.workspace import workspace_adapter_registry
from .test_app.adapters import TestWorkspaceAdapter


class AnVILAuditMixinTest(TestCase):
    """ManagedGroupGraphMixin tests that aren't covered elsewhere."""

    def test_run_audit_not_implemented(self):
        with self.assertRaises(ImproperlyConfigured):
            viewmixins.AnVILAuditMixin().run_audit()


class ManagedGroupGraphMixinTest(TestCase):
    """ManagedGroupGraphMixin tests that aren't covered elsewhere."""

    def test_get_graph_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            viewmixins.ManagedGroupGraphMixin().get_graph()


class RegisteredWorkspaceAdaptersMixinTest(TestCase):
    """Tests for the RegisteredWorkspaceAdaptersMixin class."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        super().tearDown()

    def get_view_class(self):
        return viewmixins.RegisteredWorkspaceAdaptersMixin

    def test_context_registered_workspace_adapters_with_one_type(self):
        """registered_workspace_adapters contains an instance of DefaultWorkspaceAdapter."""
        context = self.get_view_class()().get_context_data()
        self.assertIn("registered_workspace_adapters", context)
        workspace_types = context["registered_workspace_adapters"]
        self.assertEqual(len(workspace_types), 1)
        self.assertIsInstance(workspace_types[0], DefaultWorkspaceAdapter)

    def test_context_registered_workspace_adapters_with_two_types(self):
        """registered_workspace_adapters contains an instance of a test adapter when it is registered."""
        workspace_adapter_registry.register(TestWorkspaceAdapter)
        context = self.get_view_class()().get_context_data()
        self.assertIn("registered_workspace_adapters", context)
        workspace_types = context["registered_workspace_adapters"]
        self.assertEqual(len(workspace_types), 2)
        self.assertIsInstance(workspace_types[0], DefaultWorkspaceAdapter)
        self.assertIsInstance(workspace_types[1], TestWorkspaceAdapter)
