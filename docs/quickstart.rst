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

Settings
~~~~~~~~

Add ``anvil_consortium_manager`` to your ``INSTALLED_APPS``.

.. code-block:: python

    INSTALLED_APPS = [
        # ...
        "anvil_consortium_manager",
    ]


Set the ANVIL_API_SERVICE_ACCOUNT_FILE setting to the path to the service account credentials file.

.. code-block:: python

    ANVIL_API_SERVICE_ACCOUNT_FILE="/<path>/<to>/<service_account>.json"


Permissions
~~~~~~~~~~~

The app provides two different permissions settings.

1. `anvil_project_manager_view` - users with this permission can view information, for example lists of users or workspace details.

2. `anvil_project_manager_edit` - users with this permission can add, delete, or edit models, for example import an account from AnVIL or create a workspace.

We suggest creating two groups, viewers (with `anvil_project_manager_view permission`) and editors (with both `anvil_project_manager_view` and `anvil_project_manager_edit permission`). Users can then be added to the appropriate group. Note that users with edit permission but not view permission will not be able to see lists or detail pages, so both permissions should be granted together.
