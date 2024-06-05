from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# The following settings are used to configure the Anvil Consortium Manager.
# Users should set or override these values in their Django project's settings.py file.
# This file provides defaults for some of the settings.

# Required settings
# -----------------

# The path to the service account to use for managing access on AnVIL.
try:
    ANVIL_API_SERVICE_ACCOUNT_FILE = getattr(settings, "ANVIL_API_SERVICE_ACCOUNT_FILE")
except AttributeError:
    raise ImproperlyConfigured("ANVIL_API_SERVICE_ACCOUNT_FILE is required in settings.py")

# Workspace adapters.
try:
    ANVIL_WORKSPACE_ADAPTERS = getattr(settings, "ANVIL_WORKSPACE_ADAPTERS")
except AttributeError:
    raise ImproperlyConfigured("ANVIL_WORKSPACE_ADAPTERS is required in settings.py")

# Optional settings
# -----------------

# Subject line for AnVIL account verification emails.
ANVIL_ACCOUNT_LINK_EMAIL_SUBJECT = getattr(
    settings, "ANVIL_ACCOUNT_LINK_EMAIL_SUBJECT", "Verify your AnVIL account email"
)

# The URL for AccountLinkVerify view redirect
ANVIL_ACCOUNT_LINK_REDIRECT = getattr(settings, "ANVIL_ACCOUNT_LINK_REDIRECT", settings.LOGIN_REDIRECT_URL)

# If desired, specify the email address to send an email to after a user verifies an account.
# Set to None to disable (default).
ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL = getattr(settings, "ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL", None)

# Account adapter.
ANVIL_ACCOUNT_ADAPTER = getattr(
    settings, "ANVIL_ACCOUNT_ADAPTER", "anvil_consortium_manager.adapters.default.DefaultAccountAdapter"
)
