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


class AnVILGroupNotFound(Exception):
    """Exception to be raised when a group is not found on AnVIL."""


class WorkspaceAccessUnknownError(Exception):
    """Exception to be raised when the app cannot determine the access to a workspace."""


class WorkspaceAccessSharingUnknownError(WorkspaceAccessUnknownError):
    """Exception to be raised when the app cannot determine the access to a workspace due to sharing."""


class WorkspaceAccessAuthorizationDomainUnknownError(WorkspaceAccessUnknownError):
    """Exception to be raised when the app cannot determine the access to a workspace due to auth domain membership."""
