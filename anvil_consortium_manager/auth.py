from django.contrib.auth.mixins import PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType

from .models import AnVILProjectManagerAccess


class AnVILConsortiumManagerLimitedViewRequired(UserPassesTestMixin):
    """AnVIL global app limited view permission required mixin.

    This mixin allows anyone with either LIMITED_VIEW or VIEW permission to access a view."""

    def test_func(self):
        apm_content_type = ContentType.objects.get_for_model(AnVILProjectManagerAccess)
        perm_1 = f"{apm_content_type.app_label}.{AnVILProjectManagerAccess.LIMITED_VIEW_PERMISSION_CODENAME}"
        perm_2 = f"{apm_content_type.app_label}.{AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME}"
        has_perms = self.request.user.has_perms(
            (perm_1,)
        ) or self.request.user.has_perms((perm_2,))
        return has_perms


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
