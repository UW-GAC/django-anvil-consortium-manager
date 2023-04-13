# Generated by Django 3.2.12 on 2023-04-13 00:01

from django.db import migrations


def populate_email(apps, schema_editor):
    """Populate the email field for ManagedGroups using the name of the group."""
    ManagedGroup = apps.get_model("anvil_consortium_manager", "ManagedGroup")
    for row in ManagedGroup.objects.all():
        row.email = row.name.lower() + "@firecloud.org"
        row.save(update_fields=["email"])


class Migration(migrations.Migration):

    dependencies = [
        ('anvil_consortium_manager', '0010_managedgroup_add_email'),
    ]

    operations = [
        migrations.RunPython(populate_email, reverse_code=migrations.RunPython.noop),
    ]
