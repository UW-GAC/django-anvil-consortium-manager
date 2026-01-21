# Code taken from Wagtail's wagtail.core.management.commands.convert_mariadb_uuids.py
# See issue and PR:
# https://github.com/wagtail/wagtail/issues/11776
# https://github.com/wagtail/wagtail/pull/11912
from django.core.management.base import BaseCommand
from django.db import connection, models

from ...models import Account, HistoricalAccount, HistoricalUserEmailEntry, UserEmailEntry


class Command(BaseCommand):
    help = "Converts UUID columns from char type to the native UUID type used in MariaDB 10.7+ and Django 5.0+."

    def add_arguments(self, parser):
        parser.add_argument(
            "--models",
            nargs="*",
            type=str,
            choices=["Account", "HistoricalAccount", "HistoricalUserEmailEntry", "UserEmailEntry"],
            help="If specified, run audit on a subset of models. Otherwise, the command will be run on Account, "
            "HistoricalAccount, HistoricalUserEmailEntry, and UserEmailEntry.",
        )

    def convert_field(self, model, field_name, null=False):
        if model._meta.get_field(field_name).model != model:  # pragma: no cover
            # Field is inherited from a parent model
            return

        if not model._meta.managed:  # pragma: no cover
            # The migration framework skips unmanaged models, so we should too
            return

        old_field = models.CharField(null=null, max_length=36)
        old_field.set_attributes_from_name(field_name)

        new_field = models.UUIDField(null=null)
        new_field.set_attributes_from_name(field_name)

        with connection.schema_editor() as schema_editor:
            schema_editor.alter_field(model, old_field, new_field)

    def handle(self, **options):
        if options["models"]:
            models_to_convert = options["models"]
        else:
            models_to_convert = ["Account", "HistoricalAccount", "HistoricalUserEmailEntry", "UserEmailEntry"]

        if "Account" in models_to_convert:
            self.convert_field(Account, "uuid")
        if "HistoricalAccount" in models_to_convert:
            self.convert_field(HistoricalAccount, "uuid")
        if "HistoricalUserEmailEntry" in models_to_convert:
            self.convert_field(HistoricalUserEmailEntry, "uuid")
        if "UserEmailEntry" in models_to_convert:
            self.convert_field(UserEmailEntry, "uuid")
