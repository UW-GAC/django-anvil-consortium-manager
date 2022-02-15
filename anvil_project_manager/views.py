from django.views.generic import CreateView, DetailView, TemplateView
from django_tables2 import SingleTableView

from . import models, tables


class Index(TemplateView):
    template_name = "anvil_project_manager/index.html"


class InvestigatorDetail(DetailView):
    model = models.Investigator


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


class WorkspaceDetail(DetailView):
    model = models.Workspace


class WorkspaceCreate(CreateView):
    model = models.Workspace
    fields = (
        "namespace",
        "name",
        "authorization_domain",
    )
