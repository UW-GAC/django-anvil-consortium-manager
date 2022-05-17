# Generated by Django 3.2.12 on 2022-05-16 18:33

from django.db import migrations
import django.db.models.deletion
import simple_history.models


class Migration(migrations.Migration):

    dependencies = [
        ('anvil_consortium_manager', '0006_historicalaccount_historicalbillingproject_historicalgroupaccountmembership_historicalgroupgroupmemb'),
    ]

    operations = [
        migrations.AlterField(
            model_name='groupaccountmembership',
            name='account',
            field=simple_history.models.HistoricForeignKey(on_delete=django.db.models.deletion.CASCADE, to='anvil_consortium_manager.account'),
        ),
        migrations.AlterField(
            model_name='historicalgroupaccountmembership',
            name='account',
            field=simple_history.models.HistoricForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='anvil_consortium_manager.account'),
        ),
    ]