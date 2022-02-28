# Python firecloud API bindings
# https://github.com/broadinstitute/fiss/blob/master/firecloud/api.py
#
# These don't work with python3.10, don't allow us to do everything we need,
# and have some dependency resolution issues with this project. Therefore, we'll
# have to reproduce some of the API to make the calls we would like to make. Alas.
import json

import google.auth
from google.auth.transport.requests import AuthorizedSession


class AnVILAPIClient:
    # Class variable for auth session.
    auth_session = None

    def __init__(self):
        if AnVILAPIClient.auth_session is None:
            # TODO: Think about how to set the credentials as a project settings, and if it's necessary.
            # Do we need to think about refreshing the credentials/session?
            credentials = google.auth.default(
                [
                    "https://www.googleapis.com/auth/userinfo.profile",
                    "https://www.googleapis.com/auth/userinfo.email",
                ]
            )[0]
            AnVILAPIClient.auth_session = AnVILAPISession(credentials)

    def get_group(self, group_name):
        method = "groups/" + group_name
        return self.auth_session.get(method, 200)

    def create_group(self, group_name):
        method = "groups/" + group_name
        return self.auth_session.post(method, 201)

    def delete_group(self, group_name):
        method = "groups/" + group_name
        return self.auth_session.delete(method, 204)

    def get_workspace(self, workspace_namespace, workspace_name):
        method = "workspaces/" + workspace_namespace + "/" + workspace_name
        return self.auth_session.get(method, 200)

    def create_workspace(self, workspace_namespace, workspace_name):
        method = "workspaces"
        body = {
            "namespace": workspace_namespace,
            "name": workspace_name,
            "attributes": {},
        }
        return self.auth_session.post(method, 201, json=body)

    def delete_workspace(self, workspace_namespace, workspace_name):
        method = "workspaces/" + workspace_namespace + "/" + workspace_name
        return self.auth_session.delete(method, 202)

    def update_workspace_acl(self, workspace_namespace, workspace_name, acl_updates):
        method = (
            "workspaces/"
            + workspace_namespace
            + "/"
            + workspace_name
            + "/acl?inviteUsersNotFound=false"
        )
        # False here means do not invite unregistered users.
        updates = json.dumps(acl_updates)
        return self.auth_session.patch(
            method, 200, headers={"Content-type": "application/json"}, data=updates
        )


class AnVILAPISession(AuthorizedSession):

    # May eventually want to make this a setting?
    entry_point = "https://api.firecloud.org/api/"

    def get(self, method, success_code, *args, **kwargs):
        url = self.entry_point + method
        response = super().get(url, *args, **kwargs)
        self._handle_response(success_code, response)
        return response

    def post(self, method, success_code, *args, **kwargs):
        url = self.entry_point + method
        response = super().post(url, *args, **kwargs)
        print(response)
        self._handle_response(success_code, response)
        return response

    def delete(self, method, success_code, *args, **kwargs):
        url = self.entry_point + method
        response = super().delete(url, *args, **kwargs)
        self._handle_response(success_code, response)
        return response

    def patch(self, method, success_code, *args, **kwargs):
        url = self.entry_point + method
        response = super().patch(url, *args, **kwargs)
        self._handle_response(success_code, response)
        return response

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
    """Base class for all exceptions in this module."""

    def __init__(self, response):
        super().__init__(response.json()["message"])
        self.status_code = response.status_code
        self.response = response


class AnVILAPIError400(AnVILAPIError):
    """Exception for a 400 Bad Request response."""

    def __init__(self, response):
        assert response.status_code == 400
        super().__init__(response)


class AnVILAPIError403(AnVILAPIError):
    """Exception for a Forbidden 403 response."""

    def __init__(self, response):
        assert response.status_code == 403
        super().__init__(response)


class AnVILAPIError404(AnVILAPIError):
    """Exception for a 404 Not Found response."""

    def __init__(self, response):
        assert response.status_code == 404
        super().__init__(response)


class AnVILAPIError409(AnVILAPIError):
    """Exception for a 409 response."""

    def __init__(self, response):
        assert response.status_code == 409
        super().__init__(response)


class AnVILAPIError500(AnVILAPIError):
    """Exception for a 500 Internal Error response."""

    def __init__(self, response):
        assert response.status_code == 500
        super().__init__(response)
