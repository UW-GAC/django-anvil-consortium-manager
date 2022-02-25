# Python firecloud API bindings
# https://github.com/broadinstitute/fiss/blob/master/firecloud/api.py
#
# These don't work with python3.10, don't allow us to do everything we need,
# and have some dependency resolution issues with this project. Therefore, we'll
# have to reproduce some of the API to make the calls we would like to make. Alas.
import google.auth
from google.auth.transport.requests import AuthorizedSession

# Will eventually want to make this a setting.
ANVIL_API_ENDPOINT = "https://api.firecloud.org/api/"


class AnVILAPISession(AuthorizedSession):
    def __init__(self, endpoint=ANVIL_API_ENDPOINT):
        self.credentials = google.auth.default(
            [
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/userinfo.email",
            ]
        )[0]
        super().__init__(self.credentials)
        self.endpoint = endpoint

    def get_group(self, group_name):
        url = self.endpoint + "groups/" + group_name
        print(url)
        return self.get(url)
