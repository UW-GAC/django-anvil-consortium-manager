# Change log

## 0.16.4

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
