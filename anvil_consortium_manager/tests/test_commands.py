"""Tests for management commands in `anvil_consortium_manager`."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class RunAnvilAuditTest(TestCase):
    """Tests for the run_anvil_audit command"""

    def test_command_output_no_instances(self):
        """Test command output."""
        out = StringIO()
        call_command("run_anvil_audit", stdout=out)
        self.assertIn("Done!", out.getvalue())
