from unittest import TestCase

from ... import anvil_api


class AnVILAPIClientTest(TestCase):
    """Class to run integration tests of the AnVIL API client."""

    @classmethod
    def setUpClass(cls):
        cls.client = anvil_api.AnVILAPIClient()

    def test_billing_project(self):
        test_billing_project = "gregor-adrienne"

        # Try to get a billing project that exists.
        response = self.client.get_billing_project(test_billing_project)
        self.assertEqual(response.status_code, 200)
        json = response.json()
        self.assertIn("projectName", json.keys())
        self.assertEqual(json["projectName"], test_billing_project)
        self.assertIn("invalidBillingAccount", json.keys())
        self.assertEqual(json["invalidBillingAccount"], False)

        # try to get a billing project that doesn't exist.
        with self.assertRaises(anvil_api.AnVILAPIError404):
            response = self.client.get_billing_project("asdfghjkl")

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
        self.assertEqual(response.text, "")

        # Try to create the group.
        response = self.client.create_group(test_group)
        self.assertEqual(response.status_code, 201)
        json = response.json()
        self.assertIn("groupEmail", json.keys())
        self.assertEqual(json["groupEmail"], test_group + "@firecloud.org")
        self.assertIn("membersEmails", json.keys())
        self.assertEqual(json["membersEmails"], [])

        # Try to create it again.
        # EXPECTED behavior:
        # with self.assertRaises(anvil_api.AnVILAPIError409):
        #     self.client.create_group(test_group)
        # ACTUAL behavior:
        response = self.client.create_group(test_group)
        self.assertEqual(response.status_code, 201)
        json = response.json()
        self.assertIn("groupEmail", json.keys())
        self.assertEqual(json["groupEmail"], test_group + "@firecloud.org")
        self.assertIn("membersEmails", json.keys())
        self.assertEqual(json["membersEmails"], [])

        # Get info about the group now that it exists.
        response = self.client.get_group(test_group)
        self.assertEqual(response.status_code, 200)
        json = response.json()
        self.assertIn("groupEmail", json.keys())
        self.assertEqual(json["groupEmail"], test_group + "@firecloud.org")
        self.assertIn("membersEmails", json.keys())
        self.assertEqual(json["membersEmails"], [])

        # Delete the group.
        response = self.client.delete_group(test_group)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.text, "")

        # Make sure it's deleted.
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.client.get_group(test_group)

        # Try to create a group that already exists and someone else owns.
        # This one already exists on AnVIL and we are not admins.
        # This is not documented it the API, but it makes sense.
        with self.assertRaises(anvil_api.AnVILAPIError403):
            self.client.create_group("test-group")

        # Try to delete a group that already exists and someone else owns.
        # This one already exists on AnVIL and we are not admins.
        # EXPECTED behavior:
        # with self.assertRaises(anvil_api.AnVILAPIError403):
        #     self.client.delete_group("test-group")
        # ACTUAL behavior:
        response = self.client.delete_group("test-group")
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

        # Add the user to the group.
        response = self.client.add_user_to_group(test_group_1, "MEMBER", test_user)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.text, "")
        # Check group membership.
        response = self.client.get_group(test_group_1)
        json = response.json()
        self.assertIn("adminsEmails", json.keys())
        self.assertNotIn(test_user, json["adminsEmails"])  # Not an admin.
        self.assertIn("membersEmails", json.keys())
        self.assertIn(test_user, json["membersEmails"])  # Added as a member.

        # Try adding the user a second time with the same role.
        response = self.client.add_user_to_group(test_group_1, "MEMBER", test_user)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.text, "")
        # Check group membership.
        response = self.client.get_group(test_group_1)
        json = response.json()
        self.assertIn("adminsEmails", json.keys())
        self.assertNotIn(test_user, json["adminsEmails"])  # Not an admin.
        self.assertIn("membersEmails", json.keys())
        self.assertIn(test_user, json["membersEmails"])  # Still a member.

        # Remove the user from the group with an invalid role.
        with self.assertRaises(anvil_api.AnVILAPIError500):
            self.client.add_user_to_group(test_group_1, "foo", test_user)
        # Check group membership.
        response = self.client.get_group(test_group_1)
        json = response.json()
        self.assertIn("adminsEmails", json.keys())
        self.assertNotIn(test_user, json["adminsEmails"])  # Not an admin.
        self.assertIn("membersEmails", json.keys())
        self.assertIn(test_user, json["membersEmails"])  # Still a member.

        # Also add the user as an ADMIN.
        response = self.client.add_user_to_group(test_group_1, "ADMIN", test_user)
        self.assertEqual(response.status_code, 204)
        # Check group membership.
        response = self.client.get_group(test_group_1)
        json = response.json()
        self.assertIn("adminsEmails", json.keys())
        self.assertIn(test_user, json["adminsEmails"])  # Added as an admin.
        self.assertIn("membersEmails", json.keys())
        self.assertIn(test_user, json["membersEmails"])  # Also still a member.

        # Remove the user from the group MEMBERs.
        response = self.client.remove_user_from_group(test_group_1, "MEMBER", test_user)
        self.assertEqual(response.status_code, 204)
        # Check group membership.
        response = self.client.get_group(test_group_1)
        json = response.json()
        self.assertIn("adminsEmails", json.keys())
        self.assertIn(test_user, json["adminsEmails"])  # Still an admin.
        self.assertIn("membersEmails", json.keys())
        self.assertNotIn(test_user, json["membersEmails"])  # No longer a member.

        # Try removing the user from the group MEMBERs a second time.
        response = self.client.remove_user_from_group(test_group_1, "MEMBER", test_user)
        self.assertEqual(response.status_code, 204)
        # Check group membership.
        response = self.client.get_group(test_group_1)
        json = response.json()
        self.assertIn("adminsEmails", json.keys())
        self.assertIn(test_user, json["adminsEmails"])  # Still an admin.
        self.assertIn("membersEmails", json.keys())
        self.assertNotIn(test_user, json["membersEmails"])  # Still not a member.

        # Remove the user from the group ADMIN.
        response = self.client.remove_user_from_group(test_group_1, "ADMIN", test_user)
        self.assertEqual(response.status_code, 204)
        # Check group membership.
        response = self.client.get_group(test_group_1)
        json = response.json()
        self.assertIn("adminsEmails", json.keys())
        self.assertNotIn(test_user, json["adminsEmails"])  # No longer an admin.
        self.assertIn("membersEmails", json.keys())
        self.assertNotIn(test_user, json["membersEmails"])  # No longer a member.

        # Create another group.
        response = self.client.create_group(test_group_2)
        self.assertEqual(response.status_code, 201)

        # Add the second group to the first group as a MEMBER.
        response = self.client.add_user_to_group(
            test_group_1, "MEMBER", test_group_2 + "@firecloud.org"
        )
        self.assertEqual(response.status_code, 204)
        # Check group membership.
        response = self.client.get_group(test_group_1)
        json = response.json()
        self.assertIn("adminsEmails", json.keys())
        self.assertNotIn(
            test_group_2 + "@firecloud.org", json["adminsEmails"]
        )  # Not an admin.
        self.assertIn("membersEmails", json.keys())
        self.assertIn(
            test_group_2 + "@firecloud.org", json["membersEmails"]
        )  # Added as a member.

        # Remove the second group from the first group.
        response = self.client.remove_user_from_group(
            test_group_1, "MEMBER", test_group_2 + "@firecloud.org"
        )
        self.assertEqual(response.status_code, 204)
        # Check group membership.
        response = self.client.get_group(test_group_1)
        json = response.json()
        self.assertIn("adminsEmails", json.keys())
        self.assertNotIn(
            test_group_2 + "@firecloud.org", json["adminsEmails"]
        )  # Still not an admin.
        self.assertIn("membersEmails", json.keys())
        self.assertNotIn(
            test_group_2 + "@firecloud.org", json["membersEmails"]
        )  # No longer a member.

        # Add the user to a group that we don't have permission for.
        response = self.client.add_user_to_group("test-group", "MEMBER", test_user)
        # EXPECTED behavior:
        # with self.assertRaises(anvil_api.AnVILAPIError403):
        #     self.client.add_user_to_group("test-group", "MEMBER", "amstilp@uw.edu")
        # ACTUAL behavior.
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.text, "")

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
        workspace_json = response.json()
        self.assertIn("namespace", workspace_json.keys())
        self.assertEqual(workspace_json["namespace"], test_billing_project)
        self.assertIn("name", workspace_json.keys())
        self.assertEqual(workspace_json["name"], test_workspace)

        # Get that workspace
        response = self.client.get_workspace(test_billing_project, test_workspace)
        self.assertEqual(response.status_code, 200)
        json = response.json()
        self.assertIn("workspace", json.keys())
        # Last modified appears to change, but check that other keywords are the same.
        check_json = json["workspace"]
        check_json.pop("lastModified", None)
        workspace_json.pop("lastModified", None)
        self.assertEqual(check_json, workspace_json)

        # Try to create it a second time.
        with self.assertRaises(anvil_api.AnVILAPIError409):
            self.client.create_workspace(test_billing_project, test_workspace)

        # Try to delete it.
        response = self.client.delete_workspace(test_billing_project, test_workspace)
        self.assertEqual(response.status_code, 202)

        # Make sure it was deleted.
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.client.get_workspace(test_billing_project, test_workspace)

        # Get info about a workspace that we don't have access to.
        with self.assertRaises(anvil_api.AnVILAPIError404):
            self.client.get_workspace("gregor-adrienne", "api-test-workspace")

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
        json = response.json()
        self.assertIn("usersUpdated", json.keys())
        self.assertEqual(json["usersUpdated"], [])
        self.assertIn("usersNotFound", json.keys())
        self.assertEqual(len(json["usersNotFound"]), 1)
        self.assertEqual(
            json["usersNotFound"][0]["email"], test_group + "@firecloud.org"
        )
        self.assertIn("invitesSent", json.keys())
        self.assertEqual(json["invitesSent"], [])

        # Check ACLs for a workspace that doesn't exist.
        with self.assertRaises(anvil_api.AnVILAPIError404):
            response = self.client.get_workspace_acl(
                test_billing_project, test_workspace
            )

        # Create the workspace.
        response = self.client.create_workspace(test_billing_project, test_workspace)
        self.assertEqual(response.status_code, 201)

        # Check ACLs
        response = self.client.get_workspace_acl(test_billing_project, test_workspace)
        json = response.json()
        self.assertIn("acl", json.keys())
        self.assertEqual(len(json["acl"]), 1)
        owner = list(json["acl"].keys())[0]  # This is the owner of the workspace.
        owner_acl = json["acl"][owner]
        self.assertIn("accessLevel", owner_acl.keys())
        self.assertEqual(owner_acl["accessLevel"], "OWNER")
        # self.assertEqual(group_acl['canCompute'], False)
        # self.assertEqual(group_acl['canShare'], False)
        # self.assertEqual(group_acl['pending'], False)

        # Try to add a group that doesn't exist to the workspace.
        response = self.client.update_workspace_acl(
            test_billing_project, test_workspace, acl_updates
        )
        self.assertEqual(response.status_code, 200)
        json = response.json()
        self.assertIn("usersUpdated", json.keys())
        self.assertEqual(json["usersUpdated"], [])
        self.assertIn("usersNotFound", json.keys())
        self.assertEqual(len(json["usersNotFound"]), 1)
        self.assertEqual(
            json["usersNotFound"][0]["email"], test_group + "@firecloud.org"
        )
        self.assertIn("invitesSent", json.keys())
        self.assertEqual(json["invitesSent"], [])

        # Check ACLs.
        response = self.client.get_workspace_acl(test_billing_project, test_workspace)
        json = response.json()
        self.assertIn("acl", json.keys())
        self.assertEqual(len(json["acl"]), 1)
        self.assertIn(owner, json["acl"].keys())
        self.assertEqual(json["acl"][owner], owner_acl)

        # Create the group
        response = self.client.create_group(test_group)

        # Share the workspace with the group.
        response = self.client.update_workspace_acl(
            test_billing_project, test_workspace, acl_updates
        )
        self.assertEqual(response.status_code, 200)
        json = response.json()
        self.assertIn("usersUpdated", json.keys())
        self.assertEqual(len(json["usersUpdated"]), 1)
        self.assertEqual(
            json["usersUpdated"][0]["email"], test_group + "@firecloud.org"
        )
        self.assertEqual(json["usersUpdated"][0]["accessLevel"], "READER")
        self.assertIn("usersNotFound", json.keys())
        self.assertEqual(json["usersNotFound"], [])
        self.assertIn("invitesSent", json.keys())
        self.assertEqual(json["invitesSent"], [])

        # Check ACL.
        response = self.client.get_workspace_acl(test_billing_project, test_workspace)
        json = response.json()
        self.assertIn("acl", json.keys())
        self.assertEqual(len(json["acl"]), 2)
        self.assertIn(owner, json["acl"])
        self.assertEqual(
            json["acl"][owner], owner_acl
        )  # Service account permissions haven't changed.
        self.assertIn(test_group + "@firecloud.org", json["acl"])
        group_acl = json["acl"][test_group + "@firecloud.org"]
        self.assertIn("accessLevel", group_acl)
        self.assertEqual(group_acl["accessLevel"], "READER")
        self.assertEqual(group_acl["canCompute"], False)
        self.assertEqual(group_acl["canShare"], False)
        self.assertEqual(group_acl["pending"], False)

        # Share the workspace with the group a second time.
        response = self.client.update_workspace_acl(
            test_billing_project, test_workspace, acl_updates
        )
        self.assertEqual(response.status_code, 200)
        json = response.json()
        self.assertIn("usersUpdated", json.keys())
        self.assertEqual(json["usersUpdated"], [])
        self.assertIn("usersNotFound", json.keys())
        self.assertEqual(json["usersNotFound"], [])
        self.assertIn("invitesSent", json.keys())
        self.assertEqual(json["invitesSent"], [])

        # Check ACL.
        response = self.client.get_workspace_acl(test_billing_project, test_workspace)
        json = response.json()
        self.assertIn("acl", json.keys())
        self.assertEqual(len(json["acl"]), 2)
        self.assertIn(owner, json["acl"])
        self.assertEqual(
            json["acl"][owner], owner_acl
        )  # Service account permissions haven't changed.
        self.assertIn(test_group + "@firecloud.org", json["acl"])
        group_acl = json["acl"][test_group + "@firecloud.org"]
        self.assertIn("accessLevel", group_acl)
        self.assertEqual(group_acl["accessLevel"], "READER")  # Still a READER.
        self.assertEqual(group_acl["canCompute"], False)
        self.assertEqual(group_acl["canShare"], False)
        self.assertEqual(group_acl["pending"], False)

        # Change the group's access to WRITER.
        acl_updates[0]["accessLevel"] = "WRITER"
        response = self.client.update_workspace_acl(
            test_billing_project, test_workspace, acl_updates
        )
        self.assertEqual(response.status_code, 200)
        json = response.json()
        self.assertIn("usersUpdated", json.keys())
        self.assertEqual(len(json["usersUpdated"]), 1)
        self.assertEqual(
            json["usersUpdated"][0]["email"], test_group + "@firecloud.org"
        )
        self.assertEqual(json["usersUpdated"][0]["accessLevel"], "WRITER")
        self.assertIn("usersNotFound", json.keys())
        self.assertEqual(json["usersNotFound"], [])
        self.assertIn("invitesSent", json.keys())
        self.assertEqual(json["invitesSent"], [])

        # Check ACL.
        response = self.client.get_workspace_acl(test_billing_project, test_workspace)
        json = response.json()
        self.assertIn("acl", json.keys())
        self.assertEqual(len(json["acl"]), 2)
        self.assertIn(owner, json["acl"])
        self.assertEqual(
            json["acl"][owner], owner_acl
        )  # Service account permissions haven't changed.
        self.assertIn(test_group + "@firecloud.org", json["acl"])
        group_acl = json["acl"][test_group + "@firecloud.org"]
        self.assertIn("accessLevel", group_acl)
        self.assertEqual(group_acl["accessLevel"], "WRITER")  # Changed to WRITER.
        self.assertEqual(group_acl["canCompute"], False)
        self.assertEqual(group_acl["canShare"], False)
        self.assertEqual(group_acl["pending"], False)

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
        json = response.json()
        self.assertIn("usersUpdated", json.keys())
        self.assertEqual(len(json["usersUpdated"]), 1)
        self.assertEqual(
            json["usersUpdated"][0]["email"], test_group + "@firecloud.org"
        )
        self.assertEqual(json["usersUpdated"][0]["accessLevel"], "NO ACCESS")
        self.assertIn("usersNotFound", json.keys())
        self.assertEqual(json["usersNotFound"], [])
        self.assertIn("invitesSent", json.keys())
        self.assertEqual(json["invitesSent"], [])

        # Check ACL.
        response = self.client.get_workspace_acl(test_billing_project, test_workspace)
        json = response.json()
        self.assertIn("acl", json.keys())
        self.assertEqual(len(json["acl"]), 1)
        self.assertIn(owner, json["acl"])
        self.assertEqual(
            json["acl"][owner], owner_acl
        )  # Service account permissions haven't changed.
        self.assertNotIn(test_group + "@firecloud.org", json["acl"])

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
