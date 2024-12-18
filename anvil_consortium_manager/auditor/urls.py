from django.urls import include, path

from . import views

app_name = "auditor"


audit_billing_project_patterns = (
    [
        path("", views.BillingProjectAudit.as_view(), name="all"),
    ],
    "billing_projects",
)
audit_account_patterns = (
    [
        path("audit/", views.AccountAudit.as_view(), name="all"),
    ],
    "accounts",
)
audit_managed_group_membership_ignore_patterns = (
    [
        path("<str:email>/", views.IgnoredManagedGroupMembershipDetail.as_view(), name="detail"),
        path("<str:email>/new/", views.IgnoredManagedGroupMembershipCreate.as_view(), name="new"),
        path("<str:email>/update/", views.IgnoredManagedGroupMembershipUpdate.as_view(), name="update"),
        path("<str:email>/delete/", views.IgnoredManagedGroupMembershipDelete.as_view(), name="delete"),
    ],
    "ignored",
)
audit_managed_group_membership_patterns = (
    [
        path("ignored/", include(audit_managed_group_membership_ignore_patterns)),
        path("", views.ManagedGroupMembershipAudit.as_view(), name="all"),
    ],
    "membership",
)
audit_managed_group_patterns = (
    [
        path("audit/", views.ManagedGroupAudit.as_view(), name="all"),
        path("<slug:slug>/membership/", include(audit_managed_group_membership_patterns)),
    ],
    "managed_groups",
)
audit_workspace_sharing_patterns = (
    [
        path(
            "",
            views.WorkspaceSharingAudit.as_view(),
            name="all",
        ),
    ],
    "sharing",
)
audit_workspace_patterns = (
    [
        path("", views.WorkspaceAudit.as_view(), name="all"),
        path("<slug:billing_project_slug>/<slug:workspace_slug>/sharing/", include(audit_workspace_sharing_patterns)),
    ],
    "workspaces",
)
urlpatterns = [
    path("billing_projects/", include(audit_billing_project_patterns)),
    path("accounts/", include(audit_account_patterns)),
    path("managed_groups/", include(audit_managed_group_patterns)),
    path("workspaces/", include(audit_workspace_patterns)),
]
