from abc import ABC

from .. import exceptions, models
from ..anvil_api import AnVILAPIClient


class ModelInstanceResult:
    """Class to hold an audit result for a specific instance of a model."""

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

    def __init__(self, record):
        self.record = record

    def __str__(self):
        return self.record


class AnVILAudit(ABC):
    """Abstract base class for AnVIL audit results."""

    def __init__(self):
        self._model_instance_results = []
        self._not_in_app_results = []

    def ok(self):
        model_instances_ok = all([x.ok() for x in self._model_instance_results])
        not_in_app_ok = len(self._not_in_app_results) == 0
        return model_instances_ok and not_in_app_ok

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


class ManagedGroupMembershipAudit(AnVILAudit):
    """Class to hold audit results for the membership records of a specific ManagedGroup instance."""

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
            self._not_in_app_results.append(
                NotInAppResult(
                    "{}: {}".format(models.GroupAccountMembership.ADMIN, member)
                )
            )
        # Add any members that the app doesn't know about.
        for member in members_in_anvil:
            self._not_in_app_results.append(
                NotInAppResult(
                    "{}: {}".format(models.GroupAccountMembership.MEMBER, member)
                )
            )
