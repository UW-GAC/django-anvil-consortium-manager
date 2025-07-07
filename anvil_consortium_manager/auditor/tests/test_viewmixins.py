from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from .. import viewmixins


class AnVILAuditRunMixinTest(TestCase):
    """AnVILAuditRunMixin tests that aren't covered elsewhere."""

    def test_get_audit_instance(self):
        with self.assertRaises(ImproperlyConfigured):
            viewmixins.AnVILAuditRunMixin().get_audit_instance()


class AnVILAuditReviewMixinTest(TestCase):
    """AnVILAuditReviewMixin tests that aren't covered elsewhere."""

    def test_get_cache_key(self):
        with self.assertRaises(ImproperlyConfigured):
            viewmixins.AnVILAuditReviewMixin().get_cache_key()

    def test_get_audit_result_not_found_redirect_url(self):
        with self.assertRaises(ImproperlyConfigured):
            viewmixins.AnVILAuditReviewMixin().get_audit_result_not_found_redirect_url()

    @patch.object(viewmixins.AnVILAuditReviewMixin, "audit_result_not_found_redirect_url", "foo", create=True)
    def test_get_audit_result_not_found_redirect_url_not_none(self):
        self.assertEqual(viewmixins.AnVILAuditReviewMixin().get_audit_result_not_found_redirect_url(), "foo")
