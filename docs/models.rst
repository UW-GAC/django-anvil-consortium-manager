Model overview
======================================================================

In addition to their representation in the Django database, most models have methods that interact with AnVIL (e.g., by creating, delete, or updating the resource on AnVIL).

Accounts
----------------------------------------------------------------------

The :class:`~anvil_consortium_manager.models.Account` model represents an account on AnVIL, either for a user or for a service account. The difference is specified by a flag (``is_service_account``).

Creating an account in the shell
~~~~~~

.. code-block:: pycon

    >>> from anvil_consortium_manager.models import Account
    >>> a = Account(email="my_test_email@example.com", is_service_account=False)
    >>> a
    [<Account: my_test_email@example.com>]

Check if the account exists on AnVIL by making an API call. This prints out info about the request and response, plus
the boolean indicator of whether the account exists.
In this case, there is no account with this email on AnVIL and we probably don't want to save this :class:`~anvil_consortium_manager.models.Account` instance to the database.

.. code-block:: pycon

    >>> account.anvil_exists()
    INFO 2022-06-14 15:55:22,348 anvil_api 45651 4309271936 Starting request...
      GET: https://api.firecloud.org/api/proxyGroup/my_test_email@example.com
      args: ()
      kwargs: {}
    INFO 2022-06-14 15:55:22,728 anvil_api 45651 4309271936 Got response...
      status_code: 404
      text:
    [False]

For a valid account, the ``anvil_exists`` method returns ``True``:

.. code-block:: pycon

    >>> Account(email="foo@bar.com", is_service_account=False).anvil_exists()
    INFO 2022-06-14 16:17:36,437 anvil_api 46197 4298622336 Starting request...
      GET: https://api.firecloud.org/api/proxyGroup/foo@bar.com
      args: ()
      kwargs: {}
    INFO 2022-06-14 16:17:36,553 anvil_api 46197 4298622336 Got response...
      status_code: 200
      text: "PROXY_255425713192032057941@firecloud.org"
    [True]


By default, the :attr:`~anvil_consortium_manager.models.Account.status` field of an :class:`~anvil_consortium_manager.models.Account` is set to active (:attr:`anvil_consortium_manager.models.Account.STATUS_ACTIVE`).
The status can be changed to inactive (:attr:`anvil_consortium_manager.models.Account.STATUS_INACTIVE`) by calling the :meth:`~anvil_consortium_manager.models.Account.deactivate` method on the :class:`~anvil_consortium_manager.models.Account` instance.
This will keep the record of all :class:`~anvil_consortium_manager.models.ManagedGroup`\ s that an :class:`~anvil_consortium_manager.models.Account` is part of, but will remove that Account from all groups
on AnVIL.
If the :class:`~anvil_consortium_manager.models.Account` is reactivated (using the :meth:`~anvil_consortium_manager.models.Account.reactivate` method :class:`~anvil_consortium_manager.models.Account`), it will be added back to all previous Managed Groups on AnVIL.
