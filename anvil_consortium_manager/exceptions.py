"""Contains custom exceptions used by this app."""


class AnVILNotWorkspaceOwnerError(Exception):
    """Exception to be raised when the app account is not the owner of a workspace on AnVIL."""

    pass


class AnVILNotGroupAdminError(Exception):
    """Exception to be raised when the app account is not the admin of a group on AnVIL."""

    pass


class AnVILNotGroupMemberError(Exception):
    """Exception to be raised when the app account is not a member or admin of a group on AnVIL."""

    pass


class AnVILAlreadyImported(Exception):
    """Exception to be raised when an AnVIL resource has already been imported into Django."""

    pass


class AnVILRemoveAccountFromGroupError(Exception):
    """Exception to be raised when an account cannot be removed from a group on AnVIL."""


class AnVILGroupDeletionError(Exception):
    """Exception to be raised when a group was not properly deleted on AnVIL."""


class AnVILGroupNotFound(Exception):
    """Exception to be raised when a group is not found on AnVIL."""
