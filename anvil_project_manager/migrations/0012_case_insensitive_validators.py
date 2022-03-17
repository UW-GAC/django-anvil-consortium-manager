# Generated by Django 3.2.12 on 2022-03-17 00:38

import anvil_project_manager.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anvil_project_manager', '0011_group_is_managed_by_app'),
    ]

    operations = [
        migrations.AlterField(
            model_name='account',
            name='email',
            field=models.EmailField(max_length=254, unique=True, validators=[anvil_project_manager.models.validate_account_email]),
        ),
        migrations.AlterField(
            model_name='billingproject',
            name='name',
            field=models.SlugField(max_length=64, unique=True, validators=[anvil_project_manager.models.validate_billing_project_name]),
        ),
        migrations.AlterField(
            model_name='group',
            name='name',
            field=models.SlugField(max_length=64, unique=True, validators=[anvil_project_manager.models.validate_group_name]),
        ),
    ]