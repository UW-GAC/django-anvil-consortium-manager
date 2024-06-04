Management Commands
===================

The app provides custom the following management commands.

run_anvil_audit
---------------

This command runs AnVIL audits for each model type and reports the results.
Results can either be printed to stdout or as a report sent via email.
Run ``python manage.py run_anvil_audit --help`` to see available options.


convert_mariadb_uuid_fields
---------------------------

For sites using MariaDB, this command must be run once when upgrading to Django 5.0
and MariaDB 10.7 from any earlier version of Django or MariaDB. This is necessary
because Django 5.0 introduces support for MariaDB's native UUID type, breaking
backwards compatibility with `CHAR`-based UUIDs used in earlier versions of Django and
MariaDB. New sites created under Django 5.0+ and MariaDB 10.7+ are unaffected.

Taken from Wagtail's implementation: ``wagtail.core.management.commands.convert_mariadb_uuids.py``
