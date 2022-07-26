Advanced Usage
==============

The workspace adapter
---------------------

The app provides an adapter that you can use to provide extra, customized data about a workspace.
By default, the app uses :class:`~anvil_consortium_manager.adapter.DefaultWorkspaceAdapter`.
The default ``workspace_data_model`` specified in this adapter has no fields other than those provided by :class:`~anvil_consortium_manager.models.AbstractWorkspaceData`.
This section describes how to store additional information about a workspace by setting up a custom adapter.

First, you will need to define a new model with the additional fields.
It must inherit from :class:`~anvil_consortium_manager.models.AbstractWorkspaceData`, which provides a one-to-one field called ``workspace`` to the :class:`~anvil_consortium_manager.models.Workspace` model.

.. code-block:: python

    from django.db import models
    from anvil_consortium_manager.models import AbstractWorkspaceData

    class CustomWorkspaceData(AbstractWorkspaceData):
        study_name = models.CharField(max_length=255)
        consent_code = models.CharField(max_length=16)

You must also define a form containing the additional fields, and excluding the ``workspace`` field.

.. code-block:: python

    from django.forms import ModelForm
    from models import CustomWorkspaceData

    class WorkspaceDataForm(ModelForm):
        class Meta:
            model = CustomWorkspaceData
            fields = ("study_name", "consent_code",)


Optionally, you can define a new ``django-tables2`` table to use in place of the default ``WorkspaceTable`` that comes with the app.
This is helpful if you would like to display fields from your custom workspace data model in the :class:`~anvil_consortium_manager.models.Workspace` list view.
This table will need to operate on the :class:`~anvil_consortium_manager.models.Workspace` model, but it can include fields from your custom workspace data model.
If you do not want to define a custom table, you can use the default table provided by the app: :class:`~anvil_consortium_manager.tables.WorkspaceTable`.

.. code-block:: python

    import django_tables2 as tables
    from anvil_consortium_manager import models as acm_models

    class WorkspaceDataTable(tables.Table):
        name = tables.columns.Column(linkify=True)
        class Meta:
            model = acm_models.Workspace
            fields = ("customworkspacedata__study_name", "workspacedata__consent_code", "name")


Next, set up the adapter by subclassing :class:`~anvil_consortium_manager.adapter.BaseWorkspaceAdapter`. You will need to set:

* ``workspace_data_model``: the model used to store additional data about a workspace, subclassed from :class:`~anvil_consortium_manager.models.AbstractWorkspaceData`
* ``workspace_data_form_class``: the form to use to create an instance of the ``workspace_data_model``
* ``list_table_class``: the table to use to display the list of workspaces

Here is example of the custom adapter for ``my_app`` with the model, form and table defined above.

.. code-block:: python

    from anvil_consortium_manager.adapter import DefaultWorkspaceAdapter
    from my_app.models import CustomWorkspaceData
    from my_app.forms import CustomWorkspaceDataForm
    from my_app.tables import CustomWorkspaceTable

    class CustomWorkspaceAdapter(DefaultWorkspaceAdapter):
        workspace_data_model = models.CustomWorkspaceData
        workspace_data_form_class = forms.CustomWorkspaceDataForm
        list_table_class = tables.CustomWorkspaceTable

Finally, to tell the app to use this adapter, set ``ANVIL_ADAPTER`` in your settings file, e.g.: ``ANVIL_ADAPTER = my_app.adapters.CustomWorkspaceAdapter``

If you would like to display information from the custom workspace data model in the :class:`~anvil_consortium_manager.views.WorkspaceDetail` view, you can include it in the ``workspace_data`` block of the workspace_detail.html template. For example:

.. code-block:: html

    {% extends "anvil_consortium_manager/workspace_detail.html" %}
    {% block workspace_data %}
    <ul>
      <li>Study name: {{ object.customworkspacedata.study_name }}</li>
      <li>Consent: {{ object.customworkspacedata.consent_code }}</li>
    </ul>
    {% endblock workspace_data %}

If custom content is not provided for the ``workspace_data`` block, a default set of information will be displayed: the billing project, the date added, and the date modified.
