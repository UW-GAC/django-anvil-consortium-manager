# Generated by Django 3.2.12 on 2022-11-22 17:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anvil_consortium_manager', '0003_rename_workspacegroupaccess'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='note',
            field=models.TextField(blank=True, help_text='Additional notes.'),
        ),
        migrations.AddField(
            model_name='billingproject',
            name='note',
            field=models.TextField(blank=True, help_text='Additional notes.'),
        ),
        migrations.AddField(
            model_name='historicalaccount',
            name='note',
            field=models.TextField(blank=True, help_text='Additional notes.'),
        ),
        migrations.AddField(
            model_name='historicalbillingproject',
            name='note',
            field=models.TextField(blank=True, help_text='Additional notes.'),
        ),
        migrations.AddField(
            model_name='historicalmanagedgroup',
            name='note',
            field=models.TextField(blank=True, help_text='Additional notes.'),
        ),
        migrations.AddField(
            model_name='historicalworkspace',
            name='note',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='managedgroup',
            name='note',
            field=models.TextField(blank=True, help_text='Additional notes.'),
        ),
        migrations.AddField(
            model_name='workspace',
            name='note',
            field=models.TextField(blank=True),
        ),
    ]