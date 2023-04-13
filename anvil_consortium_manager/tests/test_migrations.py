"""Tests for data migrations in the app."""

from django_test_migrations.contrib.unittest_case import MigratorTestCase


class PopulateManagedGroupEmailTest(MigratorTestCase):
    """Tests for the populate_managed_group_email migration."""

    migrate_from = ("anvil_consortium_manager", "0010_managedgroup_add_email")
    migrate_to = ("anvil_consortium_manager", "0011_populate_managed_group_email")

    def prepare(self):
        """Prepare some data before the migration."""
        ManagedGroup = self.old_state.apps.get_model(
            "anvil_consortium_manager", "ManagedGroup"
        )
        ManagedGroup.objects.create(name="mygroup")
        ManagedGroup.objects.create(name="AnotherGroup")

    def test_migration_main0011(self):
        """Run the test."""
        ManagedGroup = self.new_state.apps.get_model(
            "anvil_consortium_manager", "ManagedGroup"
        )
        self.assertEqual(ManagedGroup.objects.count(), 2)
        self.assertEqual(
            ManagedGroup.objects.get(name="mygroup").email, "mygroup@firecloud.org"
        )
        self.assertEqual(
            ManagedGroup.objects.get(name="AnotherGroup").email,
            "anothergroup@firecloud.org",
        )
