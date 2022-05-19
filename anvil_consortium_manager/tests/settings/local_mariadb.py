import os

from .test import *  # noqa

# Change database settings
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DBNAME", "anvil_consortium_manager"),
        "USER": os.environ.get("DBUSER", "django"),
        "PASSWORD": os.environ.get("DBPASSWORD", "password"),
        "HOST": os.environ.get("DBHOST", "127.0.0.1"),
        "PORT": os.environ.get("DBPORT", "3306"),
    }
}

for key in DATABASES["default"].keys():
    print("{} - {}".format(key, DATABASES["default"][key]))
