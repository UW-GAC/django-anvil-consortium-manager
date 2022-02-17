from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, TemplateView
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


class ResearcherDetail(SingleTableMixin, DetailView):
    model = models.Researcher
    context_table_name = "group_table"

    def get_table(self):
        return tables.GroupMembershipTable(
            self.object.groupmembership_set.all(), exclude="researcher"
        )


class ResearcherCreate(CreateView):
    model = models.Researcher
    fields = ("email",)


class ResearcherList(SingleTableView):
    model = models.Researcher
    table_class = tables.ResearcherTable


class GroupDetail(DetailView):
    model = models.Group

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace_table"] = tables.WorkspaceGroupAccessTable(
            self.object.workspacegroupaccess_set.all(), exclude="group"
        )
        context["researcher_table"] = tables.GroupMembershipTable(
            self.object.groupmembership_set.all(), exclude="group"
        )
        return context


class GroupCreate(CreateView):
    model = models.Group
    fields = ("name",)


class GroupList(SingleTableView):
    model = models.Group
    table_class = tables.GroupTable


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


class GroupMembershipDetail(DetailView):
    model = models.GroupMembership


class GroupMembershipCreate(CreateView):
    model = models.GroupMembership
    fields = ("researcher", "group", "role")

    def get_success_url(self):
        return reverse("anvil_project_manager:group_membership:list")


class GroupMembershipList(SingleTableView):
    model = models.GroupMembership
    table_class = tables.GroupMembershipTable


class GroupMembershipDelete(DeleteView):
    model = models.GroupMembership

    def get_success_url(self):
        return reverse("anvil_project_manager:group_membership:list")


class WorkspaceGroupAccessDetail(DetailView):
    model = models.WorkspaceGroupAccess


class WorkspaceGroupAccessCreate(CreateView):
    model = models.WorkspaceGroupAccess
    fields = ("workspace", "group", "access")

    def get_success_url(self):
        return reverse("anvil_project_manager:workspace_group_access:list")


class WorkspaceGroupAccessList(SingleTableView):
    model = models.WorkspaceGroupAccess
    table_class = tables.WorkspaceGroupAccessTable


class WorkspaceGroupAccessDelete(DeleteView):
    model = models.WorkspaceGroupAccess

    def get_success_url(self):
        return reverse("anvil_project_manager:workspace_group_access:list")
