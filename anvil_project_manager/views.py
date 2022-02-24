from django.urls import reverse
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    TemplateView,
    UpdateView,
)
from django_tables2 import SingleTableMixin, SingleTableView

from . import models, tables


class Index(TemplateView):
    template_name = "anvil_project_manager/index.html"


class BillingProjectDetail(SingleTableMixin, DetailView):
    model = models.BillingProject
    context_table_name = "workspace_table"

    def get_table(self):
        return tables.WorkspaceTable(
            self.object.workspace_set.all(), exclude="billing_project"
        )


class BillingProjectCreate(CreateView):
    model = models.BillingProject
    fields = ("name",)


class BillingProjectList(SingleTableView):
    model = models.BillingProject
    table_class = tables.BillingProjectTable


class BillingProjectDelete(DeleteView):
    model = models.BillingProject

    def get_success_url(self):
        return reverse("anvil_project_manager:billing_projects:list")


class AccountDetail(SingleTableMixin, DetailView):
    model = models.Account
    context_table_name = "group_table"

    def get_table(self):
        return tables.GroupAccountMembershipTable(
            self.object.groupaccountmembership_set.all(), exclude="account"
        )


class AccountCreate(CreateView):
    model = models.Account
    fields = ("email", "is_service_account")


class AccountList(SingleTableView):
    model = models.Account
    table_class = tables.AccountTable


class AccountDelete(DeleteView):
    model = models.Account

    def get_success_url(self):
        return reverse("anvil_project_manager:accounts:list")


class GroupDetail(DetailView):
    model = models.Group

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace_table"] = tables.WorkspaceGroupAccessTable(
            self.object.workspacegroupaccess_set.all(), exclude="group"
        )
        context["account_table"] = tables.GroupAccountMembershipTable(
            self.object.groupaccountmembership_set.all(), exclude="group"
        )
        context["group_table"] = tables.GroupGroupMembershipTable(
            self.object.child_memberships.all(), exclude="parent_group"
        )
        return context


class GroupCreate(CreateView):
    model = models.Group
    fields = ("name",)


class GroupList(SingleTableView):
    model = models.Group
    table_class = tables.GroupTable


class GroupDelete(DeleteView):
    model = models.Group

    def get_success_url(self):
        return reverse("anvil_project_manager:groups:list")


class WorkspaceDetail(SingleTableMixin, DetailView):
    model = models.Workspace
    table_class = tables.WorkspaceGroupAccessTable
    context_table_name = "group_table"

    def get_table(self):
        return tables.WorkspaceGroupAccessTable(
            self.object.workspacegroupaccess_set.all(), exclude="workspace"
        )


class WorkspaceCreate(CreateView):
    model = models.Workspace
    fields = (
        "billing_project",
        "name",
    )


class WorkspaceList(SingleTableView):
    model = models.Workspace
    table_class = tables.WorkspaceTable


class WorkspaceDelete(DeleteView):
    model = models.Workspace

    def get_success_url(self):
        return reverse("anvil_project_manager:workspaces:list")


class GroupGroupMembershipDetail(DetailView):
    model = models.GroupGroupMembership


class GroupGroupMembershipCreate(CreateView):
    model = models.GroupGroupMembership
    fields = ("parent_group", "child_group", "role")

    def get_success_url(self):
        return reverse("anvil_project_manager:group_group_membership:list")


class GroupGroupMembershipUpdate(UpdateView):
    model = models.GroupGroupMembership
    fields = ("role",)
    template_name = "anvil_project_manager/groupgroupmembership_update.html"


class GroupGroupMembershipList(SingleTableView):
    model = models.GroupGroupMembership
    table_class = tables.GroupGroupMembershipTable


class GroupGroupMembershipDelete(DeleteView):
    model = models.GroupGroupMembership

    def get_success_url(self):
        return reverse("anvil_project_manager:group_group_membership:list")


class GroupAccountMembershipDetail(DetailView):
    model = models.GroupAccountMembership


class GroupAccountMembershipCreate(CreateView):
    model = models.GroupAccountMembership
    fields = ("account", "group", "role")

    def get_success_url(self):
        return reverse("anvil_project_manager:group_account_membership:list")


class GroupAccountMembershipUpdate(UpdateView):
    model = models.GroupAccountMembership
    fields = ("role",)
    template_name = "anvil_project_manager/groupaccountmembership_update.html"


class GroupAccountMembershipList(SingleTableView):
    model = models.GroupAccountMembership
    table_class = tables.GroupAccountMembershipTable


class GroupAccountMembershipDelete(DeleteView):
    model = models.GroupAccountMembership

    def get_success_url(self):
        return reverse("anvil_project_manager:group_account_membership:list")


class WorkspaceGroupAccessDetail(DetailView):
    model = models.WorkspaceGroupAccess


class WorkspaceGroupAccessCreate(CreateView):
    model = models.WorkspaceGroupAccess
    fields = ("workspace", "group", "access")

    def get_success_url(self):
        return reverse("anvil_project_manager:workspace_group_access:list")


class WorkspaceGroupAccessUpdate(UpdateView):
    model = models.WorkspaceGroupAccess
    fields = ("access",)
    template_name = "anvil_project_manager/workspacegroupaccess_update.html"


class WorkspaceGroupAccessList(SingleTableView):
    model = models.WorkspaceGroupAccess
    table_class = tables.WorkspaceGroupAccessTable


class WorkspaceGroupAccessDelete(DeleteView):
    model = models.WorkspaceGroupAccess

    def get_success_url(self):
        return reverse("anvil_project_manager:workspace_group_access:list")
