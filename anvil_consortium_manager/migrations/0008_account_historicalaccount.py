# Generated by Django 3.2.12 on 2022-07-07 19:32

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('anvil_consortium_manager', '0007_groupaccountmembership_account_historicforeignkey'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='date_verified',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='account',
            name='user',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='historicalaccount',
            name='date_verified',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='historicalaccount',
            name='user',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
    ]
