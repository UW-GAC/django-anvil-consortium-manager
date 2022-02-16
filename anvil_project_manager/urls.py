from django.urls import include, path

from . import views

app_name = "anvil_project_manager"

investigator_patterns = (
    [
        path("<int:pk>", views.InvestigatorDetail.as_view(), name="detail"),
        path("new/", views.InvestigatorCreate.as_view(), name="new"),
        path("", views.InvestigatorList.as_view(), name="list"),
    ],
    "investigators",
)

group_patterns = (
    [
        path("<int:pk>", views.GroupDetail.as_view(), name="detail"),
        path("new/", views.GroupCreate.as_view(), name="new"),
        path("", views.GroupList.as_view(), name="list"),
    ],
    "groups",
)

workspace_patterns = (
    [
        path("<int:pk>", views.WorkspaceDetail.as_view(), name="detail"),
        path("new/", views.WorkspaceCreate.as_view(), name="new"),
        path("", views.WorkspaceList.as_view(), name="list"),
    ],
    "workspaces",
)

group_membership_patterns = (
    [
        path("new/", views.GroupMembershipCreate.as_view(), name="new"),
        path("", views.GroupMembershipList.as_view(), name="list"),
    ],
    "group_membership",
)

urlpatterns = [
    path("", views.Index.as_view(), name="index"),
    path("investigators/", include(investigator_patterns)),
    path("groups/", include(group_patterns)),
    path("workspaces/", include(workspace_patterns)),
    path("group_membership/", include(group_membership_patterns)),
]
