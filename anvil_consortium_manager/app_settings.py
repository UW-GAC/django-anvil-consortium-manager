# App settings.
# Mostly follows django-allauth:
# https://github.com/pennersr/django-allauth/blob/main/allauth/app_settings.py

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class AppSettings(object):
    """Class to handle settings for django-anvil-consortium-manager."""

    def __init__(self, prefix):
        self.prefix = prefix

    def _setting(self, name, default=None):
        from django.conf import settings

        return getattr(settings, self.prefix + name, default)

    @property
    def API_SERVICE_ACCOUNT_FILE(self):
        """The path to the service account to use for managing access on AnVIL. Required."""
        x = self._setting("API_SERVICE_ACCOUNT_FILE")
        if not x:
            raise ImproperlyConfigured("ANVIL_API_SERVICE_ACCOUNT_FILE is required in settings.py")

    @property
    def WORKSPACE_ADAPTERS(self):
        """Workspace adapters. Required."""
        x = self._setting("WORKSPACE_ADAPTERS")
        if not x:
            raise ImproperlyConfigured("ANVIL_WORKSPACE_ADAPTERS is required in settings.py")

    @property
    def ACCOUNT_LINK_EMAIL_SUBJECT(self):
        """Subject line for AnVIL account verification emails. Default: 'Verify your AnVIL account email'"""
        return self._setting("ACCOUNT_LINK_EMAIL_SUBJECT", "Verify your AnVIL account email")

    @property
    def ACCOUNT_LINK_REDIRECT(self):
        """The URL for AccountLinkVerify view redirect. Default: settings.LOGIN_REDIRECT_URL."""
        return self._setting("ACCOUNT_LINK_REDIRECT", settings.LOGIN_REDIRECT_URL)

    @property
    def ACCOUNT_VERIFY_NOTIFICATION_EMAIL(self):
        """If desired, specify the email address to send an email to after a user verifies an account. Default: None.

        Set to None to disable (default).
        """
        return self._setting("ACCOUNT_VERIFY_NOTIFICATION_EMAIL", None)

    @property
    def ACCOUNT_ADAPTER(self):
        """Account adapter. Default: anvil_consortium_manager.adapters.default.DefaultAccountAdapter."""
        return self._setting("ACCOUNT_ADAPTER", "anvil_consortium_manager.adapters.default.DefaultAccountAdapter")


_app_settings = AppSettings("ANVIL_")


def __getattr__(name):
    # See https://peps.python.org/pep-0562/
    return getattr(_app_settings, name)


# The following settings are used to configure the Anvil Consortium Manager.
# Users should set or override these values in their Django project's settings.py file.
# This file provides defaults for some of the settings.

# Required settings
# -----------------

# # The path to the service account to use for managing access on AnVIL.
# try:
#     ANVIL_API_SERVICE_ACCOUNT_FILE = getattr(settings, "ANVIL_API_SERVICE_ACCOUNT_FILE")
# except AttributeError:
#     raise ImproperlyConfigured("ANVIL_API_SERVICE_ACCOUNT_FILE is required in settings.py")

# # Workspace adapters.
# try:
#     ANVIL_WORKSPACE_ADAPTERS = getattr(settings, "ANVIL_WORKSPACE_ADAPTERS")
# except AttributeError:
#     raise ImproperlyConfigured("ANVIL_WORKSPACE_ADAPTERS is required in settings.py")

# # Optional settings
# # -----------------

# # Subject line for AnVIL account verification emails.
# ANVIL_ACCOUNT_LINK_EMAIL_SUBJECT = getattr(
#     settings, "ANVIL_ACCOUNT_LINK_EMAIL_SUBJECT", "Verify your AnVIL account email"
# )

# # The URL for AccountLinkVerify view redirect
# ANVIL_ACCOUNT_LINK_REDIRECT = getattr(settings, "ANVIL_ACCOUNT_LINK_REDIRECT", settings.LOGIN_REDIRECT_URL)

# # If desired, specify the email address to send an email to after a user verifies an account.
# # Set to None to disable (default).
# ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL = getattr(settings, "ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL", None)

# # Account adapter.
# ANVIL_ACCOUNT_ADAPTER = getattr(
#     settings, "ANVIL_ACCOUNT_ADAPTER", "anvil_consortium_manager.adapters.default.DefaultAccountAdapter"
# )
