from django.urls import reverse
from django.views.generic import CreateView, DetailView, TemplateView
from django_tables2 import SingleTableView

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


class ResearcherDetail(DetailView):
    model = models.Researcher


class ResearcherCreate(CreateView):
    model = models.Researcher
    fields = ("email",)


class ResearcherList(SingleTableView):
    model = models.Researcher
    table_class = tables.ResearcherTable


class GroupDetail(DetailView):
    model = models.Group


class GroupCreate(CreateView):
    model = models.Group
    fields = ("name",)


class GroupList(SingleTableView):
    model = models.Group
    table_class = tables.GroupTable


class WorkspaceDetail(DetailView):
    model = models.Workspace


class WorkspaceCreate(CreateView):
    model = models.Workspace
    fields = (
        "billing_project",
        "name",
        "authorization_domain",
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
