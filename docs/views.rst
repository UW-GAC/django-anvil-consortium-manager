Views overview
======================================================================

The app provides both views and mixins for use.

Importing an account from AnVIL
----------------------------------------------------------------------

The :class:`anvil_consortium_manager.views.AccountImport` view provides the typical path for getting Account information from AnVIL.
In this view, the user enters the email of the account to import as well as an indicator of whether the account is a service account or a user account.
The view then checks whether the account is a valid AnVIL account by making an API call.
If it is valid, the record is saved in the database.
