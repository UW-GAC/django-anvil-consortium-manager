# Generated by Django 3.2.12 on 2022-02-16 17:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('anvil_project_manager', '0002_billingproject'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workspace',
            name='namespace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='anvil_project_manager.billingproject'),
        ),
    ]
