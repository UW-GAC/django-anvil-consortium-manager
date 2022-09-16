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
        """Add a record that is on ANVIL but is not in the app."""
        self.not_in_app.add(record)

    def add_error(self, record, error):
        """Add a record from the app that has an error in the audit."""
        if error not in self.allowed_errors:
            raise ValueError("'{}' is not an allowed error.".format(error))
        if record in self.errors:
            self.errors[record].append(error)
        else:
            self.errors[record] = [error]

    def add_verified(self, record):
        """Add a record that has been verified against AnVIL."""
        if record in self.errors:
            raise ValueError("{} has reported errors.".format(record))
        self.verified.add(record)

    def get_verified(self):
        """Return a set of the verified records."""
        return self.verified

    def get_errors(self):
        """Return the a dictionary of records and the errors that they had."""
        return self.errors

    def get_not_in_app(self):
        """Return a list of records that are on AnVIL but not in the app."""
        return self.not_in_app

    def ok(self):
        """Check if the audit results are ok."""
        return not self.errors and not self.not_in_app


class BillingProjectAuditResults(AnVILAuditResults):
    """Class to hold audit results for BillingProjects."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    # Set up allowed errors.
    allowed_errors = ERROR_NOT_IN_ANVIL


class AccountAuditResults(AnVILAuditResults):
    """Class to hold audit results for Accounts."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    # Set up allowed errors.
    allowed_errors = ERROR_NOT_IN_ANVIL


class ManagedGroupAuditResults(AnVILAuditResults):
    """Class to hold audit results for ManagedGroups."""

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
    """Class to hold audit results for the membership of a single ManagedGroup."""

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
    """Class to hold audit results for Workspaces."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"
    ERROR_NOT_OWNER_ON_ANVIL = "Not an owner on AnVIL"
    ERROR_DIFFERENT_AUTH_DOMAINS = "Has different auth domains on AnVIL"
    # Set up allowed errors.
    allowed_errors = (
        ERROR_NOT_IN_ANVIL,
        ERROR_NOT_OWNER_ON_ANVIL,
        ERROR_DIFFERENT_AUTH_DOMAINS,
    )
