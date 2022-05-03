from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType

from .models import AnvilProjectManagerAccess


class AnvilConsortiumManagerViewRequired(PermissionRequiredMixin):
    """Anvil global app view permission required mixin"""

    def get_permission_required(self):
        apm_content_type = ContentType.objects.get_for_model(AnvilProjectManagerAccess)
        perm_required = f"{apm_content_type.app_label}.{AnvilProjectManagerAccess.VIEW_PERMISSION_CODENAME}"
        return (perm_required,)


class AnvilConsortiumManagerEditRequired(PermissionRequiredMixin):
    """Anvil global app edit permission required mixin"""

    def get_permission_required(self):
        apm_content_type = ContentType.objects.get_for_model(AnvilProjectManagerAccess)
        perm_required = f"{apm_content_type.app_label}.{AnvilProjectManagerAccess.EDIT_PERMISSION_CODENAME}"
        return (perm_required,)
