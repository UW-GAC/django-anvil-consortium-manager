"""Tests for the auth.py source file classes that aren't tested elsewhere."""
from django.contrib.auth.models import Permission, User
from django.test import RequestFactory, TestCase

from .. import auth, models


class AnVILConsortiumManagerLimitedViewRequiredTest(TestCase):
    """(Temporary) class to test the AnVILConsortiumManagerLimitedViewRequired mixin."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="test", password="test")

    def get_view_class(self):
        return auth.AnVILConsortiumManagerLimitedViewRequired

    def test_user_with_limited_view_perms(self):
        """test_func returns True for a user with limited view permission."""
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.LIMITED_VIEW_PERMISSION_CODENAME)
        )
        inst = self.get_view_class()()
        request = self.factory.get("")
        request.user = self.user
        inst.request = request
        self.assertTrue(inst.test_func())

    def test_user_with_view_perms(self):
        """test_func returns True for a user with view permission."""
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME)
        )
        inst = self.get_view_class()()
        request = self.factory.get("")
        request.user = self.user
        inst.request = request
        self.assertTrue(inst.test_func())

    def test_user_with_edit_perms(self):
        """test_func returns False for a user with edit permission."""
        self.user.user_permissions.add(
            Permission.objects.get(codename=models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME)
        )
        inst = self.get_view_class()()
        request = self.factory.get("")
        request.user = self.user
        inst.request = request
        self.assertFalse(inst.test_func())

    def test_user_with_no_perms(self):
        """test_func returns False for a user with no permissions."""
        inst = self.get_view_class()()
        request = self.factory.get("")
        request.user = self.user
        inst.request = request
        self.assertFalse(inst.test_func())
