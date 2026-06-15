from .. import app_settings
from ..models import AnVILProjectManagerAccess
from .utils import check_cached_anvil_audits


def check_anvil_audits_on_login(sender, request, user, **kwargs):
    staff_view_permission_codename = AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME
    has_staff_view_perms = user.has_perm("anvil_consortium_manager." + staff_view_permission_codename)
    if not has_staff_view_perms:
        return
    else:
        if app_settings.CHECK_AUDIT_CACHE_ON_LOGIN is True:
            check_cached_anvil_audits(request=request)
