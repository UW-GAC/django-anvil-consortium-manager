from unittest import mock

from django.test import TestCase

from .. import models
from . import factories


class GroupAnVILAPIMockTest(TestCase):
    def setUp(self):
        """Setup method to mock requests."""
        super().setUp()
        patcher = mock.patch.object(models.AnVILAPISession, "get")
        self.mock_get = patcher.start()
        self.addCleanup(patcher.stop)

    def test_anvil_exists_group_exists(self):
        group = factories.GroupFactory()
        self.mock_get.return_value.status_code = 200
        self.assertIs(group.anvil_exists(), True)
        self.mock_get.assert_called_once()
