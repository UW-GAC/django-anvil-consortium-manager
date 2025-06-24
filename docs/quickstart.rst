Quick Start
======================================================================

Install
----------------------------------------------------------------------

Install from GitHub:

.. code-block:: bash

    $ pip install git+https://github.com/UW-GAC/django-anvil-consortium-manager.git



Configure
----------------------------------------------------------------------

You will need a service account credentials file that is registered with Terra.
See the `Terra service account documentation <https://support.terra.bio/hc/en-us/articles/360031023592-Service-accounts-in-Terra>`_ for more information.

Required Settings
~~~~~~~~~~~~~~~~~

1. Add required apps and ``anvil_consortium_manager`` to your ``INSTALLED_APPS`` setting.

  .. code-block:: python

      INSTALLED_APPS = [
          # The following apps are required:
          "django.contrib.messages",
          "django.contrib.sites",
          "django-tables2",
          "crispy_bootstrap5",  # If you are using the default templates

          # This app:
          "anvil_consortium_manager",
          # The associated app for auditing information against AnVIL (required):
          "anvil_consortium_manager.auditor",
      ]

2. Set the ``ANVIL_API_SERVICE_ACCOUNT_FILE`` setting to the path to the service account credentials file.

  .. code-block:: python

      ANVIL_API_SERVICE_ACCOUNT_FILE="/<path>/<to>/<service_account>.json"

  Alternatively, if you would like to browse the app without making any API, just set this to a random string (e.g., ``"foo"``).

3. Set the ``ANVIL_WORKSPACE_ADAPTERS`` setting in your settings file.

  .. code-block:: python

      ANVIL_WORKSPACE_ADAPTERS = ["anvil_consortium_manager.adapters.default.DefaultWorkspaceAdapter"]

  For more information about customizing the workspace-related behavior of the app, see the :ref:`workspace_adapter` section.

5. Set up a Site in the sites framework. In your settings file:

  .. code-block:: python

      SITE_ID = 1

1. Set up caching. The app uses caching to improve the speed of auditing, so you will want to set your preferred cache backend following Django documentation.

  For example, to use the db-backend cache, add the following to your settings file:

  .. code-block:: python

      CACHES = {
          "default": {
              "BACKEND": "django.core.cache.backends.db.DatabaseCache",
              "LOCATION": "auditor_cache",
          }
      }


Optional settings
~~~~~~~~~~~~~~~~~

These settings are set to default values automatically, but can be changed by the user in the ``settings.py`` file for further customization.

* ``ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL``: Receive an email when a user links their account (default: None)
* ``ANVIL_ACCOUNT_LINK_EMAIL_SUBJECT``: Subject of the email when a user links their account (default: "AnVIL Account Verification")
* ``ANVIL_ACCOUNT_LINK_REDIRECT_URL``: URL to redirect to after linking an account (default: ``settings.LOGIN_REDIRECT_URL``)
* ``ANVIL_ACCOUNT_ADAPTER``: Adapter to use for Accounts (default: ``"anvil_consortium_manager.adapters.default.DefaultAccountAdapter"``). See the :ref:`account_adapter` section for more information about customizing behavior for accounts.


Post-installation
~~~~~~~~~~~~~~~~~

1. In your Django root directory, execute the command below to create your database tables:

  .. code-block:: bash

      python manage.py migrate

2. Start your server and add a site for your domain using the admin interface (e.g. http://localhost:8000/admin/). Make sure ``settings.SITE_ID`` matches the ID for this site.

Permissions
~~~~~~~~~~~

The app provides four different permissions settings.

1. ``anvil_consortium_manager_staff_edit`` - users with this permission can add, delete, or edit models, for example import an account from AnVIL or create a workspace.

2. ``anvil_consortium_manager_staff_view`` - users with this permission can view the full set of information in the app, for example lists of users or workspace details.

3. ``anvil_consortium_manager_account_link`` - users with this permission can link their AnVIL accounts in the app using the `AccountLink` and `AccountLinkVerify` views.

4. ``anvil_consortium_manager_view`` - users with this permission can see a limited set of information from the :class:`~anvil_consortium_manager.views.WorkspaceLandingPage`, :class:`~anvil_consortium_manager.views.WorkspaceList`, :class:`~anvil_consortium_manager.views.WorkspaceListByType`, and :class:`~anvil_consortium_manager.views.WorkspaceDetail` views.

We suggest creating three groups,
staff viewers (with ``anvil_consortium_manager_staff_view`` permission),
staff editors (with both ``anvil_consortium_manager_staff_view`` and ``anvil_consortium_manager_staff_edit`` permission),
a group for users who are allowed to link their AnVIL account (with ``anvil_consortium_manager_account_link`` permission).
Users can then be added to the appropriate group.
Note that users with staff edit permission but not staff view permission will not be able to see lists or detail pages, so anyone granted edit permission should also be granted staff view permission.
