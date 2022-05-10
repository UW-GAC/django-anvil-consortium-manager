from .test import *  # noqa

# Change database settings
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "anvil_consortium_manager",
        "USER": "root",
        "PASSWORD": "rootpw",
        "HOST": "127.0.0.1",
        "PORT": "3306",
    }
}
