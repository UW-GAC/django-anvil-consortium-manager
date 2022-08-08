# Generated by Django 3.2.12 on 2022-08-08 23:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anvil_consortium_manager', '0010_account_uuid'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalworkspace',
            name='workspace_type',
            field=models.CharField(default='default', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='workspace',
            name='workspace_type',
            field=models.CharField(default='default', max_length=255),
            preserve_default=False,
        ),
    ]
