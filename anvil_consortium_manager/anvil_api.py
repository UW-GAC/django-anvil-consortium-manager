"""Python bindings for the AnVIL/Terra/Firecloud API

See API documentation for more information about each method: https://api.firecloud.org/#/.

"""
# Python firecloud API bindings
# https://github.com/broadinstitute/fiss/blob/master/firecloud/api.py
#
# These don't work with python3.10, don't allow us to do everything we need,
# and have some dependency resolution issues with this project. Therefore, we'll
# have to reproduce some of the API to make the calls we would like to make. Alas.
import json
import logging

from django.conf import settings
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class AnVILAPIClient:
    """Client for calling the AnVIL API.

    See the AnVIL/Terra Swagger documentation for more info (https://api.firecloud.org/#/).

    Attributes:
        auth_session: An ``AnVILAPISession`` instance.
        firecloud_entry_point (str): The entry point for the Firecloud API.
    """

    # Class variable for auth session. Set in init method.
    auth_session = None
    firecloud_entry_point = "https://api.firecloud.org"

    def __init__(self):
        """Initialize a new AnVILAPIClient instance.

        If the ``auth_session`` attribute is ``None``, create a new ``AnVILAPISession`` using the crendetials file in
        ``settings.ANVIL_API_SERVICE_ACCOUNT_FILE. Store the ``AnVILAPISession`` in the ``auth_session`` class variable.
        This way, all instances should share the same authorized session.
        """
        if AnVILAPIClient.auth_session is None:

            credentials = service_account.Credentials.from_service_account_file(
                settings.ANVIL_API_SERVICE_ACCOUNT_FILE
            )
            scoped_credentials = credentials.with_scopes(
                [
                    "https://www.googleapis.com/auth/userinfo.profile",
                    "https://www.googleapis.com/auth/userinfo.email",
                ]
            )
            AnVILAPIClient.auth_session = AnVILAPISession(scoped_credentials)

    def status(self):
        """Get the current AnVIL status.

        Calls the /status GET method.

        Returns:
            requests.Response
        """
        url = self.firecloud_entry_point + "/status"
        return self.auth_session.get(url, 200)

    def me(self):
        """Get the current authenticated user.

        Calls the /me GET method.

        Returns:
            requests.Response
        """
        url = self.firecloud_entry_point + "/me?userDetailsOnly=true"
        return self.auth_session.get(url, 200)

    def get_proxy_group(self, email):
        """Get the proxy group created for a specific AnVIL account email.

        Calls the /api/proxyGroup GET method.

        Args:
            email (str): Email address associated with the AnVIL account

        Returns:
            requests.Response
        """
        url = self.firecloud_entry_point + "/api/proxyGroup/" + email
        return self.auth_session.get(url, 200)

    def get_billing_project(self, billing_project):
        """Get information about the specified billing project.

        Calls the /api/billing/v2 GET method.

        Args:
            billing_project (str): Name of the billing project.

        Returns:
            requests.Response
        """
        url = self.firecloud_entry_point + "/api/billing/v2/" + billing_project
        return self.auth_session.get(url, 200)

    def get_groups(self):
        """Get a list of groups that the authenticated account is part of.

        Calls the /api/groups GET method.

        Returns:
            requests.Response
        """
        url = self.firecloud_entry_point + "/api/groups"
        return self.auth_session.get(url, 200)

    def get_group(self, group_name):
        """Get information about a group on AnVIL.

        Calls the /api/groups/{group_name} GET method.

        Args:
            group_name (str): Name of the AnVIL group to get information about.

        Returns:
            requests.Response
        """
        url = self.firecloud_entry_point + "/api/groups/" + group_name
        return self.auth_session.get(url, 200)

    def create_group(self, group_name):
        """Create a new group on AnVIL.

        Calls the /api/groups/{group_name} POST method.

        Args:
            group_name (str): Name of the AnVIL group to create.

        Returns:
            requests.Response
        """
        url = self.firecloud_entry_point + "/api/groups/" + group_name
        return self.auth_session.post(url, 201)

    def delete_group(self, group_name):
        """Delete a group on AnVIL.

        Calls the /api/groups/{group_name} DELETE method.

        Args:
            group_name (str): Name of the group to delete. You must be an admin of the group to use this method.

        Returns:
            requests.Response
        """
        url = self.firecloud_entry_point + "/api/groups/" + group_name
        return self.auth_session.delete(url, 204)

    def add_user_to_group(self, group_name, role, user_email):
        """Add a user to a group on AnVIL. You must be an admin of the group to use this method.

        Calls the /api/groups/{group_name}/{role}/{user_email} PUT method.

        Args:
            group_name (str): Name of the group to add this user to.
            role (str): Role that this user should have (either MEMBER or ADMIN).
            user_email (str): AnVIL email account of the user to add.

        Returns:
            requests.Response
        """
        url = (
            self.firecloud_entry_point
            + "/api/groups/"
            + group_name
            + "/"
            + role
            + "/"
            + user_email
        )
        return self.auth_session.put(url, 204)

    def remove_user_from_group(self, group_name, role, user_email):
        """Remove a user from a group on AnVIL. You must be an admin of the group to use this method.

        Calls the /api/groups/{group_name}/{role}/{user_email} DELETE method.

        Args:
            group_name (str): Name of the group to remvoe this user from.
            role (str): Role that this user should be removed from (either MEMBER or ADMIN).
            user_email (str): AnVIL email account of the user to add.

        Returns:
            requests.Response
        """
        url = (
            self.firecloud_entry_point
            + "/api/groups/"
            + group_name
            + "/"
            + role
            + "/"
            + user_email
        )
        return self.auth_session.delete(url, 204)

    def list_workspaces(self, fields=None):
        """Get a list of workspaces that you have access to on AnVIL.

        Calls the /api/workspaces GET method.

        Args:
            fields (list): List of strings indicating which fields to return. See API documentation
            (https://api.firecloud.org/#/Workspaces/getWorkspace) for more details.

        Returns:
            requests.Response
        """
        url = self.firecloud_entry_point + "/api/workspaces"
        if fields:
            return self.auth_session.get(url, 200, params={"fields": fields})
        else:
            return self.auth_session.get(url, 200)

    def get_workspace(self, workspace_namespace, workspace_name):
        """Get information about a specific workspace on AnVIL.

        Calls the /api/workspaces/{workspace_namespace}/{workspace_name} GET method.

        Args:
            workspace_namespace (str): The namespace (or billing project) of the workspace.
            workspace_name (str):  The name of the workspace.

        Returns:
            requests.Response
        """
        url = (
            self.firecloud_entry_point
            + "/api/workspaces/"
            + workspace_namespace
            + "/"
            + workspace_name
        )
        return self.auth_session.get(url, 200)

    def create_workspace(
        self, workspace_namespace, workspace_name, authorization_domains=[]
    ):
        """Create a workspace on AnVIL.

        Calls the /api/create_workspace POST method.

        Args:
            workspace_namespace (str): The namespace (or billing project) in which to create the workspace.
            workspace_name (str): The name of the workspace to create.
            authorization_domains (str): If desired, a list of group names that should be used as the authorization
                domain for this workspace.

        Returns:
            requests.Response
        """
        url = self.firecloud_entry_point + "/api/workspaces"
        body = {
            "namespace": workspace_namespace,
            "name": workspace_name,
            "attributes": {},
        }
        if not isinstance(authorization_domains, list):
            raise ValueError("authorization_domains must be a list.")

        # Add authorization domains.
        if authorization_domains:
            auth_domain = [{"membersGroupName": g} for g in authorization_domains]
            body["authorizationDomain"] = auth_domain

        return self.auth_session.post(url, 201, json=body)

    def clone_workspace(
        self,
        existing_workspace_namespace,
        existing_workspace_name,
        cloned_workspace_namespace,
        cloned_workspace_name,
        authorization_domains=[],
    ):
        """Clone an existing workspace on AnVIL.

        Calls the /api/create_workspace POST method.

        Args:
            existing_workspace_namespace (str): The namespace (or billing project) of the
                existing workspace to clone.
            existing_workspace_name (str): The name of the existing workspace to clone.
            cloned_workspace_namespace (str): The namespace (or billing project) in which
                to create the cloned workspace.
            cloned_workspace_name (str): The name of the cloned workspace to create.
            authorization_domains (str): If desired, a list of group names that should be
                used as the authorization domain for this workspace. This must include the
                authorization domains of the existing workspace.

        Returns:
            requests.Response
        """
        url = (
            self.firecloud_entry_point
            + "/api/workspaces/{namespace}/{name}/clone".format(
                namespace=existing_workspace_namespace,
                name=existing_workspace_name,
            )
        )
        body = {
            "namespace": cloned_workspace_namespace,
            "name": cloned_workspace_name,
            "attributes": {},
        }
        if not isinstance(authorization_domains, list):
            raise ValueError("authorization_domains must be a list.")

        # Add authorization domains.
        if authorization_domains:
            auth_domain = [{"membersGroupName": g} for g in authorization_domains]
            body["authorizationDomain"] = auth_domain

        return self.auth_session.post(url, 201, json=body)

    def delete_workspace(self, workspace_namespace, workspace_name):
        """Delete a workspace on AnVIL. You must be an owner of the workspace to use this method.

        Calls the /api/workspaces/{workspace_namespace}/{workspace_name} DELETE method.

        Args:
            workspace_namespace (str): The namespace (or billing project) of the workspace to be deleted.
            workspace_name (str): The name of the workspace to delete.

        Returns:
            requests.Response
        """
        url = (
            self.firecloud_entry_point
            + "/api/workspaces/"
            + workspace_namespace
            + "/"
            + workspace_name
        )
        return self.auth_session.delete(url, 202)

    def get_workspace_acl(self, workspace_namespace, workspace_name):
        """Get the list of access controls for the workspace.
        This list includes both users and groups that have access.
        You must be an owner of this workspace to use this method.

        Calls the /api/workspaces/{workspace_namespace}/{workspace_name}/acl GET method.

        Args:
            workspace_namespace (str): The namespace (or billing project) of the workspace.
            workspace_name (str): The name of the workspace.

        Returns:
            requests.Response
        """
        url = (
            self.firecloud_entry_point
            + "/api/workspaces/"
            + workspace_namespace
            + "/"
            + workspace_name
            + "/acl"
        )
        return self.auth_session.get(url, 200)

    def update_workspace_acl(self, workspace_namespace, workspace_name, acl_updates):
        """Update the access controls for a workspace for a set of users and/or groups.
        You must be an owner of the workspace to use this method.

        Calls the /api/workspaces/{workspace_namespace}/{workspace_name} PATCH method.

        Args:
            workspace_namespace (str): The namespace (or billing project) of the workspace.
            workspace_name (str): The name of the workspace.
            acl_updates (list of dict): A list of dictionaries with access updates to make. Each dictionary should have
                the following keys: "email", "accessLevel", "canShare", and "canCompute".

        Returns:
            requests.Response
        """
        url = self.firecloud_entry_point + (
            "/api/workspaces/"
            + workspace_namespace
            + "/"
            + workspace_name
            + "/acl?inviteUsersNotFound=false"
        )
        # False here means do not invite unregistered users.
        updates = json.dumps(acl_updates)
        return self.auth_session.patch(
            url, 200, headers={"Content-type": "application/json"}, data=updates
        )


class AnVILAPISession(AuthorizedSession):
    """An authorized session for use with the AnVIL API.

    Attributes:
        entry_point (str): The API entry point.
    """

    def get(self, url, success_code=None, *args, **kwargs):
        """Make a get request to the specified method after prepending ``entry_point``.

        Add the request and the response to the log.

        If ``success_code`` is not ``None``, check that the response code matches ``success_code``. If they do not
        match, raise an ``AnVILAPIError`` exception (or one of its subclasses).

        Args:
            url (str): the API url to call
            success_code (int, optional): The
            *args: Passed to ``AuthorizedSession.get``
            **kwargs: Passed to ``AuthorizedSession.get``

        Returns:
            requests.Response

        Raises:
            AnVILAPIError: If the response code is not the expected ``success_code``. May be a subclass based on the
            response code (e.g., ``AnVILAPIError404``).
        """
        self._log_request("GET", url, *args, **kwargs)
        response = super().get(url, *args, **kwargs)
        self._log_response(response)
        if success_code is not None:
            self._handle_response(success_code, response)
        return response

    def post(self, url, success_code=None, *args, **kwargs):
        """Make a post request to the specified method after prepending ``entry_point``.

        Add the request and the response to the log.

        If ``success_code`` is not ``None``, check that the response code matches ``success_code``. If they do not
        match, raise an ``AnVILAPIError`` exception (or one of its subclasses).

        Args:
            method (str): the API method to call
            success_code (int, optional): The
            *args: Passed to ``AuthorizedSession.post``
            **kwargs: Passed to ``AuthorizedSession.post``

        Returns:
            requests.Response

        Raises:
            AnVILAPIError: If the response code is not the expected ``success_code``. May be a subclass based on the
            response code (e.g., ``AnVILAPIError404``).
        """
        self._log_request("POST", url, *args, **kwargs)
        response = super().post(url, *args, **kwargs)
        self._log_response(response)
        if success_code is not None:
            self._handle_response(success_code, response)
        return response

    def delete(self, url, success_code=None, *args, **kwargs):
        """Make a delete request to the specified method after prepending ``entry_point``.

        Add the request and the response to the log.

        If ``success_code`` is not ``None``, check that the response code matches ``success_code``. If they do not
        match, raise an ``AnVILAPIError`` exception (or one of its subclasses).

        Args:
            method (str): the API method to call
            success_code (int, optional): The
            *args: Passed to ``AuthorizedSession.delete``
            **kwargs: Passed to ``AuthorizedSession.delete``

        Returns:
            requests.Response

        Raises:
            AnVILAPIError: If the response code is not the expected ``success_code``. May be a subclass based on the
            response code (e.g., ``AnVILAPIError404``).
        """
        self._log_request("DELETE", url, *args, **kwargs)
        response = super().delete(url, *args, **kwargs)
        self._log_response(response)
        if success_code is not None:
            self._handle_response(success_code, response)
        return response

    def patch(self, url, success_code=None, *args, **kwargs):
        """Make a patch request to the specified method after prepending ``entry_point``.

        Add the request and the response to the log.

        If ``success_code`` is not ``None``, check that the response code matches ``success_code``. If they do not
        match, raise an ``AnVILAPIError`` exception (or one of its subclasses).

        Args:
            method (str): the API url to call
            success_code (int, optional): The
            *args: Passed to ``AuthorizedSession.patch``
            **kwargs: Passed to ``AuthorizedSession.patch``

        Returns:
            requests.Response

        Raises:
            AnVILAPIError: If the response code is not the expected ``success_code``. May be a subclass based on the
            response code (e.g., ``AnVILAPIError404``).
        """
        self._log_request("PATCH", url, *args, **kwargs)
        response = super().patch(url, *args, **kwargs)
        self._log_response(response)
        if success_code is not None:
            self._handle_response(success_code, response)
        return response

    def put(self, url, success_code=None, *args, **kwargs):
        """Make a put request to the specified method after prepending ``entry_point``.

        If ``success_code`` is not ``None``, check that the response code matches ``success_code``. If they do not
        match, raise an ``AnVILAPIError`` exception (or one of its subclasses).

        Args:
            method (str): the API url to call
            success_code (int, optional): The
            *args: Passed to ``AuthorizedSession.put``
            **kwargs: Passed to ``AuthorizedSession.put``

        Returns:
            requests.Response

        Raises:
            AnVILAPIError: If the response code is not the expected ``success_code``. May be a subclass based on the
            response code (e.g., ``AnVILAPIError404``).
        """
        self._log_request("PUT", url, *args, **kwargs)
        response = super().put(url, *args, **kwargs)
        self._log_response(response)
        if success_code is not None:
            self._handle_response(success_code, response)
        return response

    def _log_request(self, request_type, url, *args, **kwargs):
        """Log info about the request."""
        msg = "Starting request...\n  {request_type}: {url}\n  args: {args}\n  kwargs: {kwargs}".format(
            request_type=request_type, url=url, args=args, kwargs=kwargs
        )
        logger.info(msg)

    def _log_response(self, response):
        """Log info about the response."""
        msg = "Got response...\n  status_code: {status_code}\n  text: {text}".format(
            status_code=response.status_code, text=response.text
        )
        logger.info(msg)

    def _handle_response(self, success_code, response):
        """Checks for a successful response code and raises an Exception if the code is different."""
        # Check for standard error codes.
        if response.status_code == 400:
            raise AnVILAPIError400(response)
        if response.status_code == 403:
            raise AnVILAPIError403(response)
        if response.status_code == 404:
            raise AnVILAPIError404(response)
        if response.status_code == 409:
            raise AnVILAPIError409(response)
        if response.status_code == 500:
            raise AnVILAPIError500(response)
        elif response.status_code != success_code:
            raise AnVILAPIError(response)


# Exceptions for working with the API.
class AnVILAPIError(Exception):
    """An exception raised when an error occurred with the AnVIL API.

    Attributes:
        status_code (int): the status code fo the response
        response (requests.Response): the response object.
    """

    def __init__(self, response):
        """Create a new instance of the ``AnVILAPIError`` class.

        Args:
            response (requests.Response): The response returned by the AnVIL API.
        """
        try:
            msg = response.json()["message"]
        except Exception:
            msg = "other error"
        super().__init__(msg)
        self.status_code = response.status_code
        self.response = response


class AnVILAPIError400(AnVILAPIError):
    """An exception raised when an 400 Bad Request code was returned by the AnVIL API."""

    def __init__(self, response):
        assert response.status_code == 400
        super().__init__(response)


class AnVILAPIError403(AnVILAPIError):
    """An exception raised when an 403 Forbidden code was returned by the AnVIL API."""

    def __init__(self, response):
        assert response.status_code == 403
        super().__init__(response)


class AnVILAPIError404(AnVILAPIError):
    """An exception raised when an 404 Not Found code was returned by the AnVIL API."""

    def __init__(self, response):
        assert response.status_code == 404
        super().__init__(response)


class AnVILAPIError409(AnVILAPIError):
    """An exception raised when an 409 code was returned by the AnVIL API."""

    def __init__(self, response):
        assert response.status_code == 409
        super().__init__(response)


class AnVILAPIError500(AnVILAPIError):
    """An exception raised when an 500 code was returned by the AnVIL API."""

    def __init__(self, response):
        assert response.status_code == 500
        super().__init__(response)
