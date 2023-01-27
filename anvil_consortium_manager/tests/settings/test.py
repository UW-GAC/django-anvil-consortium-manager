"""
Base test settings file.
"""
import os

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
# DEBUG = env.bool("DJANGO_DEBUG", False)
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "America/Los_Angeles"
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = "w5S8S9eqW5ZqWXPnsCpgbOkcOtajCMmRDjakwXR39lbmVDSunZPwiSV80jSaVBdL"
# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

INTERNAL_IPS = ["127.0.0.1"]
# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.{}".format(
            os.getenv("DBBACKEND", default="sqlite3")
        ),
        "NAME": os.getenv("DBNAME", default="anvil_consortium_manager"),
        "USER": os.getenv("DBUSER", default="django"),
        "PASSWORD": os.getenv("DBPASSWORD", default="password"),
        "HOST": os.getenv("DBHOST", default="127.0.0.1"),
        "PORT": os.getenv("DBPORT", default="3306"),
    }
}
print(DATABASES["default"]["ENGINE"])
# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "anvil_consortium_manager.tests.settings.urls"

# APPS
# ------------------------------------------------------------------------------
INSTALLED_APPS = [
    "dal",
    "dal_select2",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "django.forms",
    # Third party apps.
    "crispy_forms",
    "crispy_bootstrap5",
    "django_tables2",
    "fontawesomefree",  # icons
    # Your stuff: custom apps go here
    "anvil_consortium_manager",
    # Test app
    "anvil_consortium_manager.tests.test_app",
]


# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "anvil_consortium_manager.context_processors.workspace_adapter",
            ],
            "debug": True,  # Required for coverage to work.
        },
    }
]


# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"

# Since there are no templates for redirects in this app, specify the open URL.
LOGIN_URL = "test_login"

# Your stuff...
# ------------------------------------------------------------------------------

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# django-tables2 default template.
DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap4.html"

# Path to the service account to use for managing access.
# Because the calls are mocked, we don't need to set this.
ANVIL_API_SERVICE_ACCOUNT_FILE = "foo"
ANVIL_ACCOUNT_LINK_REDIRECT = "test_home"
ANVIL_ACCOUNT_LINK_EMAIL_SUBJECT = "account activation"

ANVIL_WORKSPACE_ADAPTERS = [
    "anvil_consortium_manager.adapters.default.DefaultWorkspaceAdapter",
]
ANVIL_ACCOUNT_ADAPTER = (
    "anvil_consortium_manager.adapters.default.DefaultAccountAdapter"
)
