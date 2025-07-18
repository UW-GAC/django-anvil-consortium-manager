"""
Settings file for example site.
"""

import os
from pathlib import Path

import environ

ROOT_DIR = Path(__file__).resolve(strict=True).parent.parent

# Optionally read environment variables from a .env file.
env = environ.Env()
if os.path.exists(str(ROOT_DIR / ".env")):
    env.read_env(str(ROOT_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = "9VCSwBhicTgg4AUMMbDvAC6ihzMb1h05URed7OwwyIb5jHQXAKzrJcMCNu3thS2l"
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ["*"]

# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "America/Los_Angeles"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-l10n
USE_L10N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True


# ADMIN
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = [
    # ("Your name", "your_email@example.com")
]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS


# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "db.sqlite3",
    }
}

# # https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "example_site.urls"

# APPS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "django.contrib.sites",
    "django.forms",
    # Third party apps
    "crispy_forms",
    "crispy_bootstrap5",
    "django_tables2",
    "fontawesomefree",  # icons
    "debug_toolbar",
    "django_extensions",  # useful extensions
    "simple_history",  # model history tracking - required for viewing in admin.
    "django_filters",
    # This app.
    "anvil_consortium_manager",
    "anvil_consortium_manager.auditor",
    # Autocomplete.
    # note these are supposed to come before django.contrib.admin.
    "dal",
    "dal_select2",
    # The example app.
    "example_site.app",
]


# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # Middleware for automatically populating user in django-simple-history.
    "simple_history.middleware.HistoryRequestMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = []
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(ROOT_DIR / "media")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#dirs
        "DIRS": ["example_site/templates"],
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
            ],
            "debug": False,
        },
    }
]


# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"verbose": {"format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s"}},
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

# Auditing uses a cache, so set your preferred cache backend.
CACHES = {
    # "default" is required if we are setting a cache.
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
    "anvil_audit_cache": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "anvil_audit_cache_table",
        "OPTIONS": {
            # This should be larger than the number of Workspaces + Groups + 4.
            "MAX_ENTRIES": 1000,  # Maximum number of entries in the cache.
        },
        "TIMEOUT": None,  # Cache entries never expire.
    },
}

# django-crispy-forms
# ------------------------------------------------------------------------------
# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"


# django-tables2
# ------------------------------------------------------------------------------
# https://django-tables2.readthedocs.io/en/latest/pages/custom-rendering.html?highlight=django_tables2_template#available-templates
DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap4.html"

# Auth
# ------------------------------------------------------------------------------
LOGIN_REDIRECT_URL = "home"

# django-debug-toolbar
# ------------------------------------------------------------------------------
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#internal-ips
INTERNAL_IPS = ["127.0.0.1"]


# django-anvil-consortium-manager
# ------------------------------------------------------------------------------
# Specify the path to the service account to use for managing access on AnVIL.
ANVIL_API_SERVICE_ACCOUNT_FILE = env("ANVIL_API_SERVICE_ACCOUNT_FILE")

# Specify the workspace adapters to use.
ANVIL_WORKSPACE_ADAPTERS = [
    "anvil_consortium_manager.adapters.default.DefaultWorkspaceAdapter",
    "example_site.app.adapters.CustomWorkspaceAdapter",
]

# Specify the URL for AccountLinkVerify view redirect
# ANVIL_ACCOUNT_LINK_REDIRECT = LOGIN_REDIRECT_URL  # Default

# Specify the subject for AnVIL account verification emails.
#  ANVIL_ACCOUNT_LINK_EMAIL_SUBJECT = "Verify your AnVIL account email"    # Default.

# If desired, specify the email address to send an email to after a user verifies an account.
# ANVIL_ACCOUNT_VERIFY_NOTIFICATION_EMAIL = "to@example.com"

# Account adapter.
# ANVIL_ACCOUNT_ADAPTER = "anvil_consortium_manager.adapters.default.DefaultAccountAdapter"  # Default.

# Specify the name of the cache set above.
ANVIL_AUDIT_CACHE = "anvil_audit_cache"
