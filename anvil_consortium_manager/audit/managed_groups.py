from .. import exceptions, models
from ..anvil_api import AnVILAPIClient, AnVILAPIError404
from .base import AnVILAudit, ModelInstanceResult, NotInAppResult


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
            self.add_result(model_instance_result)

        # Check for groups that exist on AnVIL but not the app.
        for group_name in groups_on_anvil:
            # Only report the ones where the app is an admin.
            if "admin" in groups_on_anvil[group_name]:
                self.add_result(NotInAppResult(group_name))


class ManagedGroupMembershipAudit(AnVILAudit):
    """Class that runs an audit for membership of a specific ManagedGroup instance."""

    # Error strings for this class.
    ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL = "Account not an admin in AnVIL"
    """Error when an Account is an admin of a ManagedGroup on the app, but not in AnVIL."""

    ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL = "Account not a member in AnVIL"
    """Error when an Account is a member of a ManagedGroup on the app, but not in AnVIL."""

    ERROR_DEACTIVATED_ACCOUNT = "Account is deactivated but still has membership records in the app."
    """Error when a deactivated Account still has membership records in the app."""

    ERROR_GROUP_ADMIN_NOT_IN_ANVIL = "Group not an admin in AnVIL"
    """Error when a ManagedGroup is an admin of another ManagedGroup on the app, but not in AnVIL."""

    ERROR_GROUP_MEMBER_NOT_IN_ANVIL = "Group not a member in AnVIL"
    """Error when an ManagedGroup is a member of another ManagedGroup on the app, but not in AnVIL."""

    def __init__(self, managed_group, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not managed_group.is_managed_by_app:
            raise exceptions.AnVILNotGroupAdminError("group {} is not managed by app".format(managed_group.name))
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
            members_in_anvil.remove(api_client.auth_session.credentials.service_account_email.lower())
        except ValueError:
            # Not listed as a member -- this is ok.
            pass
        # -- Admins ---
        response = api_client.get_group_admins(self.managed_group.name)
        # Convert to case-insensitive emails.
        admins_in_anvil = [x.lower() for x in response.json()]
        # Remove the service account as admin.
        try:
            admins_in_anvil.remove(api_client.auth_session.credentials.service_account_email.lower())
        except ValueError:
            # Not listed as an admin -- this is ok because it could be via group membership.
            pass

        # Check group-account membership.
        for membership in self.managed_group.groupaccountmembership_set.all():
            # Create an audit result instance for this model.
            model_instance_result = ModelInstanceResult(membership)
            # Check for deactivated account memberships.
            if membership.account.status == models.Account.INACTIVE_STATUS:
                model_instance_result.add_error(self.ERROR_DEACTIVATED_ACCOUNT)
            # Check membership status on AnVIL.
            if membership.role == models.GroupAccountMembership.ADMIN:
                try:
                    admins_in_anvil.remove(membership.account.email.lower())
                except ValueError:
                    # This is an error - the email is not in the list of admins.
                    model_instance_result.add_error(self.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL)
            elif membership.role == models.GroupAccountMembership.MEMBER:
                try:
                    members_in_anvil.remove(membership.account.email.lower())
                except ValueError:
                    # This is an error - the email is not in the list of members.
                    model_instance_result.add_error(self.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL)
            self.add_result(model_instance_result)

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
                    model_instance_result.add_error(self.ERROR_GROUP_MEMBER_NOT_IN_ANVIL)
            self.add_result(model_instance_result)

        # Add any admin that the app doesn't know about.
        for member in admins_in_anvil:
            self.add_result(NotInAppResult("{}: {}".format(models.GroupAccountMembership.ADMIN, member)))
        # Add any members that the app doesn't know about.
        for member in members_in_anvil:
            self.add_result(NotInAppResult("{}: {}".format(models.GroupAccountMembership.MEMBER, member)))
