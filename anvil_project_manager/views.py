from django.urls import reverse
from django.views.generic import CreateView, DetailView, TemplateView
from django_tables2 import SingleTableMixin, SingleTableView

from . import models, tables


class Index(TemplateView):
    template_name = "anvil_project_manager/index.html"


class BillingProjectDetail(DetailView):
    model = models.BillingProject


class BillingProjectCreate(CreateView):
    model = models.BillingProject
    fields = ("name",)


class BillingProjectList(SingleTableView):
    model = models.BillingProject
    table_class = tables.BillingProjectTable


class ResearcherDetail(SingleTableMixin, DetailView):
    model = models.Researcher
    table_class = tables.GroupMembershipTable
    context_table_name = "group_table"

    def get_table_data(self):
        return self.object.groupmembership_set.all()


class ResearcherCreate(CreateView):
    model = models.Researcher
    fields = ("email",)


class ResearcherList(SingleTableView):
    model = models.Researcher
    table_class = tables.ResearcherTable


class GroupDetail(SingleTableMixin, DetailView):
    model = models.Group
    table_class = tables.WorkspaceGroupAccessTable
    context_table_name = "workspace_table"

    def get_table_data(self):
        return self.object.workspacegroupaccess_set.all()


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

    def get_table_data(self):
        return self.object.workspacegroupaccess_set.all()


class WorkspaceCreate(CreateView):
    model = models.Workspace
    fields = (
        "billing_project",
        "name",
    )


class WorkspaceList(SingleTableView):
    model = models.Workspace
    table_class = tables.WorkspaceTable


class GroupMembershipCreate(CreateView):
    model = models.GroupMembership
    fields = ("researcher", "group", "role")

    def get_success_url(self):
        return reverse("anvil_project_manager:group_membership:list")


class GroupMembershipList(SingleTableView):
    model = models.GroupMembership
    table_class = tables.GroupMembershipTable


class WorkspaceGroupAccessCreate(CreateView):
    model = models.WorkspaceGroupAccess
    fields = ("workspace", "group", "access")

    def get_success_url(self):
        return reverse("anvil_project_manager:workspace_group_access:list")


class WorkspaceGroupAccessList(SingleTableView):
    model = models.WorkspaceGroupAccess
    table_class = tables.WorkspaceGroupAccessTable
