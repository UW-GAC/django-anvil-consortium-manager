.. _auditing:

Auditing information in the app
===============================

The :mod:`~anvil_consortium_manager.auditor` app provides functionality to audit information stored in the app against what is actually on AnVIL.
It uses caching to speed up the audits, so that it does not have to make a request to AnVIL every time you review audit results.
Note that the app does not automatically run audits, so you will need to run them manually via the provided views or set up a scheduled job to run the provided management command (see :ref:`run_anvil_audit`).


Audit results classes
---------------------

Results from an audit are returned as an object that is a subclass of :class:`~anvil_consortium_manager.auditor.audit.base.AnVILAudit`.
The subclasses have a method :meth:`~anvil_consortium_manager.auditor.audit.base.AnVILAudit.ok` that indicates if the audit was successful or if any errors were detected.
It also can list the set of model instances in the app that were audited against AnVIL using  :meth:`~anvil_consortium_manager.auditor.audit.base.AnVILAudit.get_verified_results`;
a dictionary of model instances with detected errors and the errors themselves using :meth:`~anvil_consortium_manager.auditor.audit.base.AnVILAudit.get_error_results`;
and the set of records that exist on AnVIL but are not in the app using :meth:`~anvil_consortium_manager.auditor.audit.base.AnVILAudit.get_not_in_app_results`;
and any "not in app" records that have been marked as ignored :meth:`~anvil_consortium_manager.auditor.audit.base.AnVILAudit.get_ignored_results`.

Audits for different models check different things and will report different potential errors.


Model-specific auditing
-----------------------

Billing project auditing
~~~~~~~~~~~~~~~~~~~~~~~~

The :class:`~anvil_consortium_manager.auditor.audit.billing_projects.BillingProjectAudit` class can be used to audit all :class:`~anvil_consortium_manager.models.BillingProject` model instances in the app. It runs the following checks:

    1. All :class:`~anvil_consortium_manager.models.BillingProject` model instances in the app also exist on AnVIL.

It does not check if there are Billing Projects on AnVIL that don't have a record in the app.


Account auditing
~~~~~~~~~~~~~~~~

The :class:`~anvil_consortium_manager.auditor.audit.accounts.AccountAudit` class can be used to audit all :class:`~anvil_consortium_manager.models.Account` model instances in the app. It runs the following checks:

    1. All :class:`~anvil_consortium_manager.models.Account` model instances in the app also exist on AnVIL.

It does not check if there are Accounts on AnVIL that don't have a record in the app, since this is expected to be the case.

Managed Group auditing
~~~~~~~~~~~~~~~~~~~~~~

The :class:`~anvil_consortium_manager.auditor.audit.managed_groups.ManagedGroupAudit` class can be used to audit all :class:`~anvil_consortium_manager.models.ManagedGroup` model instances in the app. It runs the following checks:

    1. All :class:`~anvil_consortium_manager.models.ManagedGroup` model instances in the app also exist on AnVIL.
    2. The service account running the app has the same role (admin vs member) in the app as on AnVIL.
    3. The membership of each group in the app matches the membership on AnVIL (by running an :class:`~anvil_consortium_manager.auditor.audit.managed_groups.ManagedGroupMembershipAudit` audit for each ManagedGroup).
    4. No groups that have the app service account as an Admin exist on AnVIL.

Membership auditing for a single group can be done using the :class:`~anvil_consortium_manager.auditor.audit.managed_groups.ManagedGroupMembershipAudit` class. This class performs the following checks:

    1. All account members of this :class:`~anvil_consortium_manager.models.ManagedGroup` in the app are also members in AnVIL.
    2. All account admin of this :class:`~anvil_consortium_manager.models.ManagedGroup` in the app are also admin in AnVIL.
    3. All group members of this :class:`~anvil_consortium_manager.models.ManagedGroup` in the app are also members in AnVIL.
    4. All group admin of this :class:`~anvil_consortium_manager.models.ManagedGroup` in the app are also admin in AnVIL.
    5. All admin in AnVIL are also recorded in the app.
    6. All members in AnVIL are also recorded in the app.


If desired, specific membership records can be ignored by creating an :class:`~anvil_consortium_manager.auditor.models.IgnoredManagedGroupMembership` instance in the app.
Ignored records will be included in the audit results, but will not be considered errors.


Workspace auditing
~~~~~~~~~~~~~~~~~~

The :class:`~anvil_consortium_manager.auditor.audit.workspaces.WorkspaceAudit` class can be used to audit all :class:`~anvil_consortium_manager.models.Workspace` model instances in the app. It runs the following checks:

    1. All :class:`~anvil_consortium_manager.models.Workspace` model instances in the app also exist on AnVIL.
    2. The service account running the app is an owner on AnVIL of all the :class:`~anvil_consortium_manager.models.Workspace` model instances.
    3. The :class:`~anvil_consortium_manager.models.Workspace` has the same authorization domains in the app as on AnVIL.
    4. The access to each :class:`~anvil_consortium_manager.models.Workspace` in the app matches the access on AnVIL (by running an :class:`~anvil_consortium_manager.auditor.audit.workspaces.WorkspaceSharingAudit` audit for each Workspace).
    5. No workspaces that have the app service account as an owner exist on AnVIL.
    6. The workspace ``is_locked`` status matches AnVIL.
    7. The workspace ``is_requester_pays`` status matches AnVIL.

Sharing for a workspace can be audited using the :class:`~anvil_consortium_manager.auditor.audit.workspaces.WorkspaceSharingAudit` class. This class performs the following checks:

    1. All groups that have access in the app also have access in AnVIL.
    2. Each :class:`~anvil_consortium_manager.models.ManagedGroup` that has access in the app has the same access in AnVIL.
    3. The :attr:`~anvil_consortium_manager.models.WorkspaceGroupSharing.can_compute` value is the same in the app and on AnVIL.
    4. The ``can_share`` value is as expected on AnVIL based on the group's ``role``.
    5. No groups or accounts on AnVIL have access to the workspace that are not recorded in the app.


Running audits
--------------

Auditing views
~~~~~~~~~~~~~~

The app provides a number of views to assist with auditing information in the app against AnVIL.

These views are accessible from the default navbar, and can be used to review audit results:

    - :class:`~anvil_consortium_manager.auditor.views.BillingProjectAuditReview` (accessible from default navbar)
    - :class:`~anvil_consortium_manager.views.auditor.accounts.AccountAuditReview` (accessible from default navbar)
    - :class:`~anvil_consortium_manager.views.auditor.managed_groups.ManagedGroupAuditReview` (accessible from default navbar)
    - :class:`~anvil_consortium_manager.views.auditor.workspaces.WorkspaceAuditReview` (accessible from default navbar)

The following views are used to run and cache audits:

    - :class:`~anvil_consortium_manager.auditor.views.BillingProjectAuditRun` (accessible from audit review page)
    - :class:`~anvil_consortium_manager.views.auditor.accounts.AccountAuditRun` (accessible from audit review page)
    - :class:`~anvil_consortium_manager.views.auditor.managed_groups.ManagedGroupAuditRun` (accessible from audit review page)
    - :class:`~anvil_consortium_manager.views.auditor.workspaces.WorkspaceAuditRun` (accessible from audit review page)

Workspaces and ManagedGroups have additional audit views that can audit the sharing and membership, respectively.

- :class:`~anvil_consortium_manager.models.ManagedGroup` membership:

    - Reviewing audits: :class:`~anvil_consortium_manager.auditor.views.ManagedGroupMembershipAuditReview` (accessible from Managed Group detail page)
    - Running audits: :class:`~anvil_consortium_manager.auditor.views.ManagedGroupMembershipAuditRun` (accessible from the audit review page)
- :class:`~anvil_consortium_manager.models.Workspace` sharing:

    - Reviewing audits: :class:`~anvil_consortium_manager.auditor.views.WorkspaceSharingAuditReview` (accessible from the Workspace detail page)
    - Running audits: :class:`~anvil_consortium_manager.auditor.views.WorkspaceSharingAuditRun` (accessible from the audit review page)


.. _run_anvil_audit:
Auditing via management command
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The app also provides a management command (``run_anvil_audit``) that can run audits, (optionally) cache results, and (optionally) send an email report.
This command can be used to run audits on a regular schedule, e.g., weekly audits via a cron job.

Here are some examples of calling this command:

.. code-block:: bash

    # To audit all models and print a report to the terminal.
    python manage.py run_anvil_audit

    # To audit all models and send an email report to test@example.com.
    python manage.py run_anvil_audit --email test@example.com

    # To audit just the BillingProject and Account models.
    python manage.py run_anvil_audit --models BillingProject Account

    # To cache the results for later viewing.
    python manage.py run_anvil_audit --cache

More information can be found in the help for ``run_anvil_audit``.

.. code-block:: bash

    # To audit all models and print a report to the terminal.
    python manage.py run_anvil_audit --help
