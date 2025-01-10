from django.test import TestCase

from .. import models, tables
from . import factories


class IgnoredManagedGroupMembershipTableTest(TestCase):
    model = models.IgnoredManagedGroupMembership
    model_factory = factories.IgnoredManagedGroupMembershipFactory
    table_class = tables.IgnoredManagedGroupMembershipTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)


class IgnoredWorkspaceSharingTableTest(TestCase):
    model = models.IgnoredWorkspaceSharing
    model_factory = factories.IgnoredWorkspaceSharingFactory
    table_class = tables.IgnoredWorkspaceSharingTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)
