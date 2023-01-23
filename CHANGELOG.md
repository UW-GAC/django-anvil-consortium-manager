# Change log

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
