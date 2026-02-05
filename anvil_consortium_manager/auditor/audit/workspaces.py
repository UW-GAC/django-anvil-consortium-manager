import django_tables2 as tables

from anvil_consortium_manager.anvil_api import AnVILAPIClient, AnVILAPIError404
from anvil_consortium_manager.exceptions import AnVILNotWorkspaceOwnerError
from anvil_consortium_manager.models import Workspace

from .. import models
from . import base


class WorkspaceAudit(base.AnVILAudit):
    """Class to runs an audit for Workspace instances."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    """Error when a Workspace in the app does not exist on AnVIL."""

    ERROR_NOT_OWNER_ON_ANVIL = "Not an owner on AnVIL"
    """Error when the service account running the app is not an owner of the Workspace on AnVIL."""
    ERROR_IS_OWNER_ON_ANVIL = "Owner on AnVIL"
    """Error when the service account running the app is unexpectedly an owner on AnVIL."""

    ERROR_DIFFERENT_AUTH_DOMAINS = "Has different auth domains on AnVIL"
    """Error when the Workspace has different auth domains in the app and on AnVIL."""

    ERROR_WORKSPACE_SHARING = "Workspace sharing does not match on AnVIL"
    """Error when a Workspace is shared with different ManagedGroups in the app and on AnVIL."""

    ERROR_DIFFERENT_LOCK = "Workspace lock status does not match on AnVIL"
    """Error when the workspace.is_locked status does not match the lock status on AnVIL."""

    ERROR_DIFFERENT_REQUESTER_PAYS = "Workspace bucket requester_pays status does not match on AnVIL"
    """Error when the workspace.is_locked status does not match the lock status on AnVIL."""

    cache_key = "workspace_audit_results"

    def _check_workspace_ownership(self, workspace_details):
        """Check if the service account is an owner of the workspace.

        Args:
            workspace_details (dict): The details of the workspace from AnVIL API.
        """
        if workspace_details["accessLevel"] == "OWNER":
            return True
        elif workspace_details["accessLevel"] == "NO ACCESS":
            # extra acl checks
            try:
                AnVILAPIClient().get_workspace_acl(
                    workspace_details["workspace"]["namespace"],
                    workspace_details["workspace"]["name"],
                )
            except AnVILAPIError404:
                # We don't have permission to check the ACL, so we are not an owner.
                return False
            else:
                # The app can check ACLs, so it is an owner.
                return True
        else:
            return False

    def audit(self, cache=False):
        """Run an audit on Workspaces in the app."""
        # Check the list of workspaces.
        fields = [
            "workspace.namespace",
            "workspace.name",
            "workspace.authorizationDomain",
            "workspace.isLocked",
            "accessLevel",
        ]
        response = AnVILAPIClient().list_workspaces(fields=",".join(fields))
        workspaces_on_anvil = response.json()
        # First check workspaces not managed by the app.
        for workspace in Workspace.objects.filter():
            model_instance_result = base.ModelInstanceResult(workspace)
            try:
                i = next(
                    idx
                    for idx, x in enumerate(workspaces_on_anvil)
                    if (
                        x["workspace"]["name"] == workspace.name
                        and x["workspace"]["namespace"] == workspace.billing_project.name
                    )
                )
            except StopIteration:
                model_instance_result.add_error(self.ERROR_NOT_IN_ANVIL)
            else:
                # Check role.
                workspace_details = workspaces_on_anvil.pop(i)
                if not workspace.is_managed_by_app and self._check_workspace_ownership(workspace_details):
                    # The workspace is not managed by the app, but we are owners on AnVIL.
                    model_instance_result.add_error(self.ERROR_IS_OWNER_ON_ANVIL)
                elif workspace.is_managed_by_app and not self._check_workspace_ownership(workspace_details):
                    # The workspace is managed by the app, but we are not owners on AnVIL.
                    model_instance_result.add_error(self.ERROR_NOT_OWNER_ON_ANVIL)
                elif not workspace.is_managed_by_app and not self._check_workspace_ownership(workspace_details):
                    # The workspace is not managed by the app and we are not owners.
                    # No issues here.
                    pass
                else:
                    # The workspace is managed by the app and we are owners - need to perform other checks.
                    # Since we're the owner, check workspace access.
                    sharing_audit = WorkspaceSharingAudit(workspace)
                    sharing_audit.run_audit(cache=cache)
                    if not sharing_audit.ok():
                        model_instance_result.add_error(self.ERROR_WORKSPACE_SHARING)
                    # Check is_requester_pays status. Unfortunately we have to make a separate API call.
                    response = AnVILAPIClient().get_workspace_settings(
                        workspace.billing_project.name,
                        workspace.name,
                    )
                    tmp = [x for x in response.json() if x["settingType"] == "GcpBucketRequesterPays"]
                    if len(tmp) == 0:
                        is_requester_pays_on_anvil = False
                    else:
                        is_requester_pays_on_anvil = tmp[0]["config"]["enabled"]
                    if workspace.is_requester_pays != is_requester_pays_on_anvil:
                        model_instance_result.add_error(self.ERROR_DIFFERENT_REQUESTER_PAYS)

                # Check auth domains.
                auth_domains_on_anvil = [
                    x["membersGroupName"] for x in workspace_details["workspace"]["authorizationDomain"]
                ]
                auth_domains_in_app = workspace.authorization_domains.all().values_list("name", flat=True)
                if set(auth_domains_on_anvil) != set(auth_domains_in_app):
                    model_instance_result.add_error(self.ERROR_DIFFERENT_AUTH_DOMAINS)
                # Check lock status.
                if workspace.is_locked != workspace_details["workspace"]["isLocked"]:
                    model_instance_result.add_error(self.ERROR_DIFFERENT_LOCK)

            self.add_result(model_instance_result)

        # Check for remaining workspaces on AnVIL where we are OWNER.
        for workspace_details in workspaces_on_anvil:
            if self._check_workspace_ownership(workspace_details):
                # The service account is an owner of the workspace.
                workspace_name = "{}/{}".format(
                    workspace_details["workspace"]["namespace"], workspace_details["workspace"]["name"]
                )
                self.add_result(base.NotInAppResult(workspace_name))


class WorkspaceSharingNotInAppResult(base.NotInAppResult):
    """Class to store a not in app audit result for a specific WorkspaceSharing record."""

    def __init__(self, *args, workspace=None, email=None, access=None, can_compute=None, can_share=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace
        self.email = email
        self.access = access
        self.can_compute = can_compute
        self.can_share = can_share


class WorkspaceSharingNotInAppTable(base.NotInAppTable):
    workspace = tables.Column()
    email = tables.Column()
    access = tables.Column()
    can_compute = tables.Column()
    can_share = tables.Column()
    ignore = tables.TemplateColumn(
        template_name="auditor/snippets/audit_workspacegroupsharing_notinapp_ignore_button.html",
        orderable=False,
        verbose_name="Ignore?",
    )

    class Meta:
        fields = (
            "workspace",
            "email",
            "access",
            "can_compute",
            "can_share",
        )
        exclude = ("record",)


class WorkspaceSharingIgnoredResult(base.IgnoredResult):
    """Class to store a not in app audit result for a specific WorkspaceSharing record."""

    def __init__(self, *args, current_access=None, current_can_compute=None, current_can_share=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_access = current_access
        self.current_can_compute = current_can_compute
        self.current_can_share = current_can_share


class WorkspaceSharingIgnoredTable(base.IgnoredTable):
    """A table specific to the IgnoredWorkspaceSharing model."""

    model_instance = tables.columns.Column(linkify=True, verbose_name="Details")
    model_instance__workspace = tables.columns.Column(linkify=True, verbose_name="Workspace", orderable=False)
    model_instance__ignored_email = tables.columns.Column(orderable=False, verbose_name="Ignored email")
    model_instance__added_by = tables.columns.Column(orderable=False, verbose_name="Ignored by")
    current_access = tables.columns.Column(orderable=False, verbose_name="Current access")
    current_can_compute = tables.columns.Column(orderable=False, verbose_name="Current can compute")
    current_can_share = tables.columns.Column(orderable=False, verbose_name="Current can share")

    class Meta:
        fields = (
            "model_instance",
            "model_instance__workspace",
            "model_instance__ignored_email",
            "model_instance__added_by",
            "current_access",
            "current_can_compute",
            "current_can_share",
        )
        exclude = ("record",)


class WorkspaceSharingAudit(base.AnVILAudit):
    """Class that runs an audit for sharing of a specific Workspace instance."""

    ERROR_NOT_SHARED_IN_ANVIL = "Not shared in AnVIL"
    """Error when a ManagedGroup has access to a workspace in the app but not on AnVIL."""

    ERROR_DIFFERENT_ACCESS = "Different access level in AnVIL"
    """Error when a ManagedGroup has a different access level for workspace in the app and on AnVIL."""

    ERROR_DIFFERENT_CAN_SHARE = "can_share value does not match in AnVIL"
    """Error when the can_share value for a ManagedGroup does not match what's on AnVIL."""

    ERROR_DIFFERENT_CAN_COMPUTE = "can_compute value does not match in AnVIL"
    """Error when the can_compute value for a ManagedGroup does not match what's on AnVIL."""

    not_in_app_table_class = WorkspaceSharingNotInAppTable
    ignored_table_class = WorkspaceSharingIgnoredTable

    def __init__(self, workspace, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not workspace.is_managed_by_app:
            raise AnVILNotWorkspaceOwnerError("workspace {} is not managed by app".format(workspace))
        self.workspace = workspace

    def get_cache_key(self):
        return f"workspace_sharing_{self.workspace.pk}"

    def run_audit(self, cache=False):
        """Run the audit for all workspace instances."""
        response = AnVILAPIClient().get_workspace_acl(self.workspace.billing_project.name, self.workspace.name)
        acl_in_anvil = {k.lower(): v for k, v in response.json()["acl"].items()}
        # Remove the service account.
        try:
            acl_in_anvil.pop(AnVILAPIClient().auth_session.credentials.service_account_email.lower())
        except KeyError:
            # In some cases, the workspace is shared with a group we are part of instead of directly with us.
            pass
        for access in self.workspace.workspacegroupsharing_set.all():
            # Create an audit result instance for this model.
            model_instance_result = base.ModelInstanceResult(access)
            try:
                access_details = acl_in_anvil.pop(access.group.email.lower())
            except KeyError:
                model_instance_result.add_error(self.ERROR_NOT_SHARED_IN_ANVIL)
            else:
                # Check access level.
                if access.access != access_details["accessLevel"]:
                    model_instance_result.add_error(self.ERROR_DIFFERENT_ACCESS)
                # Check can_compute value.
                if access.can_compute != access_details["canCompute"]:
                    model_instance_result.add_error(self.ERROR_DIFFERENT_CAN_COMPUTE)
                # Check can_share value -- the app never grants this, so it should always be false.
                # Can share should be True for owners and false for others.
                can_share = access.access == "OWNER"
                if access_details["canShare"] != can_share:
                    model_instance_result.add_error(self.ERROR_DIFFERENT_CAN_SHARE)
            # Save the results for this model instance.
            self.add_result(model_instance_result)

        # Handle ignored records.
        for obj in models.IgnoredWorkspaceSharing.objects.filter(workspace=self.workspace).order_by("ignored_email"):
            try:
                acl = acl_in_anvil.pop(obj.ignored_email)
                record = "{}: {}".format(acl["accessLevel"], obj.ignored_email)
                self.add_result(
                    WorkspaceSharingIgnoredResult(
                        obj,
                        record=record,
                        current_access=acl["accessLevel"],
                        current_can_compute=acl["canCompute"],
                        current_can_share=acl["canShare"],
                    )
                )
            except KeyError:
                self.add_result(
                    WorkspaceSharingIgnoredResult(
                        obj,
                        record=None,
                        current_access=None,
                        current_can_compute=None,
                        current_can_share=None,
                    )
                )

        # Add any remaining records as "not in app".
        for key in acl_in_anvil:
            self.add_result(
                WorkspaceSharingNotInAppResult(
                    "{}: {}".format(acl_in_anvil[key]["accessLevel"], key),
                    workspace=self.workspace,
                    email=key,
                    access=acl_in_anvil[key]["accessLevel"],
                    can_compute=acl_in_anvil[key]["canCompute"],
                    can_share=acl_in_anvil[key]["canShare"],
                )
            )

        # Cache the results if requested.
        if cache:
            self.cache()
