from django.views.generic import DetailView, TemplateView

from . import models


class Index(TemplateView):
    template_name = "anvil_tracker/index.html"


class InvestigatorDetail(DetailView):
    model = models.Investigator
