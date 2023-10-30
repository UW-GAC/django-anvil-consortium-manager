from django.core.exceptions import ImproperlyConfigured
from django.forms import Form, ModelForm
from django.test import TestCase, override_settings

from ..adapters.account import BaseAccountAdapter
from ..adapters.default import DefaultAccountAdapter, DefaultWorkspaceAdapter
from ..adapters.workspace import (
    AdapterAlreadyRegisteredError,
    AdapterNotRegisteredError,
    BaseWorkspaceAdapter,
    WorkspaceAdapterRegistry,
)
from ..filters import AccountListFilter, BillingProjectListFilter
from ..forms import DefaultWorkspaceDataForm, WorkspaceForm
from ..models import Account, DefaultWorkspaceData
from ..tables import AccountTable, WorkspaceTable
from . import factories
from .test_app import filters, forms, models, tables
from .test_app.adapters import TestWorkspaceAdapter


class AccountAdapterTestCase(TestCase):
    """Tests for Account adapters."""

    def get_test_adapter(self):
        """Return a test adapter class for use in tests."""

        class TestAdapter(BaseAccountAdapter):
            list_table_class = tables.TestAccountTable
            list_filterset_class = filters.TestAccountListFilter

        return TestAdapter

    def test_list_table_class_default(self):
        """get_list_table_class returns the correct table when using the default adapter."""
        self.assertEqual(DefaultAccountAdapter().get_list_table_class(), AccountTable)

    def test_list_table_class_custom(self):
        """get_list_table_class returns the correct table when using a custom adapter."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "list_table_class", tables.TestAccountTable)
        self.assertEqual(TestAdapter().get_list_table_class(), tables.TestAccountTable)

    def test_list_table_class_none(self):
        """get_list_table_class raises ImproperlyConfigured when list_table_class is not set."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "list_table_class", None)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_list_table_class()

    def test_list_filterset_class_default(self):
        """get_list_filterset_class returns the correct filter when using the default adapter."""
        self.assertEqual(
            DefaultAccountAdapter().get_list_filterset_class(), AccountListFilter
        )

    def test_list_filterset_class_custom(self):
        """get_list_filterset_class returns the correct filter when using a custom adapter."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "list_filterset_class", filters.TestAccountListFilter)
        self.assertEqual(
            TestAdapter().get_list_filterset_class(), filters.TestAccountListFilter
        )

    def test_list_filterset_class_none(self):
        """get_list_filterset_class raises ImproperlyConfigured when get_list_filterset_class is not set."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "list_filterset_class", None)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_list_filterset_class()

    def test_list_filterset_class_different_model(self):
        """get_list_filterset_class raises ImproperlyConfigured when incorrect model is used."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "list_filterset_class", BillingProjectListFilter)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_list_filterset_class()

    def test_list_filterset_class_not_filterset(self):
        """get_list_filterset_class raises ImproperlyConfigured when not a subclass of FilterSet."""

        class Foo:
            pass

        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "list_filterset_class", Foo)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_list_filterset_class()

    def test_get_autocomplete_queryset_default(self):
        """get_autocomplete_queryset returns the correct queryset when using the default adapter."""
        account_1 = factories.AccountFactory.create(email="test@test.com")
        account_2 = factories.AccountFactory.create(email="foo@bar.com")
        qs = DefaultAccountAdapter().get_autocomplete_queryset(
            Account.objects.all(), "test"
        )
        self.assertEqual(qs.count(), 1)
        self.assertIn(account_1, qs)
        self.assertNotIn(account_2, qs)

    def test_get_autocomplete_queryset_custom(self):
        """get_autocomplete_queryset returns the correct queryset when using a custom adapter."""

        def foo(self, queryset, q):
            return queryset.filter(email__startswith=q)

        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "get_autocomplete_queryset", foo)
        account_1 = factories.AccountFactory.create(email="test@test.com")
        account_2 = factories.AccountFactory.create(email="foo@test.com")
        qs = TestAdapter().get_autocomplete_queryset(Account.objects.all(), "test")
        self.assertEqual(qs.count(), 1)
        self.assertIn(account_1, qs)
        self.assertNotIn(account_2, qs)

    def test_get_autocomplete_label_default(self):
        """get_label_from_instance returns the correct queryset when using the default adapter."""
        account = factories.AccountFactory.create(email="test@test.com")
        self.assertEqual(
            DefaultAccountAdapter().get_autocomplete_label(account), "test@test.com"
        )

    def test_get_autocomplete_label_custom(self):
        """get_label_from_instance returns the correct queryset when using a custom adapter."""

        account = factories.AccountFactory.create(
            verified=True, user__username="testuser"
        )

        def foo(self, account):
            return account.user.username

        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "get_autocomplete_label", foo)
        self.assertEqual(TestAdapter().get_autocomplete_label(account), "testuser")


class WorkspaceAdapterTest(TestCase):
    """Tests for Workspace adapters."""

    def get_test_adapter(self):
        """Return a test adapter class for use in tests."""

        class TestAdapter(BaseWorkspaceAdapter):
            name = "Test"
            type = "test"
            description = "test desc"
            list_table_class = tables.TestWorkspaceDataTable
            workspace_form_class = forms.WorkspaceForm
            workspace_data_model = models.TestWorkspaceData
            workspace_data_form_class = forms.TestWorkspaceDataForm
            workspace_detail_template_name = "custom/workspace_detail.html"

        return TestAdapter

    def test_list_table_class_default(self):
        """get_list_table_class returns the correct table when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_list_table_class(), WorkspaceTable
        )

    def test_list_table_class_custom(self):
        """get_list_table_class returns the correct table when using a custom adapter."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "list_table_class", tables.TestWorkspaceDataTable)
        self.assertEqual(
            TestAdapter().get_list_table_class(), tables.TestWorkspaceDataTable
        )

    def test_list_table_class_none(self):
        """get_list_table_class raises ImproperlyConfigured when list_table_class is not set."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "list_table_class", None)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_list_table_class()

    def test_get_workspace_form_class_default(self):
        """get_workspace_form_class returns the correct form when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_workspace_form_class(),
            WorkspaceForm,
        )

    def test_get_workspace_form_class_custom(self):
        """get_workspace_form_class returns the correct form when using a custom adapter."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "workspace_form_class", forms.TestWorkspaceForm)
        self.assertEqual(
            TestAdapter().get_workspace_form_class(), forms.TestWorkspaceForm
        )

    def test_get_workspace_form_class_none(self):
        """get_workspace_form_class raises exception if form class is not set."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "workspace_form_class", None)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_form_class()

    def test_get_workspace_form_class_wrong_model(self):
        """ImproperlyConfigured raised when wrong model is speciifed in Meta."""
        TestAdapter = self.get_test_adapter()

        class TestForm(ModelForm):
            class Meta:
                model = Account
                fields = ("email",)

        setattr(TestAdapter, "workspace_form_class", TestForm)
        with self.assertRaises(ImproperlyConfigured) as e:
            TestAdapter().get_workspace_form_class()
        self.assertIn("workspace_form_class Meta model", str(e.exception))

    def test_get_workspace_form_class_wrong_subclass(self):
        """ImproperlyConfigured raised when form is not a ModelForm."""
        TestAdapter = self.get_test_adapter()

        class TestForm(Form):
            pass

        setattr(TestAdapter, "workspace_form_class", TestForm)
        with self.assertRaises(ImproperlyConfigured) as e:
            TestAdapter().get_workspace_form_class()
        self.assertIn("ModelForm", str(e.exception))

    def test_get_workspace_data_form_class_default(self):
        """get_workspace_data_form_class returns the correct form when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_workspace_data_form_class(),
            DefaultWorkspaceDataForm,
        )

    def test_get_workspace_data_form_class_custom(self):
        """get_workspace_data_form_class returns the correct form when using a custom adapter."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "workspace_data_form_class", forms.TestWorkspaceDataForm)
        self.assertEqual(
            TestAdapter().get_workspace_data_form_class(), forms.TestWorkspaceDataForm
        )

    def test_get_workspace_data_form_class_none(self):
        """get_workspace_data_form_class raises exception if form class is not set."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "workspace_data_form_class", None)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_form_class()

    def test_get_workspace_data_form_class_missing_workspace(self):
        """get_workspace_data_form_class raises exception if form does not have a workspace field."""

        class TestFormClass(ModelForm):
            class Meta:
                model = models.TestWorkspaceData
                fields = ("study_name",)

        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "workspace_data_form_class", TestFormClass)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_form_class()

    def test_get_workspace_data_model_default(self):
        """get_workspace_data_model returns the correct model when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_workspace_data_model(), DefaultWorkspaceData
        )

    def test_get_workspace_data_model_custom(self):
        """get_workspace_data_model returns the correct model when using a custom adapter."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "workspace_data_model", models.TestWorkspaceData)
        self.assertEqual(
            TestAdapter().get_workspace_data_model(), models.TestWorkspaceData
        )

    def test_get_workspace_data_model_subclass(self):
        """workspace_data_model must be a subclass of models.BaseWorkspaceData"""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "workspace_data_model", forms.TestWorkspaceDataForm)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_data_model()

    def test_get_workspace_data_model_none(self):
        """get_workspace_data_model raises ImproperlyConfigured when workspace_data_model is not set."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "workspace_data_model", None)
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
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "type", "test_adapter")
        self.assertEqual(TestAdapter().get_type(), "test_adapter")

    def test_get_type_none(self):
        """get_type raises ImproperlyConfigured when type is not set."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "type", None)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_type()

    def test_get_name_default(self):
        """get_name returns the correct string when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_name(),
            "Workspace",
        )

    def test_get_name_custom(self):
        """get_name returns the correct model when using a custom adapter."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "name", "Test")
        self.assertEqual(TestAdapter().get_name(), "Test")

    def test_get_description_default(self):
        """get_description returns the correct string when using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_description(),
            "Default workspace",
        )

    def test_get_description_custom(self):
        """get_description returns the correct model when using a custom adapter."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "name", "Test")
        self.assertEqual(TestAdapter().get_description(), "test desc")

    def test_get_description_none(self):
        """get_description raises ImproperlyConfigured when type is not set."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "description", None)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_description()

    def test_get_name_none(self):
        """get_name raises ImproperlyConfigured when type is not set."""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "name", None)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_name()

    def test_get_workspace_detail_template_name_default(self):
        """get_workspace_detail_template_name returns the correct template using the default adapter."""
        self.assertEqual(
            DefaultWorkspaceAdapter().get_workspace_detail_template_name(),
            "anvil_consortium_manager/workspace_detail.html",
        )

    def test_get_workspace_detail_template_name_custom(self):
        """get_workspace_detail_template_name returns the corret template when using a custom adapter"""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "workspace_detail_template_name", "foo")
        self.assertEqual(
            TestAdapter().get_workspace_detail_template_name(),
            "foo",
        )

    def test_get_workspace_detail_template_name_none(self):
        """get_workspace_detail_template_name raises ImproperlyConfigured when it is not set"""
        TestAdapter = self.get_test_adapter()
        setattr(TestAdapter, "workspace_detail_template_name", None)
        with self.assertRaises(ImproperlyConfigured):
            TestAdapter().get_workspace_detail_template_name()


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
            description = "one"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

        class Adapter2(BaseWorkspaceAdapter):
            name = None
            type = "adapter2"
            description = "two"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

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
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

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
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

        class Adapter2(BaseWorkspaceAdapter):
            name = None
            type = "adapter_type"
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

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
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

        with self.assertRaises(AdapterNotRegisteredError):
            registry.unregister(TestAdapter)
        self.assertEqual(len(registry._registry), 0)

    def test_cannot_unregister_adapter_with_same_type(self):
        """Cannot unregister an adapter with the same type as another registered adapter."""
        registry = WorkspaceAdapterRegistry()

        class Adapter1(BaseWorkspaceAdapter):
            name = None
            type = "adapter_type"
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

        class Adapter2(BaseWorkspaceAdapter):
            name = None
            type = "adapter_type"
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

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
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

        registry.register(Adapter)
        self.assertEqual(registry.get_registered_adapters(), {"adapter": Adapter})

    def test_get_registered_apdaters_two(self):
        """get_registered_adapters returns the correct dictionary when two adapters are registered."""

        registry = WorkspaceAdapterRegistry()

        class Adapter1(BaseWorkspaceAdapter):
            name = None
            type = "adapter1"
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

        class Adapter2(BaseWorkspaceAdapter):
            name = None
            type = "adapter2"
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

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
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

        registry.register(Adapter)
        self.assertEqual(registry.get_registered_names(), {"adapter": "Adapter"})

    def test_get_registered_names_two(self):
        """get_registered_names returns the correct dictionary when two adapters are registered."""

        registry = WorkspaceAdapterRegistry()

        class Adapter1(BaseWorkspaceAdapter):
            name = "Adapter 1"
            type = "adapter1"
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

        class Adapter2(BaseWorkspaceAdapter):
            name = "Adapter 2"
            type = "adapter2"
            description = "desc"
            list_table_class = None
            workspace_form_class = None
            workspace_data_model = None
            workspace_data_form_class = None
            workspace_detail_template_name = None

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
            "anvil_consortium_manager.tests.test_app.adapters.TestWorkspaceAdapter",
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
