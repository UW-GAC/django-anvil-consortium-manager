from django.urls import reverse
from django.views.generic import CreateView, DetailView, TemplateView
from django_tables2 import SingleTableMixin, SingleTableView

from . import models, tables


class Index(TemplateView):
    template_name = "anvil_project_manager/index.html"


class InvestigatorDetail(SingleTableMixin, DetailView):
    model = models.Investigator
    table_class = tables.GroupTable
    context_table_name = "group_table"


class InvestigatorCreate(CreateView):
    model = models.Investigator
    fields = ("email",)


class InvestigatorList(SingleTableView):
    model = models.Investigator
    table_class = tables.InvestigatorTable


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
        "namespace",
        "name",
        "authorization_domain",
    )


class WorkspaceList(SingleTableView):
    model = models.Workspace
    table_class = tables.WorkspaceTable


class GroupMembershipCreate(CreateView):
    model = models.GroupMembership
    fields = ("investigator", "group", "role")

    def get_success_url(self):
        return reverse("anvil_project_manager:group_membership:list")


class GroupMembershipList(SingleTableView):
    model = models.GroupMembership
    table_class = tables.GroupMembershipTable


class WorkspaceGroupAccessCreate(CreateView):
    model = models.WorkspaceGroupAccess
    fields = ("workspace", "group", "access_level")

    def get_success_url(self):
        return reverse("anvil_project_manager:workspace_group_access:list")


class WorkspaceGroupAccessList(SingleTableView):
    model = models.WorkspaceGroupAccess
    table_class = tables.WorkspaceGroupAccessTable
