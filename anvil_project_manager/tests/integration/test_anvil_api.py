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
        # Try to get info about a group that doesn't exist.
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.client.get_group(test_group)
        # Try to delete a group that doesn't exist.
        # EXPECTED behavior:
        # with self.assertRaises(anvil_api.AnVILAPIError404):
        #     self.client.delete_group(test_group)
        # ACTUAL behavior:
        response = self.client.delete_group(test_group)
        self.assertEqual(response.status_code, 204)
        # Try to create the group.
        response = self.client.create_group(test_group)
        self.assertEqual(response.status_code, 201)
        # Try to create it again.
        # EXPECTED behavior:
        # with self.assertRaises(anvil_api.AnVILAPIError409):
        #     self.client.create_group(test_group)
        # ACTUAL behavior:
        response = self.client.create_group(test_group)
        self.assertEqual(response.status_code, 201)
        # Get info about the group now that it exists.
        response = self.client.get_group(test_group)
        self.assertEqual(response.status_code, 200)
        # Try to create a group that already exists and someone else owns.
        # This one already exists on AnVIL and we are not admins.
        # This is not documented it the API, but it makes sense.
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.client.create_group("test-group")
        # Delete the group.
        response = self.client.delete_group(test_group)
        self.assertEqual(response.status_code, 204)

    def test_group_membership(self):
        test_group_1 = "django-anvil-project-manager-integration-test-group-1"
        test_group_2 = "django-anvil-project-manager-integration-test-group-2"
        test_user = "amstilp@uw.edu"
        # If the test succeeds, this will run twice but it's ok - it's already deleted.
        # We still want to clean up after ourselves if the test fails.
        self.addCleanup(self.client.auth_session.delete, "groups/" + test_group_1)
        self.addCleanup(self.client.auth_session.delete, "groups/" + test_group_2)
        # Try adding the user as a member to a group that doesn't exist.
        # This is undocumented in the API.
        response = self.client.add_user_to_group(test_group_1, "MEMBER", test_user)
        self.assertEqual(
            response.status_code, 204
        )  # Interesting - I'm surprised this isn't a 404.
        self.assertEqual(response.text, "")
        # Try removing a user from a group that doesn't exist.
        # This is undocumented in the API.
        response = self.client.remove_user_from_group(test_group_1, "MEMBER", test_user)
        self.assertEqual(
            response.status_code, 204
        )  # Interesting - I'm surprised this isn't a 404.
        self.assertEqual(response.text, "")
        # Create the group.
        response = self.client.create_group(test_group_1)
        self.assertEqual(response.status_code, 201)
        # Add the user to the group.
        response = self.client.add_user_to_group(test_group_1, "MEMBER", test_user)
        self.assertEqual(response.status_code, 204)
        # Try again a second time.
        response = self.client.add_user_to_group(test_group_1, "MEMBER", test_user)
        self.assertEqual(response.status_code, 204)
        # Remove the user from the group with an incorrect role.
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.client.add_user_to_group(test_group_1, "foo", test_user)
        response = self.client.add_user_to_group(test_group_1, "ADMIN", test_user)
        self.assertEqual(response.status_code, 204)
        # Remove the user from the group with the correct role.
        response = self.client.add_user_to_group(test_group_1, "MEMBER", test_user)
        self.assertEqual(response.status_code, 204)
        # Create another group.
        response = self.client.create_group(test_group_2)
        self.assertEqual(response.status_code, 201)
        # Add the second group to the first group as a member.
        response = self.client.add_user_to_group(
            test_group_1, "MEMBER", test_group_2 + "@firecloud.org"
        )
        self.assertEqual(response.status_code, 204)
        # Remove the second group from the first group.
        response = self.client.remove_user_from_group(
            test_group_1, "MEMBER", test_group_2 + "@firecloud.org"
        )
        self.assertEqual(response.status_code, 204)
        # Add the user to a group that we don't have permission for.
        response = self.client.add_user_to_group("test-group", "MEMBER", test_user)
        # EXPECTED behavior:
        # with self.assertRaises(anvil_api.AnVILAPIError403):
        #     self.client.add_user_to_group("test-group", "MEMBER", "amstilp@uw.edu")
        # ACTUAL behavior.
        self.assertEqual(response.status_code, 204)
        # Delete the groups.
        self.client.delete_group(test_group_1)
        self.client.delete_group(test_group_2)

    def test_workspaces(self):
        """Tests workspace methods."""
        test_billing_project = "gregor-adrienne"
        test_workspace = "django-anvil-project-manager-integration-test-workspace"
        test_group = "django-anvil-project-manager-integration-test-group"

        # If the test succeeds, this will run twice but it's ok - it's already deleted.
        # We still want to clean up after ourselves if the test fails.
        self.addCleanup(
            self.client.auth_session.delete,
            "workspaces/" + test_billing_project + "/" + test_workspace,
        )
        self.addCleanup(self.client.auth_session.delete, "groups/" + test_group)

        # Try to get info about a workspace that doesn't exist.
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.client.get_workspace(test_billing_project, test_workspace)
        # Try to delete a workspace that doesn't exist.
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.client.delete_workspace(test_billing_project, test_workspace)
        # Create the workspace.
        response = self.client.create_workspace(test_billing_project, test_workspace)
        self.assertEqual(response.status_code, 201)
        # Get that workspace
        response = self.client.get_workspace(test_billing_project, test_workspace)
        self.assertEqual(response.status_code, 200)
        # Try to create it a second time.
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.client.create_workspace(test_billing_project, test_workspace)
        # Try to delete it.
        response = self.client.delete_workspace(test_billing_project, test_workspace)
        self.assertEqual(response.status_code, 202)

    def test_workspace_sharing(self):
        """Tests method to share workspaces."""
        test_billing_project = "gregor-adrienne"
        test_workspace = "django-anvil-project-manager-integration-test-workspace"
        test_group = "django-anvil-project-manager-integration-test-group"

        # If the test succeeds, this will run twice but it's ok - it's already deleted.
        # We still want to clean up after ourselves if the test fails.
        self.addCleanup(
            self.client.auth_session.delete,
            "workspaces/" + test_billing_project + "/" + test_workspace,
        )
        self.addCleanup(self.client.auth_session.delete, "groups/" + test_group)

        # Try to share workspace that doesn't exist with a group that doesn't exist.
        acl_updates = [
            {
                "email": test_group + "@firecloud.org",
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        # It looks like this checks that the group exists first before checking that the workspace exists.
        # EXPECTED behavior.
        # with self.assertRaises(anvil_api.AnVILAPIError404):
        #     self.client.update_workspace_acl(test_billing_project, test_workspace, acl_updates)
        # ACTUAL behavior.
        response = self.client.update_workspace_acl(
            test_billing_project, test_workspace, acl_updates
        )
        self.assertEqual(response.status_code, 200)
        # Create the workspace.
        response = self.client.create_workspace(test_billing_project, test_workspace)
        self.assertEqual(response.status_code, 201)
        # Try to add a group that doesn't exist to the workspace.
        response = self.client.update_workspace_acl(
            test_billing_project, test_workspace, acl_updates
        )
        self.assertEqual(response.status_code, 200)
        # Create the group and share the workspace with it.
        response = self.client.create_group(test_group)
        response = self.client.update_workspace_acl(
            test_billing_project, test_workspace, acl_updates
        )
        self.assertEqual(response.status_code, 200)
        # Try to share the workspace with an invalid access level.
        acl_updates[0]["accessLevel"] = "foo"
        with self.assertRaises(anvil_api.AnVILAPIError400):
            self.client.update_workspace_acl(
                test_billing_project, test_workspace, acl_updates
            )
        # Remove the group's access to the workspace.
        acl_updates[0]["accessLevel"] = "NO ACCESS"
        response = self.client.update_workspace_acl(
            test_billing_project, test_workspace, acl_updates
        )
        self.assertEqual(response.status_code, 200)
        # Delete the workspace.
        response = self.client.delete_workspace(test_billing_project, test_workspace)
        self.assertEqual(response.status_code, 202)
        # Try to share the workspace (which does not exist) with the group (which exists).
        acl_updates[0]["accessLevel"] = "READER"
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.client.update_workspace_acl(
                test_billing_project, test_workspace, acl_updates
            )
        # Delete the group
        self.client.delete_group(test_group)
