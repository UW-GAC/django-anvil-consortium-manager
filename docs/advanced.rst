.. _advanced:

Advanced Usage
==============

.. _account_adapter:

The account adapter
-------------------

The app provides an adapter that you can use to customize behavior for Accounts.
By default, the app uses :class:`~anvil_consortium_manager.adapters.default.DefaultAccountAdapter`.

To customize app behavior for accounts, you must subclass :class:`~anvil_consortium_manager.adapters.account.BaseAccountAdapter`
and set the following attributes:

- ``list_table_class``: an attribute set to the class of the table used to display accounts in the :class:`~anvil_consortium_manager.views.AccountList` view. The default adapter uses :class:`anvil_consortium_manager.tables.AccountStaffTable`.
- ``list_filterset_class``: an attribute set to the class of the table used to filter accounts in the :class:`~anvil_consortium_manager.views.AccountList` view. The default adapter uses :class:`anvil_consortium_manager.filters.AccountListFilter`. This must subclass ``FilterSet`` from `django-filter <https://django-filter.readthedocs.io/en/stable/>`_.

Optionally, you can override the following methods:

- ``get_autocomplete_queryset(self, queryset, q)``: a method that allows the user to provide custom filtering for the autocomplete view. By default, this filters to Accounts whose email contains the case-insensitive search string in ``q``.
- ``get_autocomplete_label(self, account)``: a method that allows the user to set the label for an account shown in forms using the autocomplete widget.

.. _managed_group_adapter:

The Managed Group adapter
-------------------

The app provides an adapter that you can use to customize behavior for Managed Groups.
By default, the app uses :class:`~anvil_consortium_manager.adapters.default.DefaultManagedGroupAdapter`.

To customize app behavior for accounts, you must subclass :class:`~anvil_consortium_manager.adapters.account.BaseManagedGroupAdapter`
and set the following attributes:

- ``list_table_class_staff_view``: an attribute set to the class of the table used to display managed groups in the :class:`~anvil_consortium_manager.views.ManagedGroupList` view to users with StaffView permission. The default adapter uses :class:`anvil_consortium_manager.tables.ManagedGroupStaffTable`.
- ``list_table_class_staff_view``: an attribute set to the class of the table used to display accounts in the :class:`~anvil_consortium_manager.views.ManagedGroupList` view to users with View permission. The default adapter uses :class:`anvil_consortium_manager.tables.ManagedGroupUserTable`.

Optionally, you can override the following methods:

- ``after_anvil_create(self, managed_group)``: a method to perform any actions after creating the Managed Group on AnVIL via the :class:`~anvil_consortium_manager.views.ManagedGroupCreate` view.

.. _workspace_adapter:

The workspace adapter
---------------------

The app provides an adapter that you can use to provide extra, customized data about a workspace.
The default workspace adapter provided by the app is :class:`~anvil_consortium_manager.adapters.default.DefaultWorkspaceAdapter`.
The default ``workspace_data_model`` specified in this adapter has no fields other than those provided by :class:`~anvil_consortium_manager.models.BaseWorkspaceData`.
This section describes how to store additional information about a workspace by setting up a custom adapter.

First, you will need to define a new model with the additional fields.
It must inherit from :class:`~anvil_consortium_manager.models.BaseWorkspaceData`, which provides a one-to-one field called ``workspace`` to the :class:`~anvil_consortium_manager.models.Workspace` model.

.. code-block:: python

    from django.db import models
    from anvil_consortium_manager.models import BaseWorkspaceData

    class CustomWorkspaceData(BaseWorkspaceData):
        study_name = models.CharField(max_length=255)
        consent_code = models.CharField(max_length=16)

You must also define a form containing the additional fields. You must include the ``workspace`` field, which will automatically be linked to the new :class:`~anvil_consortium_manager.models.Workspace` when creating or importing a workspace.

.. code-block:: python

    from django.forms import ModelForm
    from models import CustomWorkspaceData

    class CustomWorkspaceDataForm(ModelForm):
        class Meta:
            model = CustomWorkspaceData
            fields = ("study_name", "consent_code", workspace")


Optionally, you can define a new ``django-tables2`` table to use in place of the default ``WorkspaceStaffTable`` that comes with the app.
This is helpful if you would like to display fields from your custom workspace data model in the :class:`~anvil_consortium_manager.models.Workspace` list view.
This table will need to operate on the :class:`~anvil_consortium_manager.models.Workspace` model, but it can include fields from your custom workspace data model.
If you do not want to define a custom table, you can use the default table provided by the app: :class:`anvil_consortium_manager.tables.WorkspaceStaffTable`.

.. code-block:: python

    import django_tables2 as tables
    from anvil_consortium_manager import models as acm_models

    class CustomWorkspaceDataTable(tables.Table):
        name = tables.columns.Column(linkify=True)
        class Meta:
            model = acm_models.Workspace
            fields = ("customworkspacedata__study_name", "workspacedata__consent_code", "name")


Next, set up the adapter by subclassing :class:`~anvil_consortium_manager.adapter.BaseWorkspaceAdapter`. You will need to set:

* ``name``: a human-readable name for workspaces created with this adapater (e.g., ``"Custom workspace"``). This will be used when displaying information about workspaces created with this adapter.
* ``type``: a string indicating the workspace type (e.g., ``"custom"``). This will be stored in the ``workspace_type`` field of the :class:`anvil_consortium_manager.models.Workspace` model for any workspaces created using the adapter.
* ``description``: a string giving a brief description of the workspace data model. This will be displayed in the :class:`~anvil_consortium_manager.views.WorkspaceLandingPage` view.
* ``workspace_form_class``: the form to use to create an instance of the ``Workspace`` model. The default adapter uses :class:`~anvil_consortium_manager.forms.WorkspaceForm``.
* ``workspace_data_model``: the model used to store additional data about a workspace, subclassed from :class:`~anvil_consortium_manager.models.BaseWorkspaceData`
* ``workspace_data_form_class``: the form to use to create an instance of the ``workspace_data_model``
* ``list_table_class_staff_view``: the table to use to display the list of workspaces for Staff viewers
* ``list_table_class_view``: the table to use to display the list of workspaces for non-Staff Viewers.
* ``workspace_detail_template_name``: the template to use to render the detail of the workspace

You may also override default settings and methods:

- ``get_autocomplete_queryset``: a method to filter a workspace queryset for use in the :class:`~anvil_consortium_manager.views.WorkspaceAutocompleteByType` view. This queryset passed to this method is the workspace data model specified by the adapter, not the `Workspace` model.
- ``get_extra_detail_context_data``: a method to add extra context data to the :class:`~anvil_consortium_manager.views.WorkspaceDetail` view. This method is passed the `Workspace` model, not the workspace data model specified by the adapter.
- ``before_anvil_create``: a method to perform any actions before creating a workspace on AnVIL via the :class:`~anvil_consortium_manager.views.WorkspaceCreate` view.
- ``after_anvil_create``: a method to perform any actions after creating a workspace on AnVIL via the :class:`~anvil_consortium_manager.views.WorkspaceCreate` view.
- ``after_anvil_import``: a method to perform any actions after importing a workspace from AnVIL via the :class:`~anvil_consortium_manager.views.WorkspaceImport` view.

Here is example of the custom adapter for ``my_app`` with the model, form and table defined above.

.. code-block:: python

    from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter
    from anvil_consortium_manager.forms import WorkspaceForm
    from my_app.models import CustomWorkspaceData
    from my_app.forms import CustomWorkspaceDataForm
    from my_app.tables import CustomWorkspaceStaffTable

    class CustomWorkspaceAdapter(BaseWorkspaceAdapter):
        name = "Custom workspace"
        type = "custom"
        description = "Example custom workspace type for demo app"
        list_table_class_staff_view = tables.CustomWorkspaceDataStaffTable
        list_table_class_view = tables.CustomWorkspaceDataUserTable
        workspace_form_class = WorkspaceForm
        workspace_data_model = models.CustomWorkspaceData
        workspace_data_form_class = forms.CustomWorkspaceDataForm
        workspace_detail_template_name = "my_app/custom_workspace_detail.html"

Finally, to tell the app to use this adapter, set ``ANVIL_WORKSPACE_ADAPTERS`` in your settings file, e.g.: ``ANVIL_WORKSPACE_ADAPTERS = ["my_app.adapters.CustomWorkspaceAdapter"]``. You can even define multiple adapters for different types of workspaces, e.g.:

.. code-block:: python

    ANVIL_WORKSPACE_ADAPTERS = [
        "my_app.adapters.FirstWorkspaceAdapter",
        "my_app.adapters.SecondWorkspaceAdapter",
    ]

as long as you have defined both ``FirstWorkspaceAdapter`` and ``SecondWorkspaceAdapter`` in your code.
If you define multiple workspaces, the index page and the navbar that comes with the app will show links for each different type of workspace.

If you would like to display information from the custom workspace data model in the :class:`~anvil_consortium_manager.views.WorkspaceDetail` view, you can include it in the ``workspace_data`` block of the ``workspace_detail.html`` template. For example:

.. code-block:: html

    {% extends "anvil_consortium_manager/workspace_detail.html" %}
    {% block workspace_data %}
    <ul>
      <li>Study name: {{ workspace_data_object.study_name }}</li>
      <li>Consent: {{ workspace_data_object.consent_code }}</li>
    </ul>
    {% endblock workspace_data %}

If custom content is not provided for the ``workspace_data`` block, a default set of information will be displayed: the billing project, the date added, and the date modified.

Customizing the :class:`~anvil_consortium_manager.models.Workspace` form
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Most workspace adapters can set `workspace_data_form` to :class:`~anvil_consortium_manager.forms.WorkspaceForm`.
This will use the default form provided by the app.

If you would like to add a custom form (e.g., to provide custom help text or do additional cleaning on fields), you can set `workspace_data_form` to a custom form.
You must subclass :class:`anvil_consortium_manager.forms.WorkspaceForm`.
If you modify the form `Meta` class, make sure that it also subclasses `WorkspaceForm.Meta`:

.. code-block:: python

    from anvil_consortium_manager.forms import WorkspaceForm

    class CustomWorkspaceForm(WorkspaceForm):

        class Meta(WorkspaceForm.Meta):
            help_texts = {"note": "Custom help for note field."}
