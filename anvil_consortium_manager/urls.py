from django.urls import include, path

from . import views

app_name = "anvil_consortium_manager"

billing_project_patterns = (
    [
        path("", views.BillingProjectList.as_view(), name="list"),
        path("import/", views.BillingProjectImport.as_view(), name="import"),
        path(
            "autocomplete/",
            views.BillingProjectAutocomplete.as_view(),
            name="autocomplete",
        ),
        path("<slug:slug>/", views.BillingProjectDetail.as_view(), name="detail"),
    ],
    "billing_projects",
)

account_patterns = (
    [
        path("<uuid:uuid>/", views.AccountDetail.as_view(), name="detail"),
        path("import/", views.AccountImport.as_view(), name="import"),
        path("all/", views.AccountList.as_view(), name="list"),
        path("active/", views.AccountActiveList.as_view(), name="list_active"),
        path("inactive/", views.AccountInactiveList.as_view(), name="list_inactive"),
        path("<uuid:uuid>/delete/", views.AccountDelete.as_view(), name="delete"),
        path(
            "<uuid:uuid>/deactivate/",
            views.AccountDeactivate.as_view(),
            name="deactivate",
        ),
        path(
            "<uuid:uuid>/reactivate/",
            views.AccountReactivate.as_view(),
            name="reactivate",
        ),
        path(
            "autocomplete/",
            views.AccountAutocomplete.as_view(),
            name="autocomplete",
        ),
    ],
    "accounts",
)

member_group_patterns = (
    [
        path(
            "<slug:child_group_slug>/",
            views.GroupGroupMembershipDetail.as_view(),
            name="detail",
        ),
        path(
            "<slug:child_group_slug>/delete/",
            views.GroupGroupMembershipDelete.as_view(),
            name="delete",
        ),
    ],
    "member_groups",
)

member_account_patterns = (
    [
        path(
            "<uuid:account_uuid>/",
            views.GroupAccountMembershipDetail.as_view(),
            name="detail",
        ),
        path(
            "<uuid:account_uuid>/delete/",
            views.GroupAccountMembershipDelete.as_view(),
            name="delete",
        ),
    ],
    "member_accounts",
)

managed_group_patterns = (
    [
        path("", views.ManagedGroupList.as_view(), name="list"),
        path("new/", views.ManagedGroupCreate.as_view(), name="new"),
        path(
            "autocomplete/",
            views.ManagedGroupAutocomplete.as_view(),
            name="autocomplete",
        ),
        path("<slug:slug>/", views.ManagedGroupDetail.as_view(), name="detail"),
        path("<slug:slug>/delete", views.ManagedGroupDelete.as_view(), name="delete"),
        path("<slug:parent_group_slug>/member_groups/", include(member_group_patterns)),
        path("<slug:group_slug>/member_accounts/", include(member_account_patterns)),
    ],
    "managed_groups",
)

workspace_patterns = (
    [
        path("", views.WorkspaceList.as_view(), name="list"),
        path("new/", views.WorkspaceCreate.as_view(), name="new"),
        path("import/", views.WorkspaceImport.as_view(), name="import"),
        path("", views.WorkspaceList.as_view(), name="list"),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/delete/",
            views.WorkspaceDelete.as_view(),
            name="delete",
        ),
        path(
            "autocomplete/",
            views.WorkspaceAutocomplete.as_view(),
            name="autocomplete",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/",
            views.WorkspaceDetail.as_view(),
            name="detail",
        ),
    ],
    "workspaces",
)

group_group_membership_patterns = (
    [
        path("", views.GroupGroupMembershipList.as_view(), name="list"),
        path("new/", views.GroupGroupMembershipCreate.as_view(), name="new"),
    ],
    "group_group_membership",
)

group_account_membership_patterns = (
    [
        # Note: these URLs will be removed and/or reworked in the future.
        path("new/", views.GroupAccountMembershipCreate.as_view(), name="new"),
        path("all/", views.GroupAccountMembershipList.as_view(), name="list"),
        path(
            "active/",
            views.GroupAccountMembershipActiveList.as_view(),
            name="list_active",
        ),
        path(
            "inactive/",
            views.GroupAccountMembershipInactiveList.as_view(),
            name="list_inactive",
        ),
    ],
    "group_account_membership",
)

workspace_group_access_patterns = (
    [
        # Note: these URLs will be removed and/or reworked in the future.
        path("", views.WorkspaceGroupAccessList.as_view(), name="list"),
        path("new/", views.WorkspaceGroupAccessCreate.as_view(), name="new"),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/access/<slug:group_slug>/",
            views.WorkspaceGroupAccessDetail.as_view(),
            name="detail",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/access/<slug:group_slug>/update/",
            views.WorkspaceGroupAccessUpdate.as_view(),
            name="update",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/access/<slug:group_slug>/delete/",
            views.WorkspaceGroupAccessDelete.as_view(),
            name="delete",
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
