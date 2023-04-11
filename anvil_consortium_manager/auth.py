from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType

from .models import AnVILProjectManagerAccess


class AnVILConsortiumManagerViewRequired(PermissionRequiredMixin):
    """AnVIL global app view permission required mixin"""

    def get_permission_required(self):
        apm_content_type = ContentType.objects.get_for_model(AnVILProjectManagerAccess)
        perm_required = f"{apm_content_type.app_label}.{AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME}"
        return (perm_required,)


class AnVILConsortiumManagerEditRequired(PermissionRequiredMixin):
    """AnVIL global app edit permission required mixin"""

    def get_permission_required(self):
        apm_content_type = ContentType.objects.get_for_model(AnVILProjectManagerAccess)
        perm_required = f"{apm_content_type.app_label}.{AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME}"
        return (perm_required,)


class AnVILConsortiumManagerAccountLinkRequired(PermissionRequiredMixin):
    """AnVIL global app account link permission required mixin"""

    def get_permission_required(self):
        apm_content_type = ContentType.objects.get_for_model(AnVILProjectManagerAccess)
        perm_required = f"{apm_content_type.app_label}.{AnVILProjectManagerAccess.ACCOUNT_LINK_PERMISSION_CODENAME}"
        return (perm_required,)
