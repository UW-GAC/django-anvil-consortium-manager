from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from .. import viewmixins


class AnVILAuditMixinTest(TestCase):
    """ManagedGroupGraphMixin tests that aren't covered elsewhere."""

    def test_run_audit_not_implemented(self):
        with self.assertRaises(ImproperlyConfigured):
            viewmixins.AnVILAuditMixin().run_audit()
