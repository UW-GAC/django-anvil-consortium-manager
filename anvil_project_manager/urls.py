from django.urls import include, path

from . import views

app_name = "anvil_project_manager"

billing_project_patterns = (
    [
        path("<int:pk>", views.BillingProjectDetail.as_view(), name="detail"),
        path("new/", views.BillingProjectCreate.as_view(), name="new"),
        path("", views.BillingProjectList.as_view(), name="list"),
        path("<int:pk>/delete", views.BillingProjectDelete.as_view(), name="delete"),
    ],
    "billing_projects",
)

researcher_patterns = (
    [
        path("<int:pk>", views.ResearcherDetail.as_view(), name="detail"),
        path("new/", views.ResearcherCreate.as_view(), name="new"),
        path("", views.ResearcherList.as_view(), name="list"),
        path("<int:pk>/delete", views.ResearcherDelete.as_view(), name="delete"),
    ],
    "researchers",
)

group_patterns = (
    [
        path("<int:pk>", views.GroupDetail.as_view(), name="detail"),
        path("new/", views.GroupCreate.as_view(), name="new"),
        path("", views.GroupList.as_view(), name="list"),
        path("<int:pk>/delete", views.GroupDelete.as_view(), name="delete"),
    ],
    "groups",
)

workspace_patterns = (
    [
        path("<int:pk>", views.WorkspaceDetail.as_view(), name="detail"),
        path("new/", views.WorkspaceCreate.as_view(), name="new"),
        path("", views.WorkspaceList.as_view(), name="list"),
        path("<int:pk>/delete", views.WorkspaceDelete.as_view(), name="delete"),
    ],
    "workspaces",
)

group_membership_patterns = (
    [
        path("<int:pk>", views.GroupMembershipDetail.as_view(), name="detail"),
        path("new/", views.GroupMembershipCreate.as_view(), name="new"),
        path("", views.GroupMembershipList.as_view(), name="list"),
        path("<int:pk>/delete", views.GroupMembershipDelete.as_view(), name="delete"),
    ],
    "group_membership",
)

workspace_group_access_patterns = (
    [
        path("<int:pk>", views.WorkspaceGroupAccessDetail.as_view(), name="detail"),
        path("new/", views.WorkspaceGroupAccessCreate.as_view(), name="new"),
        path("", views.WorkspaceGroupAccessList.as_view(), name="list"),
        path(
            "<int:pk>/delete", views.WorkspaceGroupAccessDelete.as_view(), name="delete"
        ),
    ],
    "workspace_group_access",
)

urlpatterns = [
    path("", views.Index.as_view(), name="index"),
    path("researchers/", include(researcher_patterns)),
    path("groups/", include(group_patterns)),
    path("billing_projects/", include(billing_project_patterns)),
    path("workspaces/", include(workspace_patterns)),
    path("group_membership/", include(group_membership_patterns)),
    path("workspace_group_access/", include(workspace_group_access_patterns)),
]
