# Python firecloud API bindings
# https://github.com/broadinstitute/fiss/blob/master/firecloud/api.py
#
# These don't work with python3.10, don't allow us to do everything we need,
# and have some dependency resolution issues with this project. Therefore, we'll
# have to reproduce some of the API to make the calls we would like to make. Alas.
import google.auth
from google.auth.transport.requests import AuthorizedSession

# Will eventually want to make this a setting.
ANVIL_API_ENTRY_POINT = "https://api.firecloud.org/api/"


class AnVILAPISession(AuthorizedSession):
    def __init__(self, entry_point=ANVIL_API_ENTRY_POINT):
        self.credentials = google.auth.default(
            [
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/userinfo.email",
            ]
        )[0]
        super().__init__(self.credentials)
        self.entry_point = entry_point

    def get(self, method, *args, **kwargs):
        url = self.entry_point + method
        response = super().get(url, *args, **kwargs)
        # Handle common error codes here.
        if response.status_code == 403:
            raise AnVILAPIError403(response)
        elif response.status_code == 404:
            raise AnVILAPIError404(response)
        elif response.status_code == 500:
            raise AnVILAPIError500(response)
        return response

    def post(self, method, *args, **kwargs):
        url = self.entry_point + method
        response = super().post(url, *args, **kwargs)
        print(response)
        if response.status_code == 409:
            raise AnVILAPIError409(response)
        if response.status_code == 500:
            raise AnVILAPIError500(response)
        return response

    def delete(self, method, *args, **kwargs):
        url = self.entry_point + method
        response = super().delete(url, *args, **kwargs)
        if response.status_code == 403:
            raise AnVILAPIError403(response)
        if response.status_code == 404:
            raise AnVILAPIError404(response)
        if response.status_code == 409:
            raise AnVILAPIError409(response)
        if response.status_code == 500:
            raise AnVILAPIError500(response)
        return response

    def get_group(self, group_name):
        method = "groups/" + group_name
        return self.get(method)

    def create_group(self, group_name):
        method = "groups/" + group_name
        return self.post(method)

    def delete_group(self, group_name):
        method = "groups/" + group_name
        return self.delete(method)


# Exceptions for working with the API.
class AnVILAPIError(Exception):
    """Base class for all exceptions in this module."""

    def __init__(self, response):
        super().__init__(response.json()["message"])
        self.status_code = response.status_code
        self.response = response


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
