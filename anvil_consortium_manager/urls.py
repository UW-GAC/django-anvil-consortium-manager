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
        path("audit/", views.BillingProjectAudit.as_view(), name="audit"),
        path("<slug:slug>/", views.BillingProjectDetail.as_view(), name="detail"),
        path(
            "<slug:slug>/update/", views.BillingProjectUpdate.as_view(), name="update"
        ),
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
        path("<uuid:uuid>/update/", views.AccountUpdate.as_view(), name="update"),
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
        path("link/", views.AccountLink.as_view(), name="link"),
        path(
            "verify/<uuid:uuid>/<token>/",
            views.AccountLinkVerify.as_view(),
            name="verify",
        ),
        path(
            "<uuid:uuid>/add_to_group/",
            views.GroupAccountMembershipCreateByAccount.as_view(),
            name="add_to_group",
        ),
        path("audit/", views.AccountAudit.as_view(), name="audit"),
    ],
    "accounts",
)

member_group_patterns = (
    [
        path(
            "new/",
            views.GroupGroupMembershipCreateByParent.as_view(),
            name="new",
        ),
        path(
            "<slug:child_group_slug>/",
            views.GroupGroupMembershipDetail.as_view(),
            name="detail",
        ),
        path(
            "<slug:child_group_slug>/new/",
            views.GroupGroupMembershipCreateByParentChild.as_view(),
            name="new_by_child",
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
            "new",
            views.GroupAccountMembershipCreateByGroup.as_view(),
            name="new",
        ),
        path(
            "<uuid:account_uuid>/",
            views.GroupAccountMembershipDetail.as_view(),
            name="detail",
        ),
        path(
            "<uuid:account_uuid>/new/",
            views.GroupAccountMembershipCreateByGroupAccount.as_view(),
            name="new_by_account",
        ),
        path(
            "<uuid:account_uuid>/delete/",
            views.GroupAccountMembershipDelete.as_view(),
            name="delete",
        ),
    ],
    "member_accounts",
)

managed_group_sharing_patterns = (
    [
        path(
            "new/",
            views.WorkspaceGroupSharingCreateByGroup.as_view(),
            name="new",
        ),
    ],
    "sharing",
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
        path("audit/", views.ManagedGroupAudit.as_view(), name="audit"),
        path("<slug:slug>/", views.ManagedGroupDetail.as_view(), name="detail"),
        path(
            "<slug:slug>/audit/",
            views.ManagedGroupMembershipAudit.as_view(),
            name="audit_membership",
        ),
        path("<slug:slug>/delete", views.ManagedGroupDelete.as_view(), name="delete"),
        path("<slug:parent_group_slug>/member_groups/", include(member_group_patterns)),
        path("<slug:group_slug>/member_accounts/", include(member_account_patterns)),
        path("<slug:group_slug>/sharing/", include(managed_group_sharing_patterns)),
        path("<slug:slug>/update/", views.ManagedGroupUpdate.as_view(), name="update"),
        path(
            "<slug:group_slug>/add_to_group/",
            views.GroupGroupMembershipCreateByChild.as_view(),
            name="add_to_group",
        ),
    ],
    "managed_groups",
)

workspace_sharing_patterns = (
    [
        path(
            "new/",
            views.WorkspaceGroupSharingCreateByWorkspace.as_view(),
            name="new",
        ),
        path(
            "<slug:group_slug>/",
            views.WorkspaceGroupSharingDetail.as_view(),
            name="detail",
        ),
        path(
            "<slug:group_slug>/new/",
            views.WorkspaceGroupSharingCreateByWorkspaceGroup.as_view(),
            name="new_by_group",
        ),
        path(
            "<slug:group_slug>/update/",
            views.WorkspaceGroupSharingUpdate.as_view(),
            name="update",
        ),
        path(
            "<slug:group_slug>/delete/",
            views.WorkspaceGroupSharingDelete.as_view(),
            name="delete",
        ),
    ],
    "sharing",
)

workspace_patterns = (
    [
        path("", views.WorkspaceList.as_view(), name="list_all"),
        path(
            "autocomplete/",
            views.WorkspaceAutocomplete.as_view(),
            name="autocomplete",
        ),
        path(
            "types/<str:workspace_type>/",
            views.WorkspaceListByType.as_view(),
            name="list",
        ),
        path(
            "types/<str:workspace_type>/new/",
            views.WorkspaceCreate.as_view(),
            name="new",
        ),
        path(
            "types/<str:workspace_type>/import/",
            views.WorkspaceImport.as_view(),
            name="import",
        ),
        # path(
        #     "types/<str:workspace_type>/clone/",
        #     views.WorkspaceClone.as_view(),
        #     name="clone",
        # ),
        path("audit/", views.WorkspaceAudit.as_view(), name="audit"),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/delete/",
            views.WorkspaceDelete.as_view(),
            name="delete",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/",
            views.WorkspaceDetail.as_view(),
            name="detail",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/audit/",
            views.WorkspaceSharingAudit.as_view(),
            name="audit_sharing",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/sharing/",
            include(workspace_sharing_patterns),
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/update/",
            views.WorkspaceUpdate.as_view(),
            name="update",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/clone/<str:workspace_type>/",
            views.WorkspaceClone.as_view(),
            name="clone",
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

workspace_group_sharing_patterns = (
    [
        # Note: these URLs will be removed and/or reworked in the future.
        path("", views.WorkspaceGroupSharingList.as_view(), name="list"),
        path("new/", views.WorkspaceGroupSharingCreate.as_view(), name="new"),
    ],
    "workspace_group_sharing",
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
    path("workspace_group_sharing/", include(workspace_group_sharing_patterns)),
]
