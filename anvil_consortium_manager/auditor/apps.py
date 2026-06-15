from django.apps import AppConfig
from django.contrib.auth.signals import user_logged_in


class AuditorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "anvil_consortium_manager.auditor"

    def ready(self):
        from .signals import check_anvil_audits_on_login

        user_logged_in.connect(check_anvil_audits_on_login)
