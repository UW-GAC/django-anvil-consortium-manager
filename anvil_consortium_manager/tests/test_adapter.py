from django.core.exceptions import ImproperlyConfigured
from django.forms import ModelForm
from django.test import TestCase, override_settings

from ..adapters.default import DefaultWorkspaceAdapter
from ..adapters.workspace import (
    AdapterAlreadyRegisteredError,
    AdapterNotRegisteredError,
    BaseWorkspaceAdapter,
    WorkspaceAdapterRegistry,
)
from ..forms import DefaultWorkspaceDataForm
from ..models import DefaultWorkspaceData
from ..tables import WorkspaceTable
from .adapter_app import forms, models, tables
from .adapter_app.adapters import TestWorkspaceAdapter


class WorkspaceAdapterTest(TestCase):
    """Tests for extending the WorkspaceAdapter class."""

    def test_list_table_class_default(self):
        """get_list_table_class returns the correct table when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_list_table_class(), WorkspaceTable
        )

    def test_list_table_class_custom(self):
        """get_list_table_class returns the correct table when using a custom adapter."""

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = None
            list_table_class = tables.TestWorkspaceDataTable
            workspace_data_model = None
            workspace_data_form_class = None

        self.assertEqual(
            TestAdapter().get_list_table_class(), tables.TestWorkspaceDataTable
        )

    def test_list_table_class_none(self):
        """get_list_table_class raises ImproperlyConfigured when list_table_class is not set."""

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = None
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_list_table_class()

    def test_get_workspace_data_form_class_default(self):
        """get_workspace_data_form_class returns the correct form when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_workspace_data_form_class(),
            DefaultWorkspaceDataForm,
        )

    def test_get_workspace_data_form_class_custom(self):
        """get_workspace_data_form_class returns the correct form when using a custom adapter."""

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = None
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = forms.TestWorkspaceDataForm

        self.assertEqual(
            TestAdapter().get_workspace_data_form_class(), forms.TestWorkspaceDataForm
        )

    def test_get_workspace_data_form_class_none(self):
        """get_workspace_data_form_class raises exception if form class is not set."""

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = None
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_form_class()

    def test_get_workspace_data_form_class_missing_workspace(self):
        """get_workspace_data_form_class raises exception if form does not have a workspace field."""

        class TestFormClass(ModelForm):
            class Meta:
                model = models.TestWorkspaceData
                fields = ("study_name",)

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = None
            list_table_class = None
            workspace_data_model = models.TestWorkspaceData
            workspace_data_form_class = TestFormClass

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_form_class()

    def test_get_workspace_data_model_default(self):
        """get_workspace_data_model returns the correct model when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_workspace_data_model(), DefaultWorkspaceData
        )

    def test_get_workspace_data_model_custom(self):
        """get_workspace_data_model returns the correct model when using a custom adapter."""

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = None
            list_table_class = None
            workspace_data_model = models.TestWorkspaceData
            workspace_data_form_class = None

        self.assertEqual(
            TestAdapter().get_workspace_data_model(), models.TestWorkspaceData
        )

    def test_get_workspace_data_model_subclass(self):
        """workspace_data_model must be a subclass of models.BaseWorkspaceData"""

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = None
            list_table_class = None
            workspace_data_model = forms.TestWorkspaceDataForm  # use a random class.
            workspace_data_form_class = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_model()

    def test_get_workspace_data_model_none(self):
        """get_workspace_data_model raises ImproperlyConfigured when workspace_data_model is not set."""

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = None
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_model()

    def test_get_type_default(self):
        """get_type returns the correct string when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_type(),
            "workspace",
        )

    def test_get_type_custom(self):
        """get_type returns the correct model when using a custom adapter."""

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = "test_adapter"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        self.assertEqual(TestAdapter().get_type(), "test_adapter")

    def test_get_type_none(self):
        """get_type raises ImproperlyConfigured when type is not set."""

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = None
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_type()

    def test_get_name_default(self):
        """get_name returns the correct string when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_name(),
            "Workspace",
        )

    def test_get_name_custom(self):
        """get_type returns the correct model when using a custom adapter."""

        class TestAdapter(BaseWorkspaceAdapter):
            name = "Test"
            type = None
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        self.assertEqual(TestAdapter().get_name(), "Test")

    def test_get_name_none(self):
        """get_type raises ImproperlyConfigured when type is not set."""

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = None
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_name()


class WorkspaceAdapterRegistryTest(TestCase):
    """Tests for the WorkspaceAdapterRegstry model."""

    def test_can_register_adapter(self):
        """Can register an adapter."""
        registry = WorkspaceAdapterRegistry()
        registry.register(DefaultWorkspaceAdapter)
        self.assertEqual(len(registry._registry), 1)
        self.assertIn("workspace", registry._registry)
        self.assertEqual(registry._registry["workspace"], DefaultWorkspaceAdapter)

    def test_register_two_adapters(self):
        """Cannot register an adapter with the same type as another registered adapter."""
        registry = WorkspaceAdapterRegistry()

        class Adapter1(BaseWorkspaceAdapter):
            name = None
            type = "adapter1"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        class Adapter2(BaseWorkspaceAdapter):
            name = None
            type = "adapter2"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        registry.register(Adapter1)
        registry.register(Adapter2)
        self.assertEqual(len(registry._registry), 2)
        self.assertIn("adapter1", registry._registry)
        self.assertEqual(registry._registry["adapter1"], Adapter1)
        self.assertIn("adapter2", registry._registry)
        self.assertEqual(registry._registry["adapter2"], Adapter2)

    def test_cannot_register_adapter_twice(self):
        """Cannot register the same adapter twice."""
        registry = WorkspaceAdapterRegistry()

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = "adapter_type"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        registry.register(TestAdapter)
        with self.assertRaises(AdapterAlreadyRegisteredError):
            registry.register(TestAdapter)
        self.assertEqual(len(registry._registry), 1)
        self.assertIn("adapter_type", registry._registry)
        self.assertEqual(registry._registry["adapter_type"], TestAdapter)

    def test_cannot_register_adapter_with_same_type(self):
        """Cannot register an adapter with the same type as another registered adapter."""
        registry = WorkspaceAdapterRegistry()

        class Adapter1(BaseWorkspaceAdapter):
            name = None
            type = "adapter_type"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        class Adapter2(BaseWorkspaceAdapter):
            name = None
            type = "adapter_type"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        registry.register(Adapter1)
        with self.assertRaises(AdapterAlreadyRegisteredError):
            registry.register(Adapter2)
        self.assertEqual(len(registry._registry), 1)
        self.assertIn("adapter_type", registry._registry)
        self.assertEqual(registry._registry["adapter_type"], Adapter1)

    def test_cannot_register_adapter_with_wrong_subclass(self):
        """Cannot register an adapter that does not subclass `BaseWorkspaceAdapter`."""
        registry = WorkspaceAdapterRegistry()

        class TestAdapter:
            pass

        with self.assertRaises(ImproperlyConfigured):
            registry.register(TestAdapter)

    def test_can_unregister_adapter(self):
        """Can unregister an adapter."""
        registry = WorkspaceAdapterRegistry()
        registry.register(DefaultWorkspaceAdapter)
        registry.unregister(DefaultWorkspaceAdapter)
        self.assertEqual(len(registry._registry), 0)

    def test_cannot_unregister_adapter_that_is_not_registered(self):
        """Cannot unregister an adapter that has not been registered yet."""
        registry = WorkspaceAdapterRegistry()

        class TestAdapter(BaseWorkspaceAdapter):
            name = None
            type = "adapter_type"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        with self.assertRaises(AdapterNotRegisteredError):
            registry.unregister(TestAdapter)
        self.assertEqual(len(registry._registry), 0)

    def test_cannot_unregister_adapter_with_same_type(self):
        """Cannot unregister an adapter with the same type as another registered adapter."""
        registry = WorkspaceAdapterRegistry()

        class Adapter1(BaseWorkspaceAdapter):
            name = None
            type = "adapter_type"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        class Adapter2(BaseWorkspaceAdapter):
            name = None
            type = "adapter_type"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        registry.register(Adapter1)
        with self.assertRaises(AdapterNotRegisteredError):
            registry.unregister(Adapter2)
        self.assertEqual(len(registry._registry), 1)
        self.assertIn("adapter_type", registry._registry)
        self.assertEqual(registry._registry["adapter_type"], Adapter1)

    def test_cannot_unregister_adapter_with_wrong_subclass(self):
        """Cannot unregister an adapter that does not subclass `BaseWorkspaceAdapter`."""
        registry = WorkspaceAdapterRegistry()

        class TestAdapter:
            pass

        with self.assertRaises(ImproperlyConfigured):
            registry.unregister(TestAdapter)

    def test_get_registered_apdaters_zero(self):
        """get_registered_adapters returns an empty dictionary when no adapters are registered."""
        registry = WorkspaceAdapterRegistry()
        self.assertEqual(registry.get_registered_adapters(), {})

    def test_get_registered_apdaters_one(self):
        """get_registered_adapters returns the correct dictionary when one adapter is registered."""
        registry = WorkspaceAdapterRegistry()

        class Adapter(BaseWorkspaceAdapter):
            name = None
            type = "adapter"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        registry.register(Adapter)
        self.assertEqual(registry.get_registered_adapters(), {"adapter": Adapter})

    def test_get_registered_apdaters_two(self):
        """get_registered_adapters returns the correct dictionary when two adapters are registered."""

        registry = WorkspaceAdapterRegistry()

        class Adapter1(BaseWorkspaceAdapter):
            name = None
            type = "adapter1"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        class Adapter2(BaseWorkspaceAdapter):
            name = None
            type = "adapter2"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        registry.register(Adapter1)
        registry.register(Adapter2)
        self.assertEqual(
            registry.get_registered_adapters(),
            {"adapter1": Adapter1, "adapter2": Adapter2},
        )

    def test_get_registered_names_zero(self):
        """get_registered_names returns an empty dictionary when no adapters are registered."""
        registry = WorkspaceAdapterRegistry()
        self.assertEqual(registry.get_registered_adapters(), {})

    def test_get_registered_names_one(self):
        """get_registered_names returns the correct dictionary when one adapter is registered."""
        registry = WorkspaceAdapterRegistry()

        class Adapter(BaseWorkspaceAdapter):
            name = "Adapter"
            type = "adapter"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        registry.register(Adapter)
        self.assertEqual(registry.get_registered_names(), {"adapter": "Adapter"})

    def test_get_registered_names_two(self):
        """get_registered_names returns the correct dictionary when two adapters are registered."""

        registry = WorkspaceAdapterRegistry()

        class Adapter1(BaseWorkspaceAdapter):
            name = "Adapter 1"
            type = "adapter1"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        class Adapter2(BaseWorkspaceAdapter):
            name = "Adapter 2"
            type = "adapter2"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        registry.register(Adapter1)
        registry.register(Adapter2)
        self.assertEqual(
            registry.get_registered_names(),
            {"adapter1": "Adapter 1", "adapter2": "Adapter 2"},
        )

    def test_populate_from_settings_default(self):
        registry = WorkspaceAdapterRegistry()
        registry.populate_from_settings()
        self.assertEqual(len(registry._registry), 1)
        adapter_type = DefaultWorkspaceAdapter().get_type()
        self.assertIn(adapter_type, registry._registry)
        self.assertEqual(registry._registry[adapter_type], DefaultWorkspaceAdapter)

    @override_settings(
        ANVIL_WORKSPACE_ADAPTERS=[
            "anvil_consortium_manager.adapters.default.DefaultWorkspaceAdapter",
            "anvil_consortium_manager.tests.adapter_app.adapters.TestWorkspaceAdapter",
        ]
    )
    def test_populate_from_settings_multiple(self):
        registry = WorkspaceAdapterRegistry()
        registry.populate_from_settings()
        self.assertEqual(len(registry._registry), 2)
        adapter_type = DefaultWorkspaceAdapter().get_type()
        self.assertIn(adapter_type, registry._registry)
        self.assertEqual(registry._registry[adapter_type], DefaultWorkspaceAdapter)
        adapter_type = TestWorkspaceAdapter().get_type()
        self.assertIn(adapter_type, registry._registry)
        self.assertEqual(registry._registry[adapter_type], TestWorkspaceAdapter)

    @override_settings(ANVIL_WORKSPACE_ADAPTERS=[])
    def test_populate_from_settings_zero_adapters_error(self):
        """ImproperlyConfigured error is raised when zero adapters are specified."""
        registry = WorkspaceAdapterRegistry()
        with self.assertRaises(ImproperlyConfigured) as e:
            registry.populate_from_settings()
        self.assertIn("at least one adapter", str(e.exception))

    def test_populate_from_settings_cannot_populate_twice(self):
        registry = WorkspaceAdapterRegistry()
        registry.populate_from_settings()
        with self.assertRaises(RuntimeError) as e:
            registry.populate_from_settings()
        self.assertIn("already been populated", str(e.exception))