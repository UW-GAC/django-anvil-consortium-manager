# Generated by Django 5.0 on 2024-12-17 23:13

import django.db.models.deletion
import django_extensions.db.fields
import simple_history.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('anvil_consortium_manager', '0019_accountuserarchive'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalIgnoredManagedGroupMembership',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('ignored_email', models.EmailField(help_text='Email address to ignore.', max_length=254)),
                ('note', models.TextField(help_text='Note about why this email is being ignored.')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('added_by', models.ForeignKey(blank=True, db_constraint=False, help_text='User who added the record to this table.', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('group', models.ForeignKey(blank=True, db_constraint=False, help_text='Group where email should be ignored.', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='anvil_consortium_manager.managedgroup')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical ignored managed group membership',
                'verbose_name_plural': 'historical ignored managed group memberships',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='IgnoredManagedGroupMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('ignored_email', models.EmailField(help_text='Email address to ignore.', max_length=254)),
                ('note', models.TextField(help_text='Note about why this email is being ignored.')),
                ('added_by', models.ForeignKey(help_text='User who added the record to this table.', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('group', models.ForeignKey(help_text='Group where email should be ignored.', on_delete=django.db.models.deletion.CASCADE, to='anvil_consortium_manager.managedgroup')),
            ],
        ),
        migrations.AddConstraint(
            model_name='ignoredmanagedgroupmembership',
            constraint=models.UniqueConstraint(fields=('group', 'ignored_email'), name='unique_group_ignored_email'),
        ),
    ]
