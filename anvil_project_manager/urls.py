from django.urls import include, path

from . import views

app_name = "anvil_project_manager"

billing_project_patterns = (
    [
        path("<int:pk>", views.BillingProjectDetail.as_view(), name="detail"),
        path("import/", views.BillingProjectImport.as_view(), name="import"),
        path("", views.BillingProjectList.as_view(), name="list"),
    ],
    "billing_projects",
)

account_patterns = (
    [
        path("<int:pk>", views.AccountDetail.as_view(), name="detail"),
        path("import/", views.AccountImport.as_view(), name="import"),
        path("", views.AccountList.as_view(), name="list"),
        path("<int:pk>/delete", views.AccountDelete.as_view(), name="delete"),
    ],
    "accounts",
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
        path("import/", views.WorkspaceImport.as_view(), name="import"),
        path("", views.WorkspaceList.as_view(), name="list"),
        path("<int:pk>/delete", views.WorkspaceDelete.as_view(), name="delete"),
    ],
    "workspaces",
)

group_group_membership_patterns = (
    [
        path("<int:pk>", views.GroupGroupMembershipDetail.as_view(), name="detail"),
        path("new/", views.GroupGroupMembershipCreate.as_view(), name="new"),
        path("", views.GroupGroupMembershipList.as_view(), name="list"),
        path(
            "<int:pk>/delete",
            views.GroupGroupMembershipDelete.as_view(),
            name="delete",
        ),
    ],
    "group_group_membership",
)

group_account_membership_patterns = (
    [
        path("<int:pk>", views.GroupAccountMembershipDetail.as_view(), name="detail"),
        path("new/", views.GroupAccountMembershipCreate.as_view(), name="new"),
        path("", views.GroupAccountMembershipList.as_view(), name="list"),
        path(
            "<int:pk>/delete",
            views.GroupAccountMembershipDelete.as_view(),
            name="delete",
        ),
    ],
    "group_account_membership",
)

workspace_group_access_patterns = (
    [
        path("<int:pk>", views.WorkspaceGroupAccessDetail.as_view(), name="detail"),
        path("new/", views.WorkspaceGroupAccessCreate.as_view(), name="new"),
        path("", views.WorkspaceGroupAccessList.as_view(), name="list"),
        path(
            "<int:pk>/delete", views.WorkspaceGroupAccessDelete.as_view(), name="delete"
        ),
        path(
            "<int:pk>/update",
            views.WorkspaceGroupAccessUpdate.as_view(),
            name="update",
        ),
    ],
    "workspace_group_access",
)

urlpatterns = [
    path("", views.Index.as_view(), name="index"),
    path("status/", views.AnVILStatus.as_view(), name="status"),
    path("accounts/", include(account_patterns)),
    path("groups/", include(group_patterns)),
    path("billing_projects/", include(billing_project_patterns)),
    path("workspaces/", include(workspace_patterns)),
    path("group_group_membership/", include(group_group_membership_patterns)),
    path("group_account_membership/", include(group_account_membership_patterns)),
    path("workspace_group_access/", include(workspace_group_access_patterns)),
]
