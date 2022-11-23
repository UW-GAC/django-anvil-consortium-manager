.. _user_guide:

User guide
==========


Creating a Managed Group
----------------

1. Navigate to Managed Groups -> Add a group.

2. Type the name of the group to create in the "Name" field.

3. If desired, add any notes about the Managed Group in the "note" field.

4. Click on "Save group". This can take some time due to delays from AnVIL.

If successful, you will be shown a success message and information about the group that you just created.


Importing a Billing Project
---------------------------

Note that the service account running the website must be added as a user of the billing project that you are trying to import.

1. Navigate to `Billing Projects -> Import a billing project`.

2. In the "name" field, type the name of the billing project to import.

3. If desired, add any notes about the Billing Project in the "note" field.

4. Click on the "Import billing project" button.

If successful, you will be shown a success message and information about the billing project that you just imported.

Creating a new workspace
------------------------

1. Navigate to `Workspaces -> Create a new a workspace`. Make sure to select the "Create a new workspace" link under the workspace type that you would like to create.

2. In the "Billing project" field, select the billing project in which to create the workspace (e.g., primed-cc). If it doesn’t exist, you may need to import a billing project (see instructions).

3. In the "name" field, type the name of the workspace that you would like to create within the selected billing project (e.g., test-workspace).

4. If applicable, in the "authorization domains" box, select one or more authorization domains for this workspace.

    * You can select multiple authorization domains using Command-click.
    * To de-select an authorization domain, click on it while holding the Command key.

5. If desired, add any notes about the Workspace in the "note" field.

6. Fill out all other required fields for the type of workspace you are creating.

7. Click on the "Save workspace" button. This can take some time due to delays from AnVIL.

If successful, you will be shown a success message and information about the workspace that you just created. The examples would create a workspace named "primed-cc/test-workspace".

Importing an existing workspace
-------------------------------

Note that the service account running the website must be an owner of the workspace (or in a group that has owner permissions) to be able to import it to the app.
If the workspace has any auth domains, they will be imported into the app even if the service account is not an admin of those groups.

1. Navigate to `Workspaces -> Import a workspace` from AnVIL. Make sure to select the "Create a new workspace" link under the workspace type that you would like to import.

2. From the "Workspace" dropdown, select the workspace you would like to import. Only workspaces where the service account is an owner are shown in this dropdown.

3. Fill out all other required fields for this workspace type.

4. If desired, add any notes about the Workspace in the "note" field.

5. Click on the "Import workspace" button. This can take some time due to delays from AnVIL.

If successful, you will be shown a success message and information about the workspace that you just imported.

Adding a user account to a group
--------------------------------

You can add a user account to a group using three different options.

1. Navigate to `Managed Groups -> Add an account to a group`. This allows you to select both the Managed Group and the Account on one form.
2. Navigate to a Managed Group detail page and click the "Add an account to this group" button. This allows you to select the Account to add to the group.
3. Navigate to a Account detail page and click the "Add this account to a group" button. This allows you to select the Managed Group to add to the Account to.

In any case, once you have arrived at the form using one of the above three methods, follow these instructions to add an account to a group.

1. If applicable, select the Managed Group and/or Account that you would like to add to the group from the Managed Group and Account fields. You can start typing to autocomplete the Managed Group name and Account email.
2. In the Role field, select the role that this Account should have in the Managed Group. Typically, everyone should be added as a "Member".
3. Click on the "Save membership" button. This can take some time due to delays from AnVIL.

If successful, you will be shown a success message.

Adding a group to another group
-------------------------------

You can add a user account to a group using three different options.

1. Navigate to `Managed Groups -> Add a group to a group`. This allows you to select both the parent and child Managed Groups on one form.
2. Navigate to a Managed Group detail page and click the "Add a group to this group" button. This allows you to select a child group to add to this group.
3. Navigate to a Managed Group detail page and click the "Add this group to a group" button. This allows you to select the parent Managed Group to add to this group to.

In any case, once you have arrived at the form using one of the above three methods, follow these instructions to add an account to a group.

1. If applicable, select the Parent Group and/or Child Group that you would like to add to the group from the Parent Group and Child Group fields. You can start typing to autocomplete the Parent Group name and Child Group email.
2. In the Role field, select the role that the Child Group should have in the Group. In most cases, everyone should be added as a "Member".
3. Click on the "Save membership" button. This can take some time due to delays from AnVIL.

If successful, you will be shown a success message.

Sharing a workspace with a group
--------------------------------

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



Auditing information in the app
-------------------------------

For each type of AnVIL resource (Billing Projects, Accounts, Managed Groups, and Workspaces), you can run an audit to compare the information in the app against the information on AnVIL to make sure they match.
For now, you can do this by navigating to a specific page for each type of resource.
Note that this page makes a number of API calls, so you shouldn’t load it too frequently.

* For Billing Projects: `Navigate to Billing projects -> Audit billing projects`
* For Accounts: `Navigate to Accounts -> Audit accounts`
* For Managed Groups: `Navigate to Managed groups -> Audit managed groups`
For workspaces: `Navigate to Workspaces -> Audit workspaces`

The audit page explains more about the audit and what is checked for each type of AnVIL resource.
Also see the :ref:`Auditing` section for more information.


Importing an AnVIL account
--------------------------

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
