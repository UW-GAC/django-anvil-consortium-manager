"""Contains custom exceptions used by this app."""


class AnVILNotWorkspaceOwnerError(Exception):
    """Exception to be raised when the app account is not the owner of a workspace on AnVIL."""


class AnVILNotGroupAdminError(Exception):
    """Exception to be raised when the app account is not the admin of a group on AnVIL."""


class AnVILNotGroupMemberError(Exception):
    """Exception to be raised when the app account is not a member or admin of a group on AnVIL."""


class AnVILAlreadyImported(Exception):
    """Exception to be raised when an AnVIL resource has already been imported into Django."""


class AnVILRemoveAccountFromGroupError(Exception):
    """Exception to be raised when an account cannot be removed from a group on AnVIL."""


class AnVILGroupDeletionError(Exception):
    """Exception to be raised when a group was not properly deleted on AnVIL."""


class AnVILGroupNotFound(Exception):
    """Exception to be raised when a group is not found on AnVIL."""


class AnVILAuditError(Exception):
    """Base exception to be raised when an AnVIL audit fails."""


class AnVILAuditDoesNotExistInAppError(AnVILAuditError):
    """Exception to be raised when a record(s) exists on AnVIL but not in the app."""


class AnVILAuditDoesNotExistInAnVILError(AnVILAuditError):
    """Exception to be raised when a record(s) exists in the app but not on AnVIL."""
