# Generated by Django 3.2.12 on 2023-03-03 23:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anvil_consortium_manager', '0007_workspacegroupsharing_access_fix_typo'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalworkspace',
            name='is_locked',
            field=models.BooleanField(default=False, help_text='Indicator of whether the workspace is locked or not.'),
        ),
        migrations.AddField(
            model_name='workspace',
            name='is_locked',
            field=models.BooleanField(default=False, help_text='Indicator of whether the workspace is locked or not.'),
        ),
    ]
