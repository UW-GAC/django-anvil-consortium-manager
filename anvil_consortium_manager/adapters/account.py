"""Contains base adapter for accounts."""

from abc import ABC

from django.conf import settings
from django.utils.module_loading import import_string


class BaseAccountAdapter(ABC):
    """Base class to inherit when customizing the account adapter."""

    # def get_str(self, account):
    #     """Set the custom string method for Accounts.
    #
    #     This method can be extended to show informatiom from the user profile linked to the Account.
    #     """
    #     return str(account)


def get_account_adapter():
    adapter = import_string(settings.ANVIL_ACCOUNT_ADAPTER)
    return adapter
