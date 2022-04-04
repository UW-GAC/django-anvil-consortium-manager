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

managed_group_patterns = (
    [
        path("<int:pk>", views.ManagedGroupDetail.as_view(), name="detail"),
        path("new/", views.ManagedGroupCreate.as_view(), name="new"),
        path("", views.ManagedGroupList.as_view(), name="list"),
        path("<int:pk>/delete", views.ManagedGroupDelete.as_view(), name="delete"),
    ],
    "managed_groups",
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
        path(
            "<int:pk>", views.ManagedGroupGroupMembershipDetail.as_view(), name="detail"
        ),
        path("new/", views.ManagedGroupGroupMembershipCreate.as_view(), name="new"),
        path("", views.ManagedGroupGroupMembershipList.as_view(), name="list"),
        path(
            "<int:pk>/delete",
            views.ManagedGroupGroupMembershipDelete.as_view(),
            name="delete",
        ),
    ],
    "group_group_membership",
)

group_account_membership_patterns = (
    [
        path(
            "<int:pk>",
            views.ManagedGroupAccountMembershipDetail.as_view(),
            name="detail",
        ),
        path("new/", views.ManagedGroupAccountMembershipCreate.as_view(), name="new"),
        path("", views.ManagedGroupAccountMembershipList.as_view(), name="list"),
        path(
            "<int:pk>/delete",
            views.ManagedGroupAccountMembershipDelete.as_view(),
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
    path("managed_groups/", include(managed_group_patterns)),
    path("billing_projects/", include(billing_project_patterns)),
    path("workspaces/", include(workspace_patterns)),
    path("group_group_membership/", include(group_group_membership_patterns)),
    path("group_account_membership/", include(group_account_membership_patterns)),
    path("workspace_group_access/", include(workspace_group_access_patterns)),
]
