from .. import models
from ..anvil_api import AnVILAPIClient
from .base import AnVILAudit, ModelInstanceResult, NotInAppResult


class WorkspaceAudit(AnVILAudit):
    """Class to runs an audit for Workspace instances."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    """Error when a Workspace in the app does not exist on AnVIL."""

    ERROR_NOT_OWNER_ON_ANVIL = "Not an owner on AnVIL"
    """Error when the service account running the app is not an owner of the Workspace on AnVIL."""

    ERROR_DIFFERENT_AUTH_DOMAINS = "Has different auth domains on AnVIL"
    """Error when the Workspace has different auth domains in the app and on AnVIL."""

    ERROR_WORKSPACE_SHARING = "Workspace sharing does not match on AnVIL"
    """Error when a Workspace is shared with different ManagedGroups in the app and on AnVIL."""

    ERROR_DIFFERENT_LOCK = "Workspace lock status does not match on AnVIL"
    """Error when the workspace.is_locked status does not match the lock status on AnVIL."""

    ERROR_DIFFERENT_REQUESTER_PAYS = "Workspace bucket requester_pays status does not match on AnVIL"
    """Error when the workspace.is_locked status does not match the lock status on AnVIL."""

    def run_audit(self):
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
        for workspace in models.Workspace.objects.all():
            model_instance_result = ModelInstanceResult(workspace)
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
                if workspace_details["accessLevel"] != "OWNER":
                    model_instance_result.add_error(self.ERROR_NOT_OWNER_ON_ANVIL)
                else:
                    # Since we're the owner, check workspace access.
                    sharing_audit = WorkspaceSharingAudit(workspace)
                    sharing_audit.run_audit()
                    if not sharing_audit.ok():
                        model_instance_result.add_error(self.ERROR_WORKSPACE_SHARING)
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
                # Check is_requester_pays status. Unfortunately we have to make a separate API call.
                response = AnVILAPIClient().get_workspace(
                    workspace.billing_project.name,
                    workspace.name,
                    fields=["bucketOptions"],
                )
                if workspace.is_requester_pays != response.json()["bucketOptions"]["requesterPays"]:
                    model_instance_result.add_error(self.ERROR_DIFFERENT_REQUESTER_PAYS)

            self.add_result(model_instance_result)

        # Check for remaining workspaces on AnVIL where we are OWNER.
        not_in_app = [
            "{}/{}".format(x["workspace"]["namespace"], x["workspace"]["name"])
            for x in workspaces_on_anvil
            if x["accessLevel"] == "OWNER"
        ]
        for workspace_name in not_in_app:
            self.add_result(NotInAppResult(workspace_name))


class WorkspaceSharingAudit(AnVILAudit):
    """Class that runs an audit for sharing of a specific Workspace instance."""

    ERROR_NOT_SHARED_IN_ANVIL = "Not shared in AnVIL"
    """Error when a ManagedGroup has access to a workspace in the app but not on AnVIL."""

    ERROR_DIFFERENT_ACCESS = "Different access level in AnVIL"
    """Error when a ManagedGroup has a different access level for workspace in the app and on AnVIL."""

    ERROR_DIFFERENT_CAN_SHARE = "can_share value does not match in AnVIL"
    """Error when the can_share value for a ManagedGroup does not match what's on AnVIL."""

    ERROR_DIFFERENT_CAN_COMPUTE = "can_compute value does not match in AnVIL"
    """Error when the can_compute value for a ManagedGroup does not match what's on AnVIL."""

    def __init__(self, workspace, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace

    def run_audit(self):
        """Run the audit for all workspace instances."""
        api_client = AnVILAPIClient()
        response = api_client.get_workspace_acl(self.workspace.billing_project.name, self.workspace.name)
        acl_in_anvil = {k.lower(): v for k, v in response.json()["acl"].items()}
        # Remove the service account.
        try:
            acl_in_anvil.pop(api_client.auth_session.credentials.service_account_email.lower())
        except KeyError:
            # In some cases, the workspace is shared with a group we are part of instead of directly with us.
            pass
        for access in self.workspace.workspacegroupsharing_set.all():
            # Create an audit result instance for this model.
            model_instance_result = ModelInstanceResult(access)
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

        # Add any access that the app doesn't know about.
        for key in acl_in_anvil:
            self.add_result(NotInAppResult("{}: {}".format(acl_in_anvil[key]["accessLevel"], key)))
