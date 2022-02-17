# Temporary script to create some test data.
# Run with: python manage.py shell < add_test_data.py

from anvil_project_manager.tests import factories

researchers = factories.ResearcherFactory.create_batch(5)
groups = factories.GroupFactory.create_batch(5)
workspaces = factories.WorkspaceFactory.create_batch(5)

factories.GroupMembershipFactory.create(group=groups[0], researcher=researchers[0])
factories.WorkspaceGroupAccessFactory.create(workspace=workspaces[1], group=groups[0])
