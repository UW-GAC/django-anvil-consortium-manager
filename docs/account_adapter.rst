.. _account_adapter:

The Account adapter
===================

The app provides an adapter that you can use to customize behavior for Accounts.
You can override this setting by specifying the ``ANVIL_ACCOUNT_ADAPTER`` setting in your ``settings.py`` file.
By default, the app uses :class:`~anvil_consortium_manager.adapters.default.DefaultAccountAdapter`, e.g.,:

.. code-block:: python

        ANVIL_ACCOUNT_ADAPTER = "anvil_consortium_manager.adapters.default.DefaultAccountAdapter"

To customize app behavior for accounts, you must subclass :class:`~anvil_consortium_manager.adapters.account.BaseAccountAdapter`
and set the following attributes:

- ``list_table_class``: an attribute set to the class of the table used to display accounts in the :class:`~anvil_consortium_manager.views.AccountList` view. The default adapter uses :class:`anvil_consortium_manager.tables.AccountStaffTable`.
- ``list_filterset_class``: an attribute set to the class of the table used to filter accounts in the :class:`~anvil_consortium_manager.views.AccountList` view. The default adapter uses :class:`anvil_consortium_manager.filters.AccountListFilter`. This must subclass ``FilterSet`` from `django-filter <https://django-filter.readthedocs.io/en/stable/>`_.

The following attributes have defaults, but can be overridden:


- ``account_link_email_subject``: Subject line for AnVIL account verification emails. (Default: ``"Verify your AnVIL account email"``)
- ``account_link_email_template``: The path to account verification email template. (Default: ``anvil_consortium_manager/account_verification_email.html``)
- ``account_link_verify_message``: Message to display after a user has successfully linked their AnVIL account. (Default: ``"Thank you for linking your AnVIL account."``)
- ``account_link_redirect``: The URL to redirect to after a user has successfully linked their AnVIL account. (Default: ``settings.LOGIN_REDIRECT_URL``)
- ``account_verification_notification_email``: Email address to send an email to after a user verifies an account. If ``None``, no email will be sent. (Default: ``None``)
- ``account_verification_notification_template``: The path to the template for the account verification notification email. (Default: ``anvil_consortium_manager/account_verification_notification_email.html``)

Optionally, you can override the following methods:

- ``get_autocomplete_queryset(self, queryset, q)``: a method that allows the user to provide custom filtering for the autocomplete view. By default, this filters to Accounts whose email contains the case-insensitive search string in ``q``.
- ``get_autocomplete_label(self, account)``: a method that allows the user to set the label for an account shown in forms using the autocomplete widget.
- ``after_account_verification(self, account)``: a method to perform any custom actions after an account is successfully linked. If an exception is raised by this method, account linking will still continue and site admins will be notified via email.
- ``get_account_verification_notification_context(self, account)``: a method to provide custom context data for the account verification notification email. This method is passed the ``account`` object and should return a dictionary of context data.
- ``send_account_verification_notification_email(self, account)``: a method to send an email to the address specified in ``account_verification_notification_email``. By default, this method calls the ``get_account_verification_notification_context`` method to get the context data for the email and sends an email to the address specified by ``account_verification_notification_email`` (if set). If an exception is raised by this method, account linking will still continue and site admins will be notified via email.
