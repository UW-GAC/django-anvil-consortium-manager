# Generated by Django 5.0 on 2024-03-08 00:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anvil_consortium_manager', '0015_add_new_permissions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalmanagedgroup',
            name='name',
            field=models.SlugField(help_text='Name of the group on AnVIL.', max_length=60),
        ),
        migrations.AlterField(
            model_name='historicalworkspace',
            name='name',
            field=models.SlugField(help_text='Name of the workspace on AnVIL, not including billing project name.', max_length=254),
        ),
        migrations.AlterField(
            model_name='managedgroup',
            name='name',
            field=models.SlugField(help_text='Name of the group on AnVIL.', max_length=60, unique=True),
        ),
        migrations.AlterField(
            model_name='workspace',
            name='name',
            field=models.SlugField(help_text='Name of the workspace on AnVIL, not including billing project name.', max_length=254),
        ),
    ]