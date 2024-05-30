.. _user_guide:

User guide
==========


Create a Managed Group
----------------------

1. Navigate to `Managed Groups -> Add a group`.

2. Type the name of the group to create in the "Name" field.

3. If desired, add any notes about the Managed Group in the "note" field.

4. Click on "Save group". This can take some time due to delays from AnVIL.

If successful, you will be shown a success message and information about the group that you just created.


Import a Billing Project
------------------------

Note that the service account running the website must be added as a user of the billing project that you are trying to import.

1. Navigate to `Billing Projects -> Import a billing project`.

2. In the "name" field, type the name of the billing project to import.

3. If desired, add any notes about the Billing Project in the "note" field.

4. Click on the "Import billing project" button.

If successful, you will be shown a success message and information about the billing project that you just imported.

Create a new workspace
----------------------

1. Navigate to the workspace landing page (`Workspaces -> Workspace types`).

2. On the workspace landing page, find the card for the workspace type you would like to import, and then click on the "Create a workspace on AnVIL" link in that card.

3. In the "Billing project" field, select the billing project in which to create the workspace (e.g., "primed-cc"). If it doesn’t exist, you may need to import a billing project (see instructions).

4. In the "name" field, type the name of the workspace that you would like to create within the selected billing project (e.g., "test-workspace").

5. If applicable, in the "authorization domains" box, select one or more authorization domains for this workspace.

    * You can select multiple authorization domains using Command-click.
    * To de-select an authorization domain, click on it while holding the Command key.

6. If desired, add any notes about the Workspace in the "note" field.

7. Fill out all other required fields for the type of workspace you are creating.

8. Click on the "Save workspace" button. This can take some time due to delays from AnVIL.

If successful, you will be shown a success message and information about the workspace that you just created. The examples would create a workspace named "primed-cc/test-workspace".

Clone an existing workspace
---------------------------

1. Navigate to the workspace detail page that you would like to clone.

2. Click the "Clone workspace" button and then choose the workspace type that you would like to use for the new workspace.

3. In the "Billing project" field, select the billing project in which to create the workspace (e.g., "primed-cc"). If it doesn’t exist, you may need to import a billing project (see instructions).

4. In the "name" field, type the name of the workspace that you would like to create within the selected billing project (e.g., "test-workspace").

5. If applicable, in the "authorization domains" box, select one or more authorization domains for this workspace.

    * You can select multiple authorization domains using Command-click.
    * To de-select an authorization domain, click on it while holding the Command key.
    * You must include all the authorization domains from the workspace you are cloning. The form will be autopopulated with these groups.

6. If desired, add any notes about the Workspace in the "note" field.

7. Fill out all other required fields for the type of workspace you are creating.

8. Click on the "Save workspace" button. This can take some time due to delays from AnVIL.

If successful, you will be shown a success message and information about the workspace that you just created. The examples would create a workspace named "primed-cc/test-workspace".

Import an existing workspace
----------------------------

Note that the service account running the website must be an owner of the workspace (or in a group that has owner permissions) to be able to import it to the app.
If the workspace has any auth domains, they will be imported into the app even if the service account is not an admin of those groups.

1. Navigate to the workspace landing page (`Workspaces -> Workspace types`).

2. On the workspace landing page, find the card for the workspace type you would like to import, and then click on the "Import a workspace from AnVIL" link in that card.

3. From the "Workspace" dropdown, select the workspace you would like to import. Only workspaces where the service account is an owner are shown in this dropdown.

4. Fill out all other required fields for this workspace type.

5. If desired, add any notes about the Workspace in the "note" field.

6. Click on the "Import workspace" button. This can take some time due to delays from AnVIL.

If successful, you will be shown a success message and information about the workspace that you just imported.

Note: if the workspace has auth domain(s), the group(s) used as the auth domain(s) will also be imported into the app as a new ManagedGroup. If the service account running the app is an admin of that group, it will also import some membership records. GroupGroupMembership or GroupAccountMembership records will be created if the Account or ManagedGroup that is listed as a member/admin already exists in the app.

Add a user account to a group
-----------------------------

You can add a user account to a group using three different options.

1. Navigate to `Managed Groups -> Add an account to a group`. This allows you to select both the Managed Group and the Account on one form.
2. Navigate to a Managed Group detail page and click the "Add an account to this group" button. This allows you to select the Account to add to the group.
3. Navigate to a Account detail page and click the "Add this account to a group" button. This allows you to select the Managed Group to add to the Account to.

In any case, once you have arrived at the form using one of the above three methods, follow these instructions to add an account to a group.

1. If applicable, select the Managed Group and/or Account that you would like to add to the group from the Managed Group and Account fields. You can start typing to autocomplete the Managed Group name and Account email.
2. In the Role field, select the role that this Account should have in the Managed Group. Typically, everyone should be added as a "Member".
3. Click on the "Save membership" button. This can take some time due to delays from AnVIL.

If successful, you will be shown a success message.


Remove a user account from a group
----------------------------------

To remove a user account from a group, first navigate to the detail page for that `GroupAccountMembership` record.
There are multiple ways to get to this page:

1. Navigate to the detail page for the `Managed Group`. Click on the "View active accounts in this group" dropdown, then click on the "See details" link next to the Account you'd like to remove.
2. Navigate to the detail page for the `Account`. Click on the "View groups that this account is a member of" dropdown, then click on the "See details" link next to the Group you'd like to remove them from.

Once at the detail page for the `GroupAccountMembership` to delete, click on the "Delete on AnVIL" button. You will be taken to a page to confirm the deletion.

If successful, you will be shown a success message.

Add a group to another group
----------------------------

You can add a user account to a group using three different options.

1. Navigate to `Managed Groups -> Add a group to a group`. This allows you to select both the parent and child Managed Groups on one form.
2. Navigate to a Managed Group detail page and click the "Add a group to this group" button. This allows you to select a child group to add to this group.
3. Navigate to a Managed Group detail page and click the "Add this group to a group" button. This allows you to select the parent Managed Group to add to this group to.

In any case, once you have arrived at the form using one of the above three methods, follow these instructions to add an account to a group.

1. If applicable, select the Parent Group and/or Child Group that you would like to add to the group from the Parent Group and Child Group fields. You can start typing to autocomplete the Parent Group name and Child Group email.
2. In the Role field, select the role that the Child Group should have in the Group. In most cases, everyone should be added as a "Member".
3. Click on the "Save membership" button. This can take some time due to delays from AnVIL.

If successful, you will be shown a success message.

Remove a group from another group
---------------------------------

To remove a child group from a parent group, first navigate to the detail page for that `GroupGroupMembership` record.
There are multiple ways to get to this page:

1. Navigate to the detail page for the parent `ManagedGroup`. Click on the "View groups that are in this group" dropdown, then click on the "See details" link next to the Group you'd like to remove.
2. Navigate to the detail page for the child `ManagedGroup`. Click on the "View groups that this group is in" dropdown, then click on the "See details" link next to the Group you'd like to remove it from.

Once at the detail page for the `GroupGroupMembership` to delete, click on the "Delete on AnVIL" button. You will be taken to a page to confirm the deletion.

If successful, you will be shown a success message.

Share a workspace with a group
------------------------------

You can share a workspace with a group using three different options.

1. Navigate to `Workspaces -> Share a workspace with a group`. This allows you to select both the workspace and the Managed Group on one form.
2. Navigate to a Workspace detail page and click the "Share this workspace with a group" button. This allows you to select the Managed Group with which to share the workspace.
3. Navigate to a Managed Group detail page and click the "Share a workspace with this group" button. This allows you to select the Workspace to share with this group.

In any case, once you have arrived at the form using one of the above three methods, follow these instructions to share the workspace with the group.

1. If applicable, select the Workspace and/or the Managed Group that should have access to that Workspace from the dropdown fields. You can start typing to autocomplete the Workspace and Group name.
2. Select the access level that the Group should have for this workspace. Typically, the access level should be either "Reader" or "Writer".
3. If the Group should have compute access in the workspace, select the "Can compute" box.
4. Click on the "Save access" button. This can take some time due to delays from AnVIL.

If successful, you will be shown a success message.

Stop sharing a workspace with a group
-------------------------------------

To stop sharing a workspace with a group, first navigate to the detail page for that `WorkspaceGroupSharing` record.
There are multiple ways to get to this page:

1. Navigate to the detail page for the `Managed Group`. Click on the "View workspaces shared with this group" dropdown, then click on the "See details" link next to the Workspace you'd like to stop sharing.
2. Navigate to the detail page for the `Workspace`. Click on the "View groups that this workspace is shared with" dropdown, then click on the "See details" link next to the Group you'd like to stop sharing with.

Once at the detail page for the `GroupGroupMembership` to delete, click on the "Delete on AnVIL" button. You will be taken to a page to confirm the deletion.

If successful, you will be shown a success message.


Audit information in the app
----------------------------

For each type of AnVIL resource (Billing Projects, Accounts, Managed Groups, and Workspaces), you can run an audit to compare the information in the app against the information on AnVIL to make sure they match.
For now, you can do this by navigating to a specific page for each type of resource.
Note that this page makes a number of API calls, so you shouldn’t load it too frequently.

* For Billing Projects: `Navigate to Billing projects -> Audit billing projects`
* For Accounts: `Navigate to Accounts -> Audit accounts`
* For Managed Groups: `Navigate to Managed groups -> Audit managed groups`
For workspaces: `Navigate to Workspaces -> Audit workspaces`

The audit page explains more about the audit and what is checked for each type of AnVIL resource.
Also see the :ref:`Auditing` section for more information.


Import an AnVIL account
-----------------------

Typically, consortium users should link their AnVIL accounts instead of having a coordinating center staff member follow these steps.
There are two general cases where staff may wish to import an AnVIL account:

1. A consortium member would like a service account to upload data.
2. The coordinating center would like to give access to non-consortium members, such as allowing AnVIL staff to access a workspace to help troubleshoot an issue.

For those two cases, follow these steps.
Note that the account must already exist on AnVIL to be able to import it.

1. Navigate to `Accounts -> Import an Account`.

2. Type the email of the account in the "email" field.

3. If the account that you are importing is a service account instead of a user account, check the "I service account" box.

4. If desired, add any notes about the Account in the "note" field.

5. Click on "Save account". This can take some time due to delays from AnVIL.

If successful, you will be shown a message and information about the account that you just imported. Otherwise, you will be shown an error message at the top of the page.


Deactivate an account
---------------------

The app provides the ability to deactivate an :class:`~anvil_consortium_manager.models.Account`.
When an Account is deactivated, it is removed from all groups on AnVIL and all :class:`~anvil_consortium_manager.models.GroupAccountMembership`` records for that Account are deleted.
After deactivating, it can no longer be added to new groups unless it is reactivated.

To deactivate an Account, navigate to the Account detail page and click on the "Deactivate account" button.

Reactivate an account
---------------------

Accounts that have been deactivated can be reactivated.
To reactivate an Account, navigate to the Account detail page and click on the "Reactivate account" button.
