from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from ..adapter import BaseWorkspaceAdapter, DefaultWorkspaceAdapter, get_adapter
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
            list_table_class = tables.TestWorkspaceDataTable
            workspace_data_model = None
            workspace_data_form_class = None

        self.assertEqual(
            TestAdapter().get_list_table_class(), tables.TestWorkspaceDataTable
        )

    def test_list_table_class_none(self):
        """get_list_table_class raises ImproperlyConfigured when list_table_class is not set."""

        class TestAdapter(BaseWorkspaceAdapter):
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
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = forms.TestWorkspaceDataForm

        self.assertEqual(
            TestAdapter().get_workspace_data_form_class(), forms.TestWorkspaceDataForm
        )

    def test_get_workspace_data_form_class_none(self):
        """get_workspace_data_form_class raises exception if form class but not model is set."""

        class TestAdapter(BaseWorkspaceAdapter):
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

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
            list_table_class = None
            workspace_data_model = models.TestWorkspaceData
            workspace_data_form_class = None

        self.assertEqual(
            TestAdapter().get_workspace_data_model(), models.TestWorkspaceData
        )

    def test_get_workspace_data_model_subclass(self):
        """workspace_data_model must be a subclass of models.AbstractWorkspaceData"""

        class TestAdapter(BaseWorkspaceAdapter):
            list_table_class = None
            workspace_data_model = forms.TestWorkspaceDataForm  # use a random class.
            workspace_data_form_class = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_model()

    def test_get_workspace_data_model_none(self):
        """get_workspace_data_model raises ImproperlyConfigured when workspace_data_model is not set."""

        class TestAdapter(BaseWorkspaceAdapter):
            list_table_class = None
            workspace_data_model = None
            workspace_data_form_class = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_model()


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

    # Use a random class here.
    @override_settings(
        ANVIL_ADAPTER="anvil_consortium_manager.tests.adapter_app.forms.TestWorkspaceDataForm"
    )
    def test_subclass(self):
        """get_adapter raises an error when the subclass of the adapter is incorrect."""
        with self.assertRaises(ImproperlyConfigured):
            get_adapter()
