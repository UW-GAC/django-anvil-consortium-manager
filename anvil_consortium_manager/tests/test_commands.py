"""Tests for management commands in `anvil_consortium_manager`."""

from io import StringIO
from unittest import skipUnless

from django.conf import settings
from django.core.management import call_command
from django.test import TransactionTestCase


class ConvertMariaDbUUIDFieldsTest(TransactionTestCase):
    @skipUnless(settings.DATABASES["default"]["ENGINE"] == "django.db.backends.mysql", "Only for MariaDB")
    def test_convert_mariadb_uuid_fields(self):
        """Test convert_mariadb_uuid_fields command."""
        # Add a response.
        out = StringIO()
        # Just make sure the command runs?
        call_command("convert_mariadb_uuid_fields", stdout=out)
