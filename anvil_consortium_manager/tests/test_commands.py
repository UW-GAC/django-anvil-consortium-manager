"""Tests for management commands in `anvil_consortium_manager`."""

from io import StringIO
from unittest import skipUnless

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import TransactionTestCase


class ConvertMariaDbUUIDFieldsTest(TransactionTestCase):
    @skipUnless(settings.DATABASES["default"]["ENGINE"] == "django.db.backends.mysql", "Only for MariaDB")
    def test_convert_mariadb_uuid_fields(self):
        """Test convert_mariadb_uuid_fields command."""
        # Add a response.
        out = StringIO()
        # Just make sure the command runs?
        call_command("convert_mariadb_uuid_fields", stdout=out)

    @skipUnless(settings.DATABASES["default"]["ENGINE"] == "django.db.backends.mysql", "Only for MariaDB")
    def test_convert_mariadb_uuid_fields_one_model(self):
        """Test convert_mariadb_uuid_fields command with one model."""
        # Add a response.
        out = StringIO()
        # Just make sure the command runs?
        call_command("convert_mariadb_uuid_fields", "--models=Account", stdout=out)

    @skipUnless(settings.DATABASES["default"]["ENGINE"] == "django.db.backends.mysql", "Only for MariaDB")
    def test_convert_mariadb_uuid_fields_invalid_model(self):
        """Test convert_mariadb_uuid_fields command with an invalid model."""
        # Add a response.
        out = StringIO()
        with self.assertRaises(CommandError) as e:
            # Call with the "--models=foo" so it goes through the argparse validation.
            # Calling with models=["foo"] does not throw an exception.
            call_command("convert_mariadb_uuid_fields", "--models=foo", stdout=out)
        self.assertIn("invalid choice", str(e.exception))
