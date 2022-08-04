from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.forms import ModelForm
from django.test import TestCase, override_settings

from ..adapter import (
    AdapterAlreadyRegisteredError,
    AdapterNotRegisteredError,
    BaseWorkspaceAdapter,
    DefaultWorkspaceAdapter,
    WorkspaceAdapterRegistry,
    get_adapter,
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
            workspace_data_type = None
            list_table_class = tables.TestWorkspaceDataTable
            workspace_data_model = None
            workspace_data_form_class = None

        self.assertEqual(
            TestAdapter().get_list_table_class(), tables.TestWorkspaceDataTable
        )

    def test_list_table_class_none(self):
        """get_list_table_class raises ImproperlyConfigured when list_table_class is not set."""

        class TestAdapter(BaseWorkspaceAdapter):
            workspace_data_type = None
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
            workspace_data_type = None
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = forms.TestWorkspaceDataForm

        self.assertEqual(
            TestAdapter().get_workspace_data_form_class(), forms.TestWorkspaceDataForm
        )

    def test_get_workspace_data_form_class_none(self):
        """get_workspace_data_form_class raises exception if form class is not set."""

        class TestAdapter(BaseWorkspaceAdapter):
            workspace_data_type = None
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
            workspace_data_type = None
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
            workspace_data_type = None
            list_table_class = None
            workspace_data_model = models.TestWorkspaceData
            workspace_data_form_class = None

        self.assertEqual(
            TestAdapter().get_workspace_data_model(), models.TestWorkspaceData
        )

    def test_get_workspace_data_model_subclass(self):
        """workspace_data_model must be a subclass of models.BaseWorkspaceData"""

        class TestAdapter(BaseWorkspaceAdapter):
            workspace_data_type = None
            list_table_class = None
            workspace_data_model = forms.TestWorkspaceDataForm  # use a random class.
            workspace_data_form_class = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_model()

    def test_get_workspace_data_model_none(self):
        """get_workspace_data_model raises ImproperlyConfigured when workspace_data_model is not set."""

        class TestAdapter(BaseWorkspaceAdapter):
            workspace_data_type = None
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_model()

    def test_get_workspace_data_type_default(self):
        """get_workspace_data_type returns the correct string when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_workspace_data_type(),
            "default",
        )

    def test_get_workspace_data_type_custom(self):
        """get_workspace_data_type returns the correct model when using a custom adapter."""

        class TestAdapter(BaseWorkspaceAdapter):
            workspace_data_type = "test_adapter"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        self.assertEqual(TestAdapter().get_workspace_data_type(), "test_adapter")

    def test_get_workspace_data_type_none(self):
        """get_workspace_data_type raises ImproperlyConfigured when get_workspace_data_type is not set."""

        class TestAdapter(BaseWorkspaceAdapter):
            workspace_data_type = None
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_type()


class GetAdapterTest(TestCase):
    """Tests for the get_adapter method."""

    def test_default(self):
        """get_adapter returns the default adapter with standard test settings."""
        self.assertIsInstance(get_adapter(), DefaultWorkspaceAdapter)

    @override_settings(
        ANVIL_ADAPTER="anvil_consortium_manager.tests.adapter_app.adapters.TestWorkspaceAdapter"
    )
    def test_custom(self):
        """get_adapter returns the custom test adapter when set."""
        self.assertIsInstance(get_adapter(), TestWorkspaceAdapter)

    @override_settings()
    def test_anviL_adapter_not_set(self):
        """get_adapter uses the default if ANVIL_ADAPTER is not set."""
        del settings.ANVIL_ADAPTER
        self.assertIsInstance(get_adapter(), DefaultWorkspaceAdapter)

    # Use a random class here.
    @override_settings(
        ANVIL_ADAPTER="anvil_consortium_manager.tests.adapter_app.forms.TestWorkspaceDataForm"
    )
    def test_subclass(self):
        """get_adapter raises an error when the subclass of the adapter is incorrect."""
        with self.assertRaises(ImproperlyConfigured):
            get_adapter()


class WorkspaceAdapterRegistryTest(TestCase):
    """Tests for the WorkspaceAdapterRegstry model."""

    def test_can_register_adapter(self):
        """Can register an adapter."""
        registry = WorkspaceAdapterRegistry()
        registry.register(DefaultWorkspaceAdapter)
        self.assertEqual(len(registry._registry), 1)
        self.assertIn("default", registry._registry)
        self.assertEqual(registry._registry["default"], DefaultWorkspaceAdapter)

    def test_cannot_register_adapter_twicwe(self):
        """Cannot register an adapter with the same type as another registered adapter."""
        registry = WorkspaceAdapterRegistry()

        class TestAdapter(BaseWorkspaceAdapter):
            workspace_data_type = "adapter_type"
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
            workspace_data_type = "adapter_type"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        class Adapter2(BaseWorkspaceAdapter):
            workspace_data_type = "adapter_type"
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
            workspace_data_type = "adapter_type"
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
            workspace_data_type = "adapter_type"
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        class Adapter2(BaseWorkspaceAdapter):
            workspace_data_type = "adapter_type"
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
