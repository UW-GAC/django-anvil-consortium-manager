from django.core.cache import caches

from ... import app_settings


class AuditCacheClearTestMixin:
    def tearDown(self):
        super().tearDown()
        caches[app_settings.AUDIT_CACHE].clear()
