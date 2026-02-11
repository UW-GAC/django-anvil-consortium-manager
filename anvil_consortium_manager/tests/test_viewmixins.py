from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase

from .. import viewmixins
from ..adapters.default import DefaultWorkspaceAdapter
from ..adapters.workspace import workspace_adapter_registry
from ..models import Workspace
from . import factories
from .test_app.adapters import TestWorkspaceAdapter


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
        super().tearDown()
        # Unregister all adapters.
        workspace_adapter_registry._registry = {}
        # Register the default adapter.
        workspace_adapter_registry.register(DefaultWorkspaceAdapter)
        workspace_adapter_registry.register(TestWorkspaceAdapter)

    def get_view_class(self):
        return viewmixins.RegisteredWorkspaceAdaptersMixin

    def test_context_registered_workspace_adapters_with_one_type(self):
        """registered_workspace_adapters contains an instance of DefaultWorkspaceAdapter."""
        # The test app has two, so we need to unregister one of them.
        workspace_adapter_registry.unregister(TestWorkspaceAdapter)
        context = self.get_view_class()().get_context_data()
        self.assertIn("registered_workspace_adapters", context)
        workspace_types = context["registered_workspace_adapters"]
        self.assertEqual(len(workspace_types), 1)
        self.assertIsInstance(workspace_types[0], DefaultWorkspaceAdapter)

    def test_context_registered_workspace_adapters_with_two_types(self):
        """registered_workspace_adapters contains an instance of a test adapter when it is registered."""
        context = self.get_view_class()().get_context_data()
        self.assertIn("registered_workspace_adapters", context)
        workspace_types = context["registered_workspace_adapters"]
        self.assertEqual(len(workspace_types), 2)
        self.assertIsInstance(workspace_types[0], DefaultWorkspaceAdapter)
        self.assertIsInstance(workspace_types[1], TestWorkspaceAdapter)


class WorkspaceCheckAccessMixinText(TestCase):
    """Tests for the WorkspaceCheckAccessMixin class."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.view_class = viewmixins.WorkspaceCheckAccessMixin
        self.mixin = self.view_class()

    def test_get_workspace_access_from_workspace_access(self):
        # workspace_access = owner
        with patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_access", Workspace.AppAccessChoices.OWNER):
            self.assertEqual(self.mixin.get_workspace_access(), Workspace.AppAccessChoices.OWNER)
        # workspace_access = limited
        with patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_access", Workspace.AppAccessChoices.LIMITED):
            self.assertEqual(self.mixin.get_workspace_access(), Workspace.AppAccessChoices.LIMITED)
        # workspace_access = foo
        with patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_access", "foo"), self.assertRaises(
            ImproperlyConfigured
        ) as e:
            self.view_class().get_workspace_access()
        self.assertIn("Invalid workspace access level: foo", str(e.exception))
        # workspace_access = None
        with patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_unlocked", None), self.assertRaises(
            ImproperlyConfigured
        ) as e:
            self.mixin.get_workspace_unlocked()
        self.assertIn("must set `workspace_unlocked` or override `get_workspace_unlocked`", str(e.exception))

    def test_get_workspace_access_custom(self):
        with patch.object(viewmixins.WorkspaceCheckAccessMixin, "get_workspace_access", return_value="foo"):
            self.assertEqual(self.mixin.get_workspace_access(), "foo")

    def test_get_workspace_unlocked_from_workspace_unlocked(self):
        # workspace_unlocked = True
        with patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_unlocked", True):
            self.assertTrue(self.mixin.get_workspace_unlocked())
        # Truthy-y
        with patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_unlocked", "abc"), self.assertRaises(
            ImproperlyConfigured
        ) as e:
            self.assertTrue(self.mixin.get_workspace_unlocked())
        self.assertIn("Invalid workspace_unlocked value: abc", str(e.exception))
        # workspace_unlocked = False
        with patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_unlocked", False):
            self.assertFalse(self.mixin.get_workspace_unlocked())
        # False-y
        with patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_unlocked", []), self.assertRaises(
            ImproperlyConfigured
        ) as e:
            self.assertTrue(self.mixin.get_workspace_unlocked())
        self.assertIn("Invalid workspace_unlocked value: []", str(e.exception))
        # workspace_unlocked = None
        with patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_unlocked", None), self.assertRaises(
            ImproperlyConfigured
        ) as e:
            self.mixin.get_workspace_unlocked()
        self.assertIn("must set `workspace_unlocked` or override `get_workspace_unlocked`", str(e.exception))

    def test_get_workspace_unlocked_custom(self):
        with patch.object(viewmixins.WorkspaceCheckAccessMixin, "get_workspace_unlocked", return_value="foo"):
            self.assertEqual(self.mixin.get_workspace_unlocked(), "foo")

    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_access", Workspace.AppAccessChoices.LIMITED)
    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_unlocked", True)
    def test_check_workspace_workspace_access_limited_workspace_unlocked_true(self):
        # Owner and unlocked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.OWNER,
            is_locked=False,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertTrue(self.mixin.check_workspace(workspace))
        # Owner access and locked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.OWNER,
            is_locked=True,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertFalse(self.mixin._check_workspace_lock_ok(workspace))
        self.assertFalse(self.mixin.check_workspace(workspace))
        # Limited access and unlocked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.LIMITED,
            is_locked=False,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertTrue(self.mixin.check_workspace(workspace))
        # Limited access and locked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.LIMITED,
            is_locked=True,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertFalse(self.mixin._check_workspace_lock_ok(workspace))
        self.assertFalse(self.mixin.check_workspace(workspace))

    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_access", Workspace.AppAccessChoices.OWNER)
    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_unlocked", True)
    def test_check_workspace_workspace_access_owner_workspace_unlocked_true(self):
        # Owner and unlocked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.OWNER,
            is_locked=False,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertTrue(self.mixin.check_workspace(workspace))
        # Owner access and locked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.OWNER,
            is_locked=True,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertFalse(self.mixin._check_workspace_lock_ok(workspace))
        self.assertFalse(self.mixin.check_workspace(workspace))
        # Limited access and unlocked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.LIMITED,
            is_locked=False,
        )
        self.assertFalse(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertFalse(self.mixin.check_workspace(workspace))
        # Limited access and locked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.LIMITED,
            is_locked=True,
        )
        self.assertFalse(self.mixin._check_workspace_access_ok(workspace))
        self.assertFalse(self.mixin._check_workspace_lock_ok(workspace))
        self.assertFalse(self.mixin.check_workspace(workspace))

    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_access", Workspace.AppAccessChoices.LIMITED)
    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_unlocked", False)
    def test_check_workspace_workspace_access_limited_workspace_unlocked_false(self):
        # Owner and unlocked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.OWNER,
            is_locked=False,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertTrue(self.mixin.check_workspace(workspace))
        # Owner access and locked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.OWNER,
            is_locked=True,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertTrue(self.mixin.check_workspace(workspace))
        # Limited access and unlocked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.LIMITED,
            is_locked=False,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertTrue(self.mixin.check_workspace(workspace))
        # Limited access and locked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.LIMITED,
            is_locked=True,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertTrue(self.mixin.check_workspace(workspace))

    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_access", Workspace.AppAccessChoices.OWNER)
    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_unlocked", False)
    def test_check_workspace_workspace_access_owner_workspace_unlocked_false(self):
        # Owner and unlocked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.OWNER,
            is_locked=False,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertTrue(self.mixin.check_workspace(workspace))
        # Owner access and locked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.OWNER,
            is_locked=True,
        )
        self.assertTrue(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertTrue(self.mixin.check_workspace(workspace))
        # Limited access and unlocked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.LIMITED,
            is_locked=False,
        )
        self.assertFalse(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertFalse(self.mixin.check_workspace(workspace))
        # Limited access and locked.
        workspace = factories.WorkspaceFactory(
            app_access=Workspace.AppAccessChoices.LIMITED,
            is_locked=True,
        )
        self.assertFalse(self.mixin._check_workspace_access_ok(workspace))
        self.assertTrue(self.mixin._check_workspace_lock_ok(workspace))
        self.assertFalse(self.mixin.check_workspace(workspace))

    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "get_workspace_access", return_value="foo")
    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_unlocked", False)
    def test_check_workspace_get_workspace_access_invalid(self, mock):
        workspace = factories.WorkspaceFactory()
        with self.assertRaises(ValueError) as e:
            self.mixin._check_workspace_access_ok(workspace)
        self.assertIn("Invalid workspace access level: foo", str(e.exception))
        with self.assertRaises(ValueError) as e:
            self.mixin.check_workspace(workspace)
        self.assertIn("Invalid workspace access level: foo", str(e.exception))

    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "workspace_access", Workspace.AppAccessChoices.LIMITED)
    @patch.object(viewmixins.WorkspaceCheckAccessMixin, "get_workspace_unlocked", return_value="foo")
    def test_check_workspace_get_workspace_unlocked_invalid(self, mock):
        workspace = factories.WorkspaceFactory()
        with self.assertRaises(ValueError) as e:
            self.mixin._check_workspace_lock_ok(workspace)
        self.assertIn("Invalid workspace unlocked value: foo", str(e.exception))
        with self.assertRaises(ValueError) as e:
            self.mixin.check_workspace(workspace)
        self.assertIn("Invalid workspace unlocked value: foo", str(e.exception))
