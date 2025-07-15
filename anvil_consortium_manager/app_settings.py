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
        return getattr(settings, self.prefix + name, default)

    @property
    def API_SERVICE_ACCOUNT_FILE(self):
        """The path to the service account to use for managing access on AnVIL. Required."""
        x = self._setting("API_SERVICE_ACCOUNT_FILE")
        if not x:
            raise ImproperlyConfigured("ANVIL_API_SERVICE_ACCOUNT_FILE is required in settings.py")
        return x

    @property
    def WORKSPACE_ADAPTERS(self):
        """Workspace adapters. Required."""
        x = self._setting("WORKSPACE_ADAPTERS")
        if not x:
            msg = (
                "ANVIL_WORKSPACE_ADAPTERS must specify at least one adapter. Did you mean to use "
                "the default `anvil_consortium_manager.adapters.default.DefaultWorkspaceAdapter`?"
            )
            raise ImproperlyConfigured(msg)
        return x

    @property
    def ACCOUNT_ADAPTER(self):
        """Account adapter. Default: anvil_consortium_manager.adapters.default.DefaultAccountAdapter."""
        return self._setting("ACCOUNT_ADAPTER", "anvil_consortium_manager.adapters.default.DefaultAccountAdapter")

    @property
    def MANAGED_GROUP_ADAPTER(self):
        """ManagedGroup adapter. Default: anvil_consortium_manager.adapters.default.DefaultManagedGroupAdapter."""
        return self._setting(
            "MANAGED_GROUP_ADAPTER", "anvil_consortium_manager.adapters.default.DefaultManagedGroupAdapter"
        )

    @property
    def AUDIT_CACHE(self):
        """Name of the cache to use for audit caches. Default: "default"."""
        x = self._setting("AUDIT_CACHE")
        if not x:
            raise ImproperlyConfigured("ANVIL_AUDIT_CACHE is required in settings.py")
        return x


_app_settings = AppSettings("ANVIL_")


def __getattr__(name):
    # See https://peps.python.org/pep-0562/
    return getattr(_app_settings, name)
