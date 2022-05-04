from .local import *  # noqa
from .local import env

# Change database settings
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DJANGO_DB_NAME", default="anvil_consortium_manager"),
        "USER": env("DJANGO_DB_USER", default="django"),
        "PASSWORD": env("DJANGO_DB_PASSWORD", default="password"),
        "HOST": env("DJANGO_DB_HOST", default="localhost"),
        "PORT": env("DJANGO_DB_HOST", default="3306"),
    }
}
