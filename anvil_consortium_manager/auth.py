from django.contrib.auth.mixins import PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType

from .models import AnVILProjectManagerAccess


class AnVILConsortiumManagerViewRequired(UserPassesTestMixin):
    """AnVIL global app view permission required mixin.

    This mixin allows anyone with either VIEW or STAFF_VIEW permission to access a view."""

    def test_func(self):
        apm_content_type = ContentType.objects.get_for_model(AnVILProjectManagerAccess)
        perm_1 = f"{apm_content_type.app_label}.{AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME}"
        perm_2 = f"{apm_content_type.app_label}.{AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME}"
        has_perms = self.request.user.has_perms((perm_1,)) or self.request.user.has_perms((perm_2,))
        return has_perms


class AnVILConsortiumManagerStaffViewRequired(PermissionRequiredMixin):
    """AnVIL global app staff view permission required mixin"""

    def get_permission_required(self):
        apm_content_type = ContentType.objects.get_for_model(AnVILProjectManagerAccess)
        perm_required = f"{apm_content_type.app_label}.{AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME}"
        return (perm_required,)


class AnVILConsortiumManagerStaffEditRequired(PermissionRequiredMixin):
    """AnVIL global app edit permission required mixin"""

    def get_permission_required(self):
        apm_content_type = ContentType.objects.get_for_model(AnVILProjectManagerAccess)
        perm_required = f"{apm_content_type.app_label}.{AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME}"
        return (perm_required,)


class AnVILConsortiumManagerAccountLinkRequired(PermissionRequiredMixin):
    """AnVIL global app account link permission required mixin"""

    def get_permission_required(self):
        apm_content_type = ContentType.objects.get_for_model(AnVILProjectManagerAccess)
        perm_required = f"{apm_content_type.app_label}.{AnVILProjectManagerAccess.ACCOUNT_LINK_PERMISSION_CODENAME}"
        return (perm_required,)
