"""
With these settings, tests run faster.
"""

from .base import *  # noqa
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="w5S8S9eqW5ZqWXPnsCpgbOkcOtajCMmRDjakwXR39lbmVDSunZPwiSV80jSaVBdL",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Your stuff...
# ------------------------------------------------------------------------------

# Required for coverage to work
TEMPLATES[0]["OPTIONS"]["debug"] = True  # noqa

# Path to the service account to use for managing access.
# Because the calls are mocked, we don't need to set this.
ANVIL_API_SERVICE_ACCOUNT_FILE = "foo"

# In test set the admin login url so we can
# successfully test redirect to login for non-logged in users
LOGIN_URL = "admin:login"
