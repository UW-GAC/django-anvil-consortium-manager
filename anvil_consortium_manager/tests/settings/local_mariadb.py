import os

from .test import *  # noqa

# Change database settings
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DBNAME", default="anvil_consortium_manager"),
        "USER": os.getenv("DBUSER", default="django"),
        "PASSWORD": os.getenv("DBPASSWORD", default="password"),
        "HOST": os.getenv("DBHOST", default="127.0.0.1"),
        "PORT": os.getenv("DBPORT", default="3306"),
    }
}

for key in DATABASES["default"].keys():
    print("{} - {}".format(key, DATABASES["default"][key]))
