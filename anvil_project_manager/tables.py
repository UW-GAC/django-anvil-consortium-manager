import django_tables2 as tables

from . import models


class InvestigatorTable(tables.Table):
    email = tables.LinkColumn("anvil:investigator:detail", args=[tables.utils.A("pk")])

    class Meta:
        model = models.Investigator
        fields = ("pk", "email")
