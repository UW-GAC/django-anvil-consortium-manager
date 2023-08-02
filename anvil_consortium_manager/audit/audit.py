from abc import ABC

from .. import exceptions, models
from ..anvil_api import AnVILAPIClient, AnVILAPIError404


class ModelInstanceResult:
    """Class to hold an audit result for a specific instance of a model."""

    # TODO:
    # - Write tests for this class.

    def __init__(self, model_instance):
        self.model_instance = model_instance
        self.errors = set()

    def __eq__(self, other):
        return (
            self.model_instance == other.model_instance and self.errors == other.errors
        )

    def add_error(self, error):
        """Add an error to the audit result for this model instance."""
        self.errors.add(error)

    def ok(self):
        """Check whether an audit result has errors."""

        if self.errors:
            return False
        else:
            return True


class NotInAppResult:
    """Class to hold an audit result for a record that is not present in the app."""

    # TODO:
    # - Write tests for this class.

    def __init__(self, record):
        self.record = record

    def __str__(self):
        return self.record


class AnVILAudit(ABC):
    """Abstract base class for AnVIL audit results."""

    # TODO:
    # - in add_not_in_app_result, check that the result hasn't already been added.
    # - in add_model_instance_result, check that the result hasn't been added yet.
    # - add a model_class field, in add_model_instance_result check that the model instance is the correct type
    #   - This may not work when auditing group membership, since that has both group and account member records.
    # - Write tests for this class.

    def __init__(self):
        self._model_instance_results = []
        self._not_in_app_results = []

    def ok(self):
        model_instances_ok = all([x.ok() for x in self._model_instance_results])
        not_in_app_ok = len(self._not_in_app_results) == 0
        return model_instances_ok and not_in_app_ok

    def run_audit(self):
        raise NotImplementedError("Define a run_audit method.")

    def add_not_in_app_result(self, result):
        if not isinstance(result, NotInAppResult):
            raise ValueError("result must be an instance of NotInAppResult.")
        # Check that it hasn't been added yet.
        self._not_in_app_results.append(result)

    def add_model_instance_result(self, result):
        if not isinstance(result, ModelInstanceResult):
            raise ValueError("result must be an instance of ModelInstanceResult.")
        # Check that it hasn't been added yet.
        self._model_instance_results.append(result)

    def get_result_for_model_instance(self, model_instance):
        results = [
            x
            for x in self._model_instance_results
            if x.model_instance == model_instance
        ]
        if len(results) != 1:
            raise ValueError("model_instance is not in the results.")
        return results[0]

    def get_verified_results(self):
        return [x for x in self._model_instance_results if x.ok()]

    def get_error_results(self):
        return [x for x in self._model_instance_results if not x.ok()]

    def get_not_in_app_results(self):
        return self._not_in_app_results


class BillingProjectAudit(AnVILAudit):
    """Class that runs an audit for BillingProject instances."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    """Error when a BillingProject in the app does not exist in AnVIL."""

    def run_audit(self):
        # Check that all billing projects exist.
        for billing_project in models.BillingProject.objects.filter(
            has_app_as_user=True
        ).all():
            model_instance_result = ModelInstanceResult(billing_project)
            if not billing_project.anvil_exists():
                model_instance_result.add_error(self.ERROR_NOT_IN_ANVIL)
            self.add_model_instance_result(model_instance_result)


class AccountAudit(AnVILAudit):
    """Class that runs an audit for Account instances."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    """Error when the Account does not exist in AnVIL."""

    def run_audit(self):
        # Only checks active accounts.
        for account in models.Account.objects.filter(
            status=models.Account.ACTIVE_STATUS
        ).all():
            model_instance_result = ModelInstanceResult(account)
            if not account.anvil_exists():
                model_instance_result.add_error(self.ERROR_NOT_IN_ANVIL)
            self.add_model_instance_result(model_instance_result)


class ManagedGroupAudit(AnVILAudit):
    """Class to runs an audit for ManagedGroup instances."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    """Error when a ManagedGroup in the app does not exist in AnVIL."""

    ERROR_DIFFERENT_ROLE = "App has a different role in this group"
    """Error when the service account running the app has a different role on AnVIL."""

    ERROR_GROUP_MEMBERSHIP = "Group membership does not match in AnVIL"
    """Error when a ManagedGroup has a different record of membership in the app compared to on AnVIL."""

    def run_audit(self):
        """Run an audit on managed groups in the app."""
        # Check the list of groups.
        response = AnVILAPIClient().get_groups()
        # Change from list of group dictionaries to dictionary of roles. That way we can handle being both
        # a member and an admin of a group.
        groups_on_anvil = {}
        for group_details in response.json():
            group_name = group_details["groupName"]
            role = group_details["role"].lower()
            try:
                groups_on_anvil[group_name] = groups_on_anvil[group_name] + [role]
            except KeyError:
                groups_on_anvil[group_name] = [role]
        # Audit groups that exist in the app.
        for group in models.ManagedGroup.objects.all():
            model_instance_result = ModelInstanceResult(group)
            try:
                group_roles = groups_on_anvil.pop(group.name)
            except KeyError:
                # Check if the group actually does exist but we're not a member of it.
                try:
                    # If this returns a 404 error, then the group actually does not exist.
                    response = AnVILAPIClient().get_group_email(group.name)
                    if group.is_managed_by_app:
                        model_instance_result.add_error(self.ERROR_DIFFERENT_ROLE)

                except AnVILAPIError404:
                    model_instance_result.add_error(self.ERROR_NOT_IN_ANVIL)
                    # Perhaps we want to add has_app_as_member as a field and check that.
            else:
                # Check role.
                if group.is_managed_by_app:
                    if "admin" not in group_roles:
                        model_instance_result.add_error(self.ERROR_DIFFERENT_ROLE)
                    else:
                        membership_audit = ManagedGroupMembershipAudit(group)
                        membership_audit.run_audit()
                        if not membership_audit.ok():
                            model_instance_result.add_error(self.ERROR_GROUP_MEMBERSHIP)
                elif not group.is_managed_by_app and "admin" in group_roles:
                    model_instance_result.add_error(self.ERROR_DIFFERENT_ROLE)
            # Add the final result for this group to the class results.
            self.add_model_instance_result(model_instance_result)

        # Check for groups that exist on AnVIL but not the app.
        for group_name in groups_on_anvil:
            self.add_not_in_app_result(NotInAppResult(group_name))


class ManagedGroupMembershipAudit(AnVILAudit):
    """Class that runs an audit for membership of a specific ManagedGroup instance."""

    # Error strings for this class.
    ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL = "Account not an admin in AnVIL"
    """Error when an Account is an admin of a ManagedGroup on the app, but not in AnVIL."""

    ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL = "Account not a member in AnVIL"
    """Error when an Account is a member of a ManagedGroup on the app, but not in AnVIL."""

    ERROR_GROUP_ADMIN_NOT_IN_ANVIL = "Group not an admin in AnVIL"
    """Error when a ManagedGroup is an admin of another ManagedGroup on the app, but not in AnVIL."""

    ERROR_GROUP_MEMBER_NOT_IN_ANVIL = "Group not a member in AnVIL"
    """Error when an ManagedGroup is a member of another ManagedGroup on the app, but not in AnVIL."""

    def __init__(self, managed_group, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not managed_group.is_managed_by_app:
            raise exceptions.AnVILNotGroupAdminError(
                "group {} is not managed by app".format(self.name)
            )
        self.managed_group = managed_group

    def run_audit(self):
        """Run an audit on all membership of the managed group."""
        # Get the list of members on AnVIL.
        api_client = AnVILAPIClient()
        # --- Members ---
        response = api_client.get_group_members(self.managed_group.name)
        # Convert to case insensitive emails.
        members_in_anvil = [x.lower() for x in response.json()]
        # Sometimes the service account is also listed as a member. Remove that too.
        try:
            members_in_anvil.remove(
                api_client.auth_session.credentials.service_account_email.lower()
            )
        except ValueError:
            # Not listed as a member -- this is ok.
            pass
        # -- Admins ---
        response = api_client.get_group_admins(self.managed_group.name)
        # Convert to case-insensitive emails.
        admins_in_anvil = [x.lower() for x in response.json()]
        # Remove the service account as admin.
        try:
            admins_in_anvil.remove(
                api_client.auth_session.credentials.service_account_email.lower()
            )
        except ValueError:
            # Not listed as an admin -- this is ok because it could be via group membership.
            pass

        # Check group-account membership.
        for membership in self.managed_group.groupaccountmembership_set.all():
            # Create an audit result instance for this model.
            model_instance_result = ModelInstanceResult(membership)
            if membership.role == models.GroupAccountMembership.ADMIN:
                try:
                    admins_in_anvil.remove(membership.account.email.lower())
                except ValueError:
                    # This email is not in the list of members.
                    model_instance_result.add_error(
                        self.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL
                    )
            elif membership.role == models.GroupAccountMembership.MEMBER:
                try:
                    members_in_anvil.remove(membership.account.email.lower())
                except ValueError:
                    # This email is not in the list of members.
                    model_instance_result.add_error(
                        self.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL
                    )
            self.add_model_instance_result(model_instance_result)

        # Check group-group membership.
        for membership in self.managed_group.child_memberships.all():
            model_instance_result = ModelInstanceResult(membership)
            if membership.role == models.GroupGroupMembership.ADMIN:
                try:
                    admins_in_anvil.remove(membership.child_group.email.lower())
                except ValueError:
                    # This email is not in the list of members.
                    model_instance_result.add_error(self.ERROR_GROUP_ADMIN_NOT_IN_ANVIL)
                # Also remove from members if it exists there.
                try:
                    members_in_anvil.remove(membership.child_group.email.lower())
                except ValueError:
                    # The group is not directly listed as a member, so this is ok.
                    # It is already an admin.
                    pass
            elif membership.role == models.GroupGroupMembership.MEMBER:
                try:
                    members_in_anvil.remove(membership.child_group.email.lower())
                except ValueError:
                    # This email is not in the list of members.
                    model_instance_result.add_error(
                        self.ERROR_GROUP_MEMBER_NOT_IN_ANVIL
                    )
            self.add_model_instance_result(model_instance_result)

        # Add any admin that the app doesn't know about.
        for member in admins_in_anvil:
            self.add_not_in_app_result(
                NotInAppResult(
                    "{}: {}".format(models.GroupAccountMembership.ADMIN, member)
                )
            )
        # Add any members that the app doesn't know about.
        for member in members_in_anvil:
            self.add_not_in_app_result(
                NotInAppResult(
                    "{}: {}".format(models.GroupAccountMembership.MEMBER, member)
                )
            )


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

    def run_audit(self):
        """Run an audit on Workspaces in the app."""
        # Check the list of workspaces.
        fields = [
            "workspace.namespace",
            "workspace.name",
            "workspace.authorizationDomain",
            "workspace.isLocked,accessLevel",
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
                        and x["workspace"]["namespace"]
                        == workspace.billing_project.name
                    )
                )
            except StopIteration:
                model_instance_result.add_error(self.ERROR_NOT_IN_ANVIL)
            else:
                # Check role.
                workspace_details = workspaces_on_anvil.pop(i)
                if workspace_details["accessLevel"] != "OWNER":
                    model_instance_result.add_error(self.ERROR_NOT_OWNER_ON_ANVIL)
                elif not workspace.anvil_audit_sharing().ok():
                    # Since we're the owner, check workspace access.
                    model_instance_result.add_error(self.ERROR_WORKSPACE_SHARING)
                # Check auth domains.
                auth_domains_on_anvil = [
                    x["membersGroupName"]
                    for x in workspace_details["workspace"]["authorizationDomain"]
                ]
                auth_domains_in_app = workspace.authorization_domains.all().values_list(
                    "name", flat=True
                )
                if set(auth_domains_on_anvil) != set(auth_domains_in_app):
                    model_instance_result.add_error(self.ERROR_DIFFERENT_AUTH_DOMAINS)
                # Check lock status.
                if workspace.is_locked != workspace_details["workspace"]["isLocked"]:
                    model_instance_result.add_error(self.ERROR_DIFFERENT_LOCK)

            self.add_model_instance_result(model_instance_result)

        # Check for remaining workspaces on AnVIL where we are OWNER.
        not_in_app = [
            "{}/{}".format(x["workspace"]["namespace"], x["workspace"]["name"])
            for x in workspaces_on_anvil
            if x["accessLevel"] == "OWNER"
        ]
        for workspace_name in not_in_app:
            self.add_not_in_app_result(NotInAppResult(workspace_name))


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
        response = api_client.get_workspace_acl(
            self.workspace.billing_project.name, self.workspace.name
        )
        acl_in_anvil = {k.lower(): v for k, v in response.json()["acl"].items()}
        # Remove the service account.
        try:
            acl_in_anvil.pop(
                api_client.auth_session.credentials.service_account_email.lower()
            )
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
            self.add_model_instance_result(model_instance_result)

        # Add any access that the app doesn't know about.
        for key in acl_in_anvil:
            self.add_not_in_app_result(
                NotInAppResult("{}: {}".format(acl_in_anvil[key]["accessLevel"], key))
            )
