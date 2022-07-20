from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from ..adapter import DefaultWorkspaceAdapter
from ..tables import WorkspaceTable
from .adapter_app import forms, models, tables


class WorkspaceAdapterTest(TestCase):
    """Tests for extending the WorkspaceAdapter class."""

    def test_default_list_table_class(self):
        """get_list_table_class returns the correct table when using the default adapter."""
        adapter = DefaultWorkspaceAdapter()
        self.assertEqual(adapter.get_list_table_class(), WorkspaceTable)

    def test_custom_list_table_class(self):
        """get_list_table_class returns the correct table when using a custom adapter."""

        class TestAdapter(DefaultWorkspaceAdapter):
            list_table_class = tables.TestWorkspaceDataTable

        self.assertEqual(
            TestAdapter().get_list_table_class(), tables.TestWorkspaceDataTable
        )

    def test_default_get_workspace_data_form_class(self):
        """get_workspace_data_form_class returns the correct form when using a custom adapter."""
        self.assertIsNone(DefaultWorkspaceAdapter().get_workspace_data_form_class())

    def test_custom_get_workspace_data_form_class(self):
        """get_workspace_data_form_class returns the correct form when using a custom adapter."""

        class TestAdapter(DefaultWorkspaceAdapter):
            workspace_data_model = models.TestWorkspaceData
            workspace_data_form_class = forms.TestWorkspaceDataForm

        self.assertEqual(
            TestAdapter().get_workspace_data_form_class(), forms.TestWorkspaceDataForm
        )

    def test_custom_get_workspace_data_form_class_no_model(self):
        """get_workspace_data_form_class raises exception if form class but not model is set."""

        class TestAdapter(DefaultWorkspaceAdapter):
            workspace_data_model = models.TestWorkspaceData

        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_form_class()
