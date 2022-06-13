Model overview
======================================================================

In addition to their representation in the Django database, most models have methods that interact with AnVIL (e.g., by creating, delete, or updating the resource on AnVIL).

Accounts
----------------------------------------------------------------------

This model represents an account on AnVIL, either for a user or for a service account. The difference is specified by a flag (``is_service_account``).
