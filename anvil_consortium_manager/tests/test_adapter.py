from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from ..adapter import DefaultWorkspaceAdapter
from ..forms import DefaultWorkspaceDataForm
from ..models import DefaultWorkspaceData
from ..tables import WorkspaceTable
from .adapter_app import forms, models, tables


class WorkspaceAdapterTest(TestCase):
    """Tests for extending the WorkspaceAdapter class."""

    def test_list_table_class_default(self):
        """get_list_table_class returns the correct table when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_list_table_class(), WorkspaceTable
        )

    def test_list_table_class_custom(self):
        """get_list_table_class returns the correct table when using a custom adapter."""

        class TestAdapter(DefaultWorkspaceAdapter):
            list_table_class = tables.TestWorkspaceDataTable

        self.assertEqual(
            TestAdapter().get_list_table_class(), tables.TestWorkspaceDataTable
        )

    def test_list_table_class_none(self):
        """get_list_table_class raises ImproperlyConfigured when list_table_class is not set."""

        class TestAdapter(DefaultWorkspaceAdapter):
            list_table_class = None

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

        class TestAdapter(DefaultWorkspaceAdapter):
            workspace_data_form_class = forms.TestWorkspaceDataForm

        self.assertEqual(
            TestAdapter().get_workspace_data_form_class(), forms.TestWorkspaceDataForm
        )

    def test_get_workspace_data_form_class_none(self):
        """get_workspace_data_form_class raises exception if form class but not model is set."""

        class TestAdapter(DefaultWorkspaceAdapter):
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

        class TestAdapter(DefaultWorkspaceAdapter):
            workspace_data_model = models.TestWorkspaceData

        self.assertEqual(
            TestAdapter().get_workspace_data_model(), models.TestWorkspaceData
        )

    def test_get_workspace_data_model_none(self):
        """get_workspace_data_model raises ImproperlyConfigured when workspace_data_model is not set."""

        class TestAdapter(DefaultWorkspaceAdapter):
            workspace_data_model = None

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_model()
