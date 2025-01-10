import django_tables2 as tables

from anvil_consortium_manager.anvil_api import AnVILAPIClient, AnVILAPIError404
from anvil_consortium_manager.exceptions import AnVILNotGroupAdminError
from anvil_consortium_manager.models import Account, GroupAccountMembership, GroupGroupMembership, ManagedGroup

from .. import models
from . import base


class ManagedGroupAudit(base.AnVILAudit):
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
        for group in ManagedGroup.objects.all():
            model_instance_result = base.ModelInstanceResult(group)
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
                self.add_result(base.NotInAppResult(group_name))


class ManagedGroupMembershipNotInAppResult(base.NotInAppResult):
    """Class to store a not in app audit result for a specific ManagedGroupMembership record."""

    def __init__(self, *args, group=None, email=None, role=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        self.email = email
        self.role = role


class ManagedGroupMembershipNotInAppTable(base.NotInAppTable):
    group = tables.Column()
    email = tables.Column()
    role = tables.Column()
    ignore = tables.TemplateColumn(
        template_name="anvil_consortium_manager/snippets/audit_managedgroupmembership_notinapp_ignore_button.html",
        orderable=False,
        verbose_name="Ignore?",
    )

    class Meta:
        fields = (
            "group",
            "email",
            "role",
        )
        exclude = ("record",)


class ManagedGroupMembershipIgnoredResult(base.IgnoredResult):
    """Class to store a not in app audit result for a specific ManagedGroupMembership record."""

    def __init__(self, *args, current_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_role = current_role


class ManagedGroupMembershipIgnoredTable(base.IgnoredTable):
    """A table specific to the IgnoredManagedGroupMembership model."""

    model_instance = tables.columns.Column(linkify=True, verbose_name="Details")
    model_instance__group = tables.columns.Column(linkify=True, verbose_name="Managed group", orderable=False)
    model_instance__ignored_email = tables.columns.Column(orderable=False, verbose_name="Ignored email")
    model_instance__added_by = tables.columns.Column(orderable=False, verbose_name="Ignored by")
    current_role = tables.columns.Column(verbose_name="Current role")

    class Meta:
        fields = (
            "model_instance",
            "model_instance__group",
            "model_instance__ignored_email",
            "model_instance__added_by",
            "current_role",
            # "record",
        )


class ManagedGroupMembershipAudit(base.AnVILAudit):
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

    not_in_app_table_class = ManagedGroupMembershipNotInAppTable
    ignored_table_class = ManagedGroupMembershipIgnoredTable

    def __init__(self, managed_group, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not managed_group.is_managed_by_app:
            raise AnVILNotGroupAdminError("group {} is not managed by app".format(managed_group.name))
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
            model_instance_result = base.ModelInstanceResult(membership)
            # Check for deactivated account memberships.
            if membership.account.status == Account.INACTIVE_STATUS:
                model_instance_result.add_error(self.ERROR_DEACTIVATED_ACCOUNT)
            # Check membership status on AnVIL.
            if membership.role == GroupAccountMembership.ADMIN:
                try:
                    admins_in_anvil.remove(membership.account.email.lower())
                except ValueError:
                    # This is an error - the email is not in the list of admins.
                    model_instance_result.add_error(self.ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL)
            elif membership.role == GroupAccountMembership.MEMBER:
                try:
                    members_in_anvil.remove(membership.account.email.lower())
                except ValueError:
                    # This is an error - the email is not in the list of members.
                    model_instance_result.add_error(self.ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL)
            self.add_result(model_instance_result)

        # Check group-group membership.
        for membership in self.managed_group.child_memberships.all():
            model_instance_result = base.ModelInstanceResult(membership)
            if membership.role == GroupGroupMembership.ADMIN:
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
            elif membership.role == GroupGroupMembership.MEMBER:
                try:
                    members_in_anvil.remove(membership.child_group.email.lower())
                except ValueError:
                    # This email is not in the list of members.
                    model_instance_result.add_error(self.ERROR_GROUP_MEMBER_NOT_IN_ANVIL)
            self.add_result(model_instance_result)

        # Add any admin that the app doesn't know about.
        ignored_qs = models.IgnoredManagedGroupMembership.objects.filter(group=self.managed_group)
        for obj in ignored_qs.order_by("ignored_email"):
            try:
                admins_in_anvil.remove(obj.ignored_email)
                record = "{}: {}".format(GroupAccountMembership.ADMIN, obj.ignored_email)
                self.add_result(
                    ManagedGroupMembershipIgnoredResult(obj, record=record, current_role=GroupAccountMembership.ADMIN)
                )
            except ValueError:
                try:
                    members_in_anvil.remove(obj.ignored_email)
                    record = "{}: {}".format(GroupAccountMembership.MEMBER, obj.ignored_email)
                    self.add_result(
                        ManagedGroupMembershipIgnoredResult(
                            obj, record=record, current_role=GroupAccountMembership.MEMBER
                        )
                    )
                except ValueError:
                    # This email is not in the list of members or admins.
                    self.add_result(ManagedGroupMembershipIgnoredResult(obj, record=None))

        for member in admins_in_anvil:
            record = "{}: {}".format(GroupAccountMembership.ADMIN, member)
            self.add_result(
                ManagedGroupMembershipNotInAppResult(
                    record, group=self.managed_group, email=member, role=GroupAccountMembership.ADMIN
                )
            )
        # Add any members that the app doesn't know about.
        for member in members_in_anvil:
            record = "{}: {}".format(GroupAccountMembership.MEMBER, member)
            self.add_result(
                ManagedGroupMembershipNotInAppResult(
                    record, group=self.managed_group, email=member, role=GroupAccountMembership.MEMBER
                )
            )
