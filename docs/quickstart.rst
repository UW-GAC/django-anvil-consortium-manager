Quick Start
======================================================================

Install
----------------------------------------------------------------------

Install from GitHub:

.. code-block:: bash

    $ pip install git+https://github.com/UW-GAC/django-anvil-consortium-manager.git



Configure
----------------------------------------------------------------------

You will need a service account credentials file that is registered with Terra. XXX Get info from Ben about this.

Required Settings
~~~~~~~~~~~~~~~~~

1. Add ``anvil_consortium_manager`` to your ``INSTALLED_APPS``.

  .. code-block:: python

      INSTALLED_APPS = [
          # ...
          "anvil_consortium_manager",
      ]

  If you would like to use the views and templates provided by the app, then you should also install ``django-tables2`` in your project.

2. Set the ``ANVIL_API_SERVICE_ACCOUNT_FILE`` setting to the path to the service account credentials file.

  .. code-block:: python

      ANVIL_API_SERVICE_ACCOUNT_FILE="/<path>/<to>/<service_account>.json"

  Alternatively, if you would like to browse the app without making any API, just set this to a random string (e.g., ``"foo"``).

3. Set the default account and workspace adapters in your settings file.

  .. code-block:: python

      ANVIL_WORKSPACE_ADAPTERS = ["anvil_consortium_manager.adapters.default.DefaultWorkspaceAdapter"]
      ANVIL_ACCOUNT_ADAPTER = "anvil_consortium_manager.adapters.default.DefaultAccountAdapter"

  See the :ref:`Advanced Usage` section for information about customizing Accounts and Workspaces.
  Note that you can have multiple Workspace adapters, but only one Account adapter.


4. If you would like to use the templates provided with the app, add the ``"anvil_consortium_manager.context_processors.workspace_adapter"`` context processor to your settings file. This allows the templates to know about which types of workspace adapters that are registered (step 3), and then display links to the correct URLs.

5. Add account linking settings to your settings file.

  .. code-block:: python

      # Specify the URL name that AccountLink and AccountLinkVerify redirect to.
      ANVIL_ACCOUNT_LINK_REDIRECT = "home"
      # Specify the subject for AnVIL account verification emails.
      ANVIL_ACCOUNT_LINK_EMAIL_SUBJECT = "Verify your AnVIL account email"


Optional settings
~~~~~~~~~~~~~~~~~
If you would like to receive emails when a user links their account, set the ``ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL`` setting in your settings file.

  .. code-block:: python

      ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL = "to@example.com"


Permissions
~~~~~~~~~~~

The app provides three different permissions settings.

1. ``anvil_project_manager_view`` - users with this permission can view information, for example lists of users or workspace details.

2. ``anvil_project_manager_edit`` - users with this permission can add, delete, or edit models, for example import an account from AnVIL or create a workspace.

3. ``anvil_project_manager_account_link`` - users with this permission can link their AnVIL accounts in the app using the `AccountLink` and `AccountLinkVerify` views.

We suggest creating three groups, viewers (with ``anvil_project_manager_view`` permission), editors (with both ``anvil_project_manager_view`` and ``anvil_project_manager_edit`` permission), and a final group for users who are allowed to link their AnVIL account. Users can then be added to the appropriate group. Note that users with edit permission but not view permission will not be able to see lists or detail pages, so anyone granted edit permission should also be granted view permission.
