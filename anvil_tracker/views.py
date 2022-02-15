from django.views.generic import CreateView, DetailView, TemplateView

from . import models


class Index(TemplateView):
    template_name = "anvil_tracker/index.html"


class InvestigatorDetail(DetailView):
    model = models.Investigator


class InvestigatorCreate(CreateView):
    model = models.Investigator
    fields = ("email",)
