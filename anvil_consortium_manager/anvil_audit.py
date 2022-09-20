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


class BillingProjectAuditResults(AnVILAuditResults):
    """Class to hold audit results for :class:`~anviL_consortium_manager.models.BillingProject`s."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    # Set up allowed errors.
    allowed_errors = ERROR_NOT_IN_ANVIL


class AccountAuditResults(AnVILAuditResults):
    """Class to hold audit results for :class:`~anviL_consortium_manager.models.Accounts`."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    # Set up allowed errors.
    allowed_errors = ERROR_NOT_IN_ANVIL


class ManagedGroupAuditResults(AnVILAuditResults):
    """Class to hold audit results for :class:`~anviL_consortium_manager.models.ManagedGroup`s."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    ERROR_DIFFERENT_ROLE = "App has a different role in this group"
    ERROR_GROUP_MEMBERSHIP = "Group membership does not match in AnVIL"
    # Set up allowed errors.
    allowed_errors = (
        ERROR_NOT_IN_ANVIL,
        ERROR_DIFFERENT_ROLE,
        ERROR_GROUP_MEMBERSHIP,
    )


class ManagedGroupMembershipAuditResults(AnVILAuditResults):
    """Class to hold audit results for the membership of a model instance of
    :class:`~anviL_consortium_manager.models.ManagedGroup`.
    """

    ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL = "Account not an admin in AnVIL"
    ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL = "Account not a member in AnVIL"
    ERROR_GROUP_ADMIN_NOT_IN_ANVIL = "Group not an admin in AnVIL"
    ERROR_GROUP_MEMBER_NOT_IN_ANVIL = "Group not a member in AnVIL"
    # Set up allowed errors.
    allowed_errors = (
        ERROR_ACCOUNT_ADMIN_NOT_IN_ANVIL,
        ERROR_ACCOUNT_MEMBER_NOT_IN_ANVIL,
        ERROR_GROUP_ADMIN_NOT_IN_ANVIL,
        ERROR_GROUP_MEMBER_NOT_IN_ANVIL,
    )


class WorkspaceAuditResults(AnVILAuditResults):
    """Class to hold audit results for :class:`~anviL_consortium_manager.models.Workspace`s."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    ERROR_NOT_OWNER_ON_ANVIL = "Not an owner on AnVIL"
    ERROR_DIFFERENT_AUTH_DOMAINS = "Has different auth domains on AnVIL"
    # Set up allowed errors.
    allowed_errors = (
        ERROR_NOT_IN_ANVIL,
        ERROR_NOT_OWNER_ON_ANVIL,
        ERROR_DIFFERENT_AUTH_DOMAINS,
    )


class WorkspaceGroupAccessAuditResults(AnVILAuditResults):
    """Class to hold audit results for group access to :class:`~anviL_consortium_manager.models.Workspace`s."""

    ERROR_NO_ACCESS_IN_ANVIL = "No access in AnVIL"
    ERROR_DIFFERENT_ACCESS = "Different access level in AnVIL"
    ERROR_DIFFERENT_CAN_SHARE = "can_share value does not match in AnVIL"
    ERROR_DIFFERENT_CAN_COMPUTE = "can_compute value does not match in AnVIL"
    # Set up allowed errors.
    allowed_errors = (
        ERROR_NO_ACCESS_IN_ANVIL,
        ERROR_DIFFERENT_ACCESS,
        ERROR_DIFFERENT_CAN_SHARE,
        ERROR_DIFFERENT_CAN_COMPUTE,
    )
