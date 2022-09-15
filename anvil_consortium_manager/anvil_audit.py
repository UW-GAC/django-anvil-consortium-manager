"""Classes handling auditing of information in the Django database against AnVIL."""


class AnVILAuditResults:
    """Base class to store audit results from AnVIL."""

    ERROR_NOT_IN_ANVIL = "Not in AnVIL"

    def __init__(self):
        self.verified = set()
        self.errors = {}
        self.not_in_app = set()

    def add_not_in_app(self, record):
        """Add a record that is on ANVIL but is not in the app."""
        self.not_in_app.add(record)

    def add_error(self, record, error):
        """Add a record from the app that has an error in the audit."""
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


class BillingProjectAuditResults(AnVILAuditResults):
    """Class to hold audit results for BillingProjects."""


class AccountAuditResults(AnVILAuditResults):
    """Class to hold audit results for Accounts."""


class ManagedGroupAuditResults(AnVILAuditResults):
    """Class to hold audit results for ManagedGroups."""

    ERROR_DIFFERENT_ROLE = "App has a different role in this group."


class WorkspaceAuditResults(AnVILAuditResults):
    """Class to hold audit results for Workspaces."""

    ERROR_NOT_OWNER_ON_ANVIL = "Not an owner on AnVIL"
    ERROR_DIFFERENT_AUTH_DOMAINS = "Has different auth domains on AnVIL"
