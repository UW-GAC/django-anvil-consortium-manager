"""Classes handling auditing of information in the Django database against AnVIL."""

from abc import ABC, abstractproperty


class AnVILAuditResults(ABC):
    """Abstract base class to store audit results from AnVIL."""

    @abstractproperty
    def allowed_errors(self):
        """List specifying the list of allowed errors for this audit result class."""
        ...

    def __init__(self):
        self.verified = set()
        self.errors = {}
        self.not_in_app = set()

    def add_not_in_app(self, record):
        """Add a record that is on ANVIL but is not in the app.

        Args:
            record (str): An identifier for the record that is not in the app.
                For example, for ManagedGroups, this will be the name of the group on AnVIL.
        """
        self.not_in_app.add(record)

    def add_error(self, model_instance, error):
        """Add an error for a Django model instance.

        Args:
            model_instance (obj): The Django model instance that had a detected error.
            error (str): The error that was detected.

        Raises:
            ValueError: If the `error` is not in the `allowed_errors` attribute of the class.
        """
        if error not in self.allowed_errors:
            raise ValueError("'{}' is not an allowed error.".format(error))
        if model_instance in self.verified:
            # Should this just remove it from verified and add the error instead?
            raise ValueError(
                "Cannot add error for model_instance {} that is already verified.".format(
                    model_instance
                )
            )
        if model_instance in self.errors:
            self.errors[model_instance].append(error)
        else:
            self.errors[model_instance] = [error]

    def add_verified(self, model_instance):
        """Add a Django model instance that has been verified against AnVIL.

        Args:
            model_instance (obj): The Django model instance that was verified.

        Raises:
            ValueError: If the Django model instance being added has an error recorded in the `errors` attribute.
        """
        if model_instance in self.errors:
            raise ValueError("{} has reported errors.".format(model_instance))
        self.verified.add(model_instance)

    def get_verified(self):
        """Return a set of the verified records.

        Returns:
            set: The set of Django model instances that were verified against AnVIL.
        """
        return self.verified

    def get_errors(self):
        """Return the errors that were recorded in the audit.

        Returns:
            dict: A dictionary of errors.

            The keys of the dictionary are the Django model instances that had errors.
            The value for a given element is a list of the errors that were detected for that instance.
        """
        return self.errors

    def get_not_in_app(self):
        """Return records that are on AnVIL but not in the app.

        Returns:
            set: The records that exist on AnVIL but not in the app.
        """
        return self.not_in_app

    def ok(self):
        """Check if the audit results are ok.

        Returns:
            bool: An indicator of whether all audited records were successfully verified.
        """
        return not self.errors and not self.not_in_app

    def export(
        self, include_verified=True, include_errors=True, include_not_in_app=True
    ):
        """Return a dictionary representation of the audit results."""
        x = {}
        if include_verified:
            x["verified"] = [
                {"id": instance.pk, "instance": instance}
                for instance in self.get_verified()
            ]
        if include_errors:
            x["errors"] = [
                {"id": k.pk, "instance": k, "errors": v}
                for k, v in self.get_errors().items()
            ]
        if include_not_in_app:
            x["not_in_app"] = list(self.get_not_in_app())
        return x


class BillingProjectAuditResults(AnVILAuditResults):
    """Class to hold audit results for :class:`~anvil_consortium_manager.models.BillingProject`.

    The elements of the set returned by ``get_verified()``
    and the keys of the dictionary returned by ``get_errors()``
    should all be :class:`~anvil_consortium_manager.models.BillingProject` model instances.
    """

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    """Error when a BillingProject in the app does not exist in AnVIL."""

    # Set up allowed errors.
    allowed_errors = ERROR_NOT_IN_ANVIL


class AccountAuditResults(AnVILAuditResults):
    """Class to hold audit results for :class:`~anviL_consortium_manager.models.Account`.

    The elements of the set returned by ``get_verified()``
    and the keys of the dictionary returned by ``get_errors()``
    should all be :class:`~anvil_consortium_manager.models.Account` model instances.
    """

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    """Error when the Account does not exist in AnVIL."""

    # Set up allowed errors.
    allowed_errors = ERROR_NOT_IN_ANVIL


class ManagedGroupAuditResults(AnVILAuditResults):
    """Class to hold audit results for :class:`~anviL_consortium_manager.models.ManagedGroup`s.

    The elements of the set returned by ``get_verified()``
    and the keys of the dictionary returned by ``get_errors()``
    should are be :class:`~anvil_consortium_manager.models.ManagedGroup` model instances.
    """

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    """Error when a ManagedGroup in the app does not exist in AnVIL."""

    ERROR_DIFFERENT_ROLE = "App has a different role in this group"
    """Error when the service account running the app has a different role on AnVIL."""

    ERROR_GROUP_MEMBERSHIP = "Group membership does not match in AnVIL"
    """Error when a ManagedGroup has a different record of membership in the app compared to on AnVIL."""

    # Set up allowed errors.
    allowed_errors = (
        ERROR_NOT_IN_ANVIL,
        ERROR_DIFFERENT_ROLE,
        ERROR_GROUP_MEMBERSHIP,
    )


class ManagedGroupMembershipAuditResults(AnVILAuditResults):
    """Class to hold audit results for the membership of a model instance of
    :class:`~anviL_consortium_manager.models.ManagedGroup`.

    The elements of the set returned by ``get_verified()``
    and the keys of the dictionary returned by ``get_errors()``
    should all be :class:`~anvil_consortium_manager.models.ManagedGroupMembership` model instances.
    """

    ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL = "Account not an admin in AnVIL"
    """Error when an Account is an admin of a ManagedGroup on the app, but not in AnVIL."""

    ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL = "Account not a member in AnVIL"
    """Error when an Account is a member of a ManagedGroup on the app, but not in AnVIL."""

    ERROR_GROUP_ADMIN_NOT_IN_ANVIL = "Group not an admin in AnVIL"
    """Error when a ManagedGroup is an admin of another ManagedGroup on the app, but not in AnVIL."""

    ERROR_GROUP_MEMBER_NOT_IN_ANVIL = "Group not a member in AnVIL"
    """Error when an ManagedGroup is a member of another ManagedGroup on the app, but not in AnVIL."""

    # Set up allowed errors.
    allowed_errors = (
        ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL,
        ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL,
        ERROR_GROUP_ADMIN_NOT_IN_ANVIL,
        ERROR_GROUP_MEMBER_NOT_IN_ANVIL,
    )


class WorkspaceAuditResults(AnVILAuditResults):
    """Class to hold audit results for :class:`~anviL_consortium_manager.models.Workspace`.

    The elements of the set returned by ``get_verified()``
    and the keys of the dictionary returned by ``get_errors()``
    should all be :class:`~anvil_consortium_manager.models.Workspace` model instances.
    """

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

    # Set up allowed errors.
    allowed_errors = (
        ERROR_NOT_IN_ANVIL,
        ERROR_NOT_OWNER_ON_ANVIL,
        ERROR_DIFFERENT_AUTH_DOMAINS,
        ERROR_WORKSPACE_SHARING,
        ERROR_DIFFERENT_LOCK,
    )


class WorkspaceGroupSharingAuditResults(AnVILAuditResults):
    """Class to hold audit results for group sharing to :class:`~anviL_consortium_manager.models.Workspace`s.

    The elements of the set returned by ``get_verified()``
    and the keys of the dictionary returned by ``get_errors()``
    should all be :class:`~anvil_consortium_manager.models.WorkspaceGroupSharing` model instances.
    """

    ERROR_NOT_SHARED_IN_ANVIL = "Not shared in AnVIL"
    """Error when a ManagedGroup has access to a workspace in the app but not on AnVIL."""

    ERROR_DIFFERENT_ACCESS = "Different access level in AnVIL"
    """Error when a ManagedGroup has a different access level for workspace in the app and on AnVIL."""

    ERROR_DIFFERENT_CAN_SHARE = "can_share value does not match in AnVIL"
    """Error when the can_share value for a ManagedGroup does not match what's on AnVIL."""

    ERROR_DIFFERENT_CAN_COMPUTE = "can_compute value does not match in AnVIL"
    """Error when the can_compute value for a ManagedGroup does not match what's on AnVIL."""

    # Set up allowed errors.
    allowed_errors = (
        ERROR_NOT_SHARED_IN_ANVIL,
        ERROR_DIFFERENT_ACCESS,
        ERROR_DIFFERENT_CAN_SHARE,
        ERROR_DIFFERENT_CAN_COMPUTE,
    )
