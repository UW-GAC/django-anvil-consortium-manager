from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    name = "example_site.users"
    verbose_name = _("Users")

    def ready(self):
        try:
            import example_site.users.signals  # noqa F401
        except ImportError:
            pass
