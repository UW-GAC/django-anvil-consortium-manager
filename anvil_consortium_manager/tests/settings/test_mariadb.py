from .test import *  # noqa

# Change database settings
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "anvil_consortium_manager",
        "USER": "django",
        "PASSWORD": "password",
        "HOST": "localhost",
        "PORT": "3306",
    }
}
