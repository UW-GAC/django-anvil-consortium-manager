Views overview
======================================================================

The app provides both views and mixins for use.

Importing an account from AnVIL
----------------------------------------------------------------------

The :class:`~anvil_consortium_manager.views.AccountImport` view provides the typical path for getting :class:`~anvil_consortium_manager.models.Account` information from AnVIL.
In this view, the user enters the email of the account to import as well as an indicator of whether the account is a service account or a user account.
The view then checks whether the account is a valid AnVIL account by making an API call.
If it is valid, the record is saved in the database.


User account linking
----------------------------------------------------------------------

You can also use existing views to allow a user to import and link their own AnVIL :class:`~anvil_consortium_manager.models.Account`.
The :class:`~anvil_consortium_manager.views.AccountLink` view provides a form to create a :class:`~anvil_consortium_manager.models.UserEmailEntry`.
It verifies that the email is associated with an AnVIL account, and sends an email to the that email with a verification link.
The user is then required to click on the verification link to verify their email using :class:`~anvil_consortium_manager.views.AccountLinkVerify`, create an :class:`~anvil_consortium_manager.models.Account`, and link it to their user.

Users must have the `anvil_consortium_manager_account_link` permission to access these views.


AnVIL auditing
----------------------------------------------------------------------

You can audit information in the app against AnVIL using the following views:

    - Billing projects: :class:`anvil_consortium_manager.views.BillingProjectAudit`
    - Accounts: :class:`anvil_consortium_manager.views.AccountAudit`
    - Managed Groups: :class:`anvil_consortium_manager.views.ManagedGroupAudit`
    - Membership of a specific managed group: :class:`anvil_consortium_manager.views.ManagedGroupMembershipAudit`
    - Workspaces: :class:`anvil_consortium_manager.views.WorkspaceAudit`
    - Access to a specific workspace: :class:`anvil_consortium_manager.views.WorkspaceSharingAudit`
