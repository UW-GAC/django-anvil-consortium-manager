from .. import app_settings
from .utils import check_cached_anvil_audits


def check_anvil_audits_on_login(sender, request, user, **kwargs):
    if not user.is_staff:
        return
    else:
        if app_settings.CHECK_AUDIT_CACHE_ON_LOGIN is True:
            check_cached_anvil_audits(request=request)
