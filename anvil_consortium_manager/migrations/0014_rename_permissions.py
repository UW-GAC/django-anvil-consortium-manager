# Generated by Django 4.2.7 on 2023-11-06 19:12
# We cannot easily test this migration using django-test-migrations because
# permissions and content types are created via post-migrate signals, and
# django-test-migrations mutes signals.
# So this is only manually tested :(
#
# Some relevant stack overflow posts:
# https://stackoverflow.com/questions/47182012/remove-old-permissions-in-django

from django.db import migrations


def set_up_new_permissions(apps, schema_editor):
    # Map between original codename and updated codename.
    permissions_codename_map = {
        "anvil_project_manager_edit": "anvil_consortium_manager_staff_edit",
        "anvil_project_manager_view": "anvil_consortium_manager_staff_view",
        "anvil_project_manager_limited_view": "anvil_consortium_manager_view",
        "anvil_project_manager_account_link": "anvil_consortium_manager_account_link",
    }
    # Map between original codename and updated name.
    permissions_name_map = {
        "anvil_project_manager_edit": "AnVIL Consortium Manager Staff Edit Permission",
        "anvil_project_manager_view": "AnVIL Consortium Manager Staff View Permission",
        "anvil_project_manager_limited_view": "AnVIL Consortium Manager View Permission",
        "anvil_project_manager_account_link": "AnVIL Consortium Manager Account Link Permission",
    }
    # Rename old permissions if they exist.
    Permission = apps.get_model("auth", "Permission")

    ContentType = apps.get_model("contenttypes", "ContentType")
    try:
        model = ContentType.objects.get(app_label="anvil_consortium_manager", model="anvilprojectmanageraccess")
        for original_codename in permissions_codename_map.keys():
            permission = Permission.objects.get(content_type=model, codename=original_codename)
            # Update codename and name.
            permission.codename = permissions_codename_map[original_codename]
            permission.name = permissions_name_map[original_codename]
            # Save the new permission
            permission.save()
    except ContentType.DoesNotExist:
        # Permissions and ContentTypes are created after all migrations are completed using
        # post-migrate signals. If the ContentType for this app does not exist, then this is
        # the first time that "migrate" has been run, so no permissions need to be renamed.
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("anvil_consortium_manager", "0013_alter_anvilprojectmanageraccess_options"),
    ]

    operations = [
        # I could not get the reverse code to work - see comments above.
        migrations.RunPython(set_up_new_permissions, reverse_code=migrations.RunPython.noop),
    ]
