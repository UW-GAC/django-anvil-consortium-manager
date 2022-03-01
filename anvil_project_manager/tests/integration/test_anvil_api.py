from unittest import TestCase

from ... import anvil_api


class AnVILAPIClientTest(TestCase):
    """Class to run integration tests of the AnVIL API client."""

    @classmethod
    def setUpClass(cls):
        cls.client = anvil_api.AnVILAPIClient()

    def test_groups(self):
        """Tests group methods."""
        test_group = "django-anvil-project-manager-integration-test-group"
        # If the test succeeds, this will run twice but it's ok - it's already deleted.
        # We still want to clean up after ourselves if the test fails.
        self.addCleanup(self.client.auth_session.delete, "groups/" + test_group)
        # The group should not already exist.
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.client.get_group(test_group)
        # Try to create the group.
        response = self.client.create_group(test_group)
        self.assertEqual(response.status_code, 201)
        # Try to create it again.
        response = self.client.create_group(test_group)
        # self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.status_code, 201
        )  # TODO: The API says it should be 409, but it actually returns 201.
        response = self.client.get_group(test_group)
        self.assertEqual(response.status_code, 200)
        # Try to create a group that already exists and someone else owns.
        # This one already exists on AnVIL and we are not admins.
        with self.assertRaises(
            anvil_api.AnVILAPIError403
        ):  # This is not documented it the API, but it makes sense.
            self.client.create_group("test-group")
        # Delete the group.
        response = self.client.delete_group(test_group)
        self.assertEqual(response.status_code, 204)
