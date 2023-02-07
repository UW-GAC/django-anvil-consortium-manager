# Temporary script to create some test data.
# Run with: python manage.py shell < add_test_data.py

from anvil_consortium_manager.tests import factories

accounts = factories.AccountFactory.create_batch(5)
groups = factories.ManagedGroupFactory.create_batch(5)
workspaces = factories.WorkspaceFactory.create_batch(5, workspace_type="example")

# Add some groups to other groups.
factories.GroupGroupMembershipFactory.create(
    parent_group=groups[0], child_group=groups[1]
)
factories.GroupGroupMembershipFactory.create(
    parent_group=groups[0], child_group=groups[2]
)
factories.GroupGroupMembershipFactory.create(
    parent_group=groups[3], child_group=groups[2]
)

# Add accounts to groups.
factories.GroupAccountMembershipFactory.create(group=groups[1], account=accounts[0])
factories.GroupAccountMembershipFactory.create(group=groups[1], account=accounts[1])

factories.GroupAccountMembershipFactory.create(group=groups[2], account=accounts[2])
factories.GroupAccountMembershipFactory.create(group=groups[2], account=accounts[3])

# Share workspaces with a group
factories.WorkspaceGroupSharingFactory.create(workspace=workspaces[0], group=groups[1])
factories.WorkspaceGroupSharingFactory.create(workspace=workspaces[1], group=groups[2])
