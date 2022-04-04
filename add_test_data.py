# Temporary script to create some test data.
# Run with: python manage.py shell < add_test_data.py

from anvil_project_manager.tests import factories

accounts = factories.AccountFactory.create_batch(5)
groups = factories.ManagedGroupFactory.create_batch(5)
workspaces = factories.WorkspaceFactory.create_batch(5)

# Add some groups to other groups.
factories.ManagedGroupGroupMembershipFactory.create(
    parent_group=groups[0], child_group=groups[1]
)
factories.ManagedGroupGroupMembershipFactory.create(
    parent_group=groups[0], child_group=groups[2]
)

# Add accounts to groups.
factories.ManagedGroupAccountMembershipFactory.create(
    group=groups[1], account=accounts[0]
)
factories.ManagedGroupAccountMembershipFactory.create(
    group=groups[1], account=accounts[1]
)

factories.ManagedGroupAccountMembershipFactory.create(
    group=groups[2], account=accounts[2]
)
factories.ManagedGroupAccountMembershipFactory.create(
    group=groups[2], account=accounts[3]
)

# Share workspaces with a group
factories.WorkspaceGroupAccessFactory.create(workspace=workspaces[0], group=groups[1])
factories.WorkspaceGroupAccessFactory.create(workspace=workspaces[1], group=groups[2])
