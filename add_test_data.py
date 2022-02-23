# Temporary script to create some test data.
# Run with: python manage.py shell < add_test_data.py

from anvil_project_manager.tests import factories

accounts = factories.AccountFactory.create_batch(5)
groups = factories.GroupFactory.create_batch(5)
workspaces = factories.WorkspaceFactory.create_batch(5)

factories.GroupAccountMembershipFactory.create(group=groups[0], account=accounts[0])
factories.WorkspaceGroupAccessFactory.create(workspace=workspaces[1], group=groups[0])
