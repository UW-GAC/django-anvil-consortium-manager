# Change log

## 0.34.0 (2026-12-21)

* Add support for Django 5.2.
* Allow `ManagedGroups` to be filtered by whether or not they are used as an auth domain for a workspace
* Add a base template for listing objects (`__object_list.html`)
* Show filter form in list views in a collapsible accordion
* Show an alert on the `WorkspaceSharingAuditReview` and `ManagedGroupMembershipAuditReview` views if an error is found in the audit result for the workspace or group, respectively. Such errors could indicate that the sharing or membership audits could be incorrect.
* Add a new mixin for use with workspace adapters (`WorkspaceSharingAdapterMixin`) that will automatically share a workspace upon creation or import with a set of specified groups
* Add a new mixin for use with managed group adapters (`GroupGroupMembershipAdapterMixin`) that will automatically add members to any Managed Group that is created
* Update `ManagedGroupCreate`, `WorkspaceCreate`, `WorkspaceImport`, and `WorkspaceClone` views ot handle adapter exceptions:
    -  log any exceptions in `before_anvil_create`, `after_anvil_create`, or `after_anvil_import` adapter methods
    - show the user a message if an exception occurs
* Break advanced docs into its own TOC and sub-section source documents
* Reduce the number of defined test adapters in favor of mocking in tests
* Fix `convert_mariadb_uuid_fields` command to also convert historical models.
* Bugfix: `Workspace.is_shared_with_group` did not correctly check if a workspace was shared directly with a group instead of one of its parents

## 0.33.0 (2025-08-04)

* Implement new `anvil_api` method `get_billing_projects` to get a list of billing projects for the user
* Update `BillingProjectImport` to use the billing project list to provide a dropdown of choices available to import
* Allow the app to manage workspaces where it is an owner but does not have access (e.g., due to auth domain membership).
* Rework methods for determining access to workspaces.
    * Add `Workspace.has_account_in_authorization_domain()`, `Workspace.is_shared_with_account()`, `Workspace.is_accessible_by_account()` methods to determine access to a workspace for an account.
    * Add `Workspace.has_group_in_authorization_domain()`, `Workspace.is_shared_with_group()` methods to determine access to a workspace for an group. Note that there is no corresponding check for overall group access.
    * Remove old `Workspace` methods used for determining workspace access: `is_in_authorization_domain`, `is_shared`.
    * Remove old `ManagedGroup` methods used for determining workspace access: `is_in_authorization_domain`, `is_shared`, `has_access`.
    * Remove old `Account` methods used for determine workspace access: `get_accessible_workspaces`, `has_workspace_access`.

## 0.32.0 (2025-07-01)

* Implement audit result caching. Users should set the `ANVIL_AUDIT_CACHE` setting and set an appropriate backend.
    * Audit views have been split into "run" and "review" views. The "run" view runs the audit and caches the results, while the "review" view displays the cached results.
    * The `run_anvil_audit` management command can optionally cache the results if called with the `--cache-results` flag.
* Typo fixes

## 0.31.0 (2025-06-03)

* Add a new to update workspace requester pays status on AnVIL. Note that this removes the "is_requester_pays" field from the `WorkspaceForm`, since updates are now handled via the new `WorkspaceUpdateRequesterPays` view.

## 0.30.1 (2025-03-07)

* Only make additional API calls in `WorkspaceAudit.run_audit` if the app is an owner of the workspace.

## 0.30.0 (2025-03-04)

* Add ability to customize account verification notification emails.
* Restructure `AccountLinkVerify` such that account verification notification emails are sent after custom actions defined in `after_account_link_verify`.
* Restructure attribute and method names for `AccountAdapter` to be more consistent. Deprecation warnings have been added.
    * Rename `BaseAccountAdapter.account_verify_notification_email` to `BaseAccountAdapter.account_verification_notification_email`.
    * Rename `BaseAccountAdapter.after_account_link_verify` to `BaseAccountAdapter.after_account_verification`.
    * Rename `BaseAccountAdapter.account_verification_email_template` to `BaseAccountAdapter.account_link_email_template`.
    * Rename `BaseAccountAdapter.account_verification_notify_email_template` to `BaseAccountAdapter.account_verification_notification_template`.
    * Change `after_account_verification` to operate on an Account instead of a user.
    * Add type and value checking on `account` in `after_account_verification`.


## 0.29.0 (2025-03-26)

* Allow users to ignore a specific WorkspaceSharingAudit "not in app" record.
* Update for changes in plotly 6.0.0.
* Fix docs build on readthedocs, which has been broken since ~0.20.
* Add a new `AccountAdapter` method (`after_account_link_verify`) that allows a site to perform custom actions after a user links their AnVIL account.

## 0.28.0 (2025-01-06)

* Restructure audits by moving them to their own sub-app (`anvil_consortium_manager.auditor`)
* Allow users to ignore a specific ManagedGroupMembershipAudit "not in app" record

## 0.27.0 (2024-12-06)

* Allow a user to link an Account that is not or has never been linked to another user.

## 0.26.1 (2024-12-02)

* Bugfix: `run_anvil_audit` now raises a `CommandException` if an API call fails.
* Bugfix: use the workspace form specified in the workspace adapter when cloning a workspace.

## 0.26.0 (2024-11-08)

* Move most account settings into the Account adapter
* Allow the user to set a custom success message to be displayed after they verify an AnVIL account
* Move the setting to specify the template for account link verification emails into the AccountAdapter
* Allow users to specify the template for the WorkspaceListByType view in the WorkspaceAdapter

## 0.25.0 (2024-08-07)

* Add an adapter for ManagedGroups that lets the user set the table class to display as well as an `after_anvil_create` method.
* Add model class checks to adapter methods where appropriate.
* Drop support for MariaDB 10.4.
* Drop support for Python 3.8.
* Add a new `extra_pills` block to the workspace detail template, which allows users to add additional pills/badges to the workspace detail page for a given workspace type.


## 0.24.0 (2024-07-03)

* Add AccountUserArchive model to the admin interface.
* Drop support for Django 3.2.
* Add support for Django 5.0.
* Add `convert_mariadb_uuid_fields` command to convert UUID fields for MariaDB 10.7+ and Django 5.0+. See the documentation of this command for more information.
* Move app settings to their own file, and set defaults for some settings.
* Add additional customization for WorkspaceAdapters. Users can override the `before_anvil_create`, `after_anvil_create`, and `after_anvil_import` methods to run custom code before or after creating or after importing a workspace.

## 0.23.0 (2024-05-31)

* Do not track previous groups for inactive accounts.
* Add an audit error if any group membership records exist for inactive accounts.
* Add the ability to unlink a user from an account.

## 0.22.1 (2024-05-22)

* Maintenance: specify different numpy version requirement for python 3.12.

## 0.22.0 (2024-03-11)

* Add customizeable `get_extra_detail_context_data` method for workspace adapters. Users can override this method to provide additional context data on a workspace detail page.
* Add filtering by workspace type to the admin interface.
* Set max_length for `ManagedGroup` and `Workspace` models to match what AnVIL allows.
* Track requester pays status for `Workspace` objects.

## 0.21.0 (2023-12-04)

* Add docs dependencies to hatch via pyproject.toml.
* Add requests as a direct dependency instead of as an extra to google-auth.
* Rename existing tables to include "Staff" in the name, in preparation for adding tables that are viewable by non-staff users.
* Rename the `list_table_class` property of Workspace adapters to `list_table_class_staff_view`.
* Add a new required `list_table_class_view` property to Workspace adapters. This table will be shown to users with anvil_consortium_manager_view permission, and `list_table_class_staff_view` will be shown to users with anvil_consortium_manager_staff_view permission.
* Allow users with anvil_consortium_manager_view permission to see the `WorkspaceDetail`, `WorkspaceList`, `WorkspaceListByType`, and `WorkspaceLanding` views.

## 0.20.1 (2023-11-09)

* Bugfix: Fix `WorkspaceClone` and `WorkspaceImport` views to work with a `WorkspaceData` model that has a second foreign key to `Workspace`.

## 0.20 (2023-11-08)

* Switch to using `pyproject.toml` where possible.
* Use hatch for backend building.
* Rename permissions and associated auth mixins.
    - anvil_project_manager_edit -> anvil_consortium_manager_staff_edit
    - anvil_project_manager_view -> anvil_consortium_manager_staff_view
    - anvil_project_manager_limited_view -> anvil_consortium_manager_view
    - `AnVILConsortiumManagerEditRequired` -> `AnVILConsortiumManagerStaffEditRequired`
    - `AnVILConsortiumManagerViewRequired` -> `AnVILConsortiumManagerStaffViewRequired`
    - `AnVILConsortiumManagerLimitedViewRequired` -> `AnVILConsortiumManagerViewRequired`
* Bugfix: Allow Workspace Data objects to have a second foreign key to `Workspace`.
* Remove ACM Home link from navbar.

## 0.19 (2023-10-27)

* Add filtering in list views.
* Bugfix: Print the correct number of "ok" instances in audit emails. 0.18 introduced a bug where the email included "0 instance(s) verified even if there was more than one verified instance.
* Bugfix: ManagedGroupMembershipAudit does not unexpectedly show errors for deactivated accounts that were in the group before they were deactivated.
* Bugfix: ManagedGroupMembershipAudit now raises the correct exception when instantiated with a ManagedGroup that is not managed by the app.
* Bugfix: ManagedGroupAudit does not report missing groups where the app is only a member.
* Bugfix: Allow groups not managed by the app to be added as child groups of another group, and allow workspaces to be shared with them.

## 0.18 (2023-10-03)

* Include a workspace_data_object context variable for the `WorkspaceDetail` and `WorkspaceUpdate` views.
* Refactor auditing classes.
* Add ability to specify a custom `Workspace` form in the workspace adapter.
* Add informational text to tables on Detail pages.
* Add a new "Limited view" permission. This permission is not yet used anywhere in the app, but can be used by projects using the app (e.g., to show a custom page to users with this permission).

## 0.17 (2023-07-11)

* Import ManagedGroup membership from AnVIL when importing a ManagedGroup and the members already have records in the app.
* Sort available workspaces alphabetically in the `WorkspaceImport` view.
* Synchronize dropdown items in navbar and links in cards on home page.

## 0.16.4 (2023-06-16)

* Bugfix: Move autocomplete query if statement to adapter methods so that adapter methods can handle forwarded values even when a query is not passed. `get_autocomplete_queryset` methods should be updated to process the query parameter.

## 0.16.3 (2023-06-13)

* Bugfix: Fix failing ManagedGroup.anvil_audit_membership when a group is both a member of and admin of another group.

## 0.16.2 (2023-06-12)

* Bugfix: Display "not in app" table correctly in emailed AnVIL audit report.

## 0.16.1 (2023-06-09)

* Bugfix: correctly import AnVIL groups when the service account is both a member and an admin of the group.
* Bugfix: Fix failing ManagedGroup.anvil_audit_memership when the service account is not directly an admin of the group (but is via membership in another group).

## 0.16 (2023-06-01)

* The `run_anvil_audit` management command now sends html emails instead of only text emails.
* Move view mixins to their own source file (`viewmixins.py`).

## 0.15 (2023-04-18)

- Add a new permission, `anvil_consortium_manager_account_link`, which is required for a user to be able to link their AnVIL account.
- Handle groups that the app service account is not part of when auditing ManagedGroups.
- Add information about deactivating and reactivating Accounts to documentation user guide.
- Sort workspaces by name in the WorkspaceTable.
- Remove billing project from the workspace name in WorkspaceTable, since it has its own column already.
- Add a view to autocomplete by workspace type.

## 0.14 (2023-03-23)

- Track whether an AnVIL workspace is locked or not.
- Add a new workspace landing page showing the registered workspace types.
- Move workspace type links from the navbar to a new workspace landing page, because the navbar gets unwieldy when there are large number of registered workspace types.
- Add a new required "description" field for Workspace adapters.

## 0.13 (2023-03-03)

- Bugfix: require records with `access=OWNER` to have `can_compute=True` for `WorkspaceGroupSharing` objects.
- Add information about deleting GroupAccountMembership, GrooupGroupMembership, and WorkspaceGroupSharing records to the documentation User guide.
- Add the `run_anvil_audit` management command to run AnVIL audits.

## 0.12.1 (2023-02-16)

- Add form Mixin class that adds select2-bootstrap-5-theme to form media.

## 0.12 (2023-02-13)

- Support Django 4.1.*.
- Fix broken links in group membership detail pages.
- Add last update date to GroupGroupMembership, GroupAccountMembership, and WorkspaceGroupSharing tables.
- Load workspace data form media in workspace editing templates.
- Bugfix: Accessible workspaces for an account only includes workspaces that are shared with groups they are in.
- Add a view to show a graph-based visualization of ManagedGroups.
- Show a graph-based visualization of group relationships in the ManagedGroupDetail view.

## 0.11 (2023-01-24)

- Copy notebooks when cloning a workspace.
- Links to workspaces on AnVIL open in a new tab.
- Prevent users from linking a Google service account to their user account.
- When importing a workspace, create `WorkspaceGroupSharing` records if the workspace is shared with a group and that group is already in the app.

## 0.10 (2023-01-23)

- Update `anvil_api` to use Rawls and Sam APIs for most API calls. These APIs were recommended over the Firecloud API by Terra support.
- Modify `AnVILAPIMockTestMixin` to use the `responses.RequestMock` object instead of just adding to `responses`.
- In tests, require that all registered requests are actually requested.
- Add a default `__str__` method to `BaseWorkspaceData`.
- Add a django-simple-history `history` field to `BaseWorkspaceData`. Any model inheriting from `BaseWorkspaceData` to have history, which is consistent with other models in the app.
- Add the `Account.get_accessible_workspaces` method.
- Show the workspaces accessible to an Account in the `AccountDetail` view.

## 0.9 (2023-01-09)

- Bug fix: Do not allow `ManagedGroup` or `Workspace` instances to be deleted if referenced in another model by a protected foreign key.
- Add a customizable adapter for `Accounts`. This requires setting the `ANVIL_ACCOUNT_ADAPTER` setting in your settings file.
- Various UI updates: the detail box on object detail pages now uses a description list instead of an unordered list.

## 0.8 (2022-12-27)

- Change `Workspace` link on AnVIL to use `anvil.terra.bio` instead of `app.terra.bio`
- Add ability to send a notification email when a user links their AnVIL account.
- Display the linked user in the `AccountTable` table.
- Show a link to the linked user on the `AccountDetail` page.

## 0.7 (2022-12-07)

- Add ability to clone a workspace on AnVIL.

## 0.6 (2022-11-29)

- Add ability to update `BillingProject`, `Account`, `ManagedGroup`, and `Workspace`, and workspace data models.
- Add an extendable __object_detail.html template intended to be used by object detail templates.

## 0.5 (2022-11-22)

- Add an optional note field to the  `BillingProject`, `Account`, `ManagedGroup`, and `Workspace` models.
- Add a user guide to the documentation.

## 0.4 (2022-11-09)

- Only show links to views requiring edit permission if the user has that permission.
- Add a get_absolute_url method for `WorkspaceData` which returns the absolute url of the associated workspace.
- Add a required "workspace_detail_template_name" field for workspace adapters.
- Add Workspace and ManagedGroup methods to check whether a group has access to a workspace.
- Rename the `WorkspaceGroupAccess` model to `WorkspaceGroupSharing`, which is more consistent with AnVIL terminology.
- Reword "access" to "sharing" in WorkspaceGroupSharing-related views and templates.
- Add more views for creating WorkspaceGroupSharing, GroupAccountMembership, and GroupGroupMembership objects using url parameters.

## 0.3 (2022-09-27)

- Show groups that a group is part of on the ManagedGroup detail page.
- Add methods and views to audit information against AnVIL.

## 0.2 (2022-09-12)

- Add account linking functionality

## 0.1 (2022-08-31)

- First release
