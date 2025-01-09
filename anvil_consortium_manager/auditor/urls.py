from django.urls import include, path

from . import views

app_name = "auditor"


billing_project_patterns = (
    [
        path("", views.BillingProjectAudit.as_view(), name="all"),
    ],
    "billing_projects",
)

account_patterns = (
    [
        path("audit/", views.AccountAudit.as_view(), name="all"),
    ],
    "accounts",
)

managed_group_membership_by_group_ignore_patterns = (
    [
        path("<str:email>/", views.IgnoredManagedGroupMembershipDetail.as_view(), name="detail"),
        path("<str:email>/new/", views.IgnoredManagedGroupMembershipCreate.as_view(), name="new"),
        path("<str:email>/update/", views.IgnoredManagedGroupMembershipUpdate.as_view(), name="update"),
        path("<str:email>/delete/", views.IgnoredManagedGroupMembershipDelete.as_view(), name="delete"),
    ],
    "ignored",
)

managed_group_membership_by_group_patterns = (
    [
        path("", views.ManagedGroupMembershipAudit.as_view(), name="all"),
        path("ignored/", include(managed_group_membership_by_group_ignore_patterns)),
    ],
    "by_group",
)
managed_group_membership_patterns = (
    [
        path("ignored/", views.IgnoredManagedGroupMembershipList.as_view(), name="ignored"),
        path("<slug:slug>/", include(managed_group_membership_by_group_patterns)),
    ],
    "membership",
)

managed_group_patterns = (
    [
        path("audit/", views.ManagedGroupAudit.as_view(), name="all"),
        path("membership/", include(managed_group_membership_patterns)),
    ],
    "managed_groups",
)

workspace_sharing_by_group_ignore_patterns = (
    [
        path("<str:email>/", views.IgnoredWorkspaceSharingDetail.as_view(), name="detail"),
        path("<str:email>/new/", views.IgnoredWorkspaceSharingCreate.as_view(), name="new"),
        path("<str:email>/update/", views.IgnoredWorkspaceSharingUpdate.as_view(), name="update"),
        path("<str:email>/delete/", views.IgnoredWorkspaceSharingDelete.as_view(), name="delete"),
    ],
    "ignored",
)

workspace_sharing_by_group_patterns = (
    [
        path("", views.WorkspaceSharingAudit.as_view(), name="all"),
        path("ignored/", include(workspace_sharing_by_group_ignore_patterns)),
    ],
    "by_workspace",
)
workspace_sharing_patterns = (
    [
        path("<slug:billing_project_slug>/<slug:workspace_slug>/", include(workspace_sharing_by_group_patterns)),
    ],
    "sharing",
)

workspace_patterns = (
    [
        path("", views.WorkspaceAudit.as_view(), name="all"),
        path("sharing/", include(workspace_sharing_patterns)),
    ],
    "workspaces",
)

urlpatterns = [
    path("billing_projects/", include(billing_project_patterns)),
    path("accounts/", include(account_patterns)),
    path("managed_groups/", include(managed_group_patterns)),
    path("workspaces/", include(workspace_patterns)),
]
