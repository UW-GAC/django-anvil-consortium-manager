# Generated by Django 3.2.12 on 2022-04-05 00:09

import anvil_project_manager.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, unique=True, validators=[anvil_project_manager.models.validate_account_email])),
                ('is_service_account', models.BooleanField()),
            ],
        ),
        migrations.CreateModel(
            name='BillingProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.SlugField(max_length=64, unique=True)),
                ('has_app_as_user', models.BooleanField()),
            ],
        ),
        migrations.CreateModel(
            name='ManagedGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.SlugField(max_length=64, unique=True, validators=[anvil_project_manager.models.validate_group_name])),
                ('is_managed_by_app', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Workspace',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.SlugField(max_length=64)),
            ],
        ),
        migrations.CreateModel(
            name='WorkspaceGroupAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access', models.CharField(choices=[('OWNER', 'Owner'), ('WRITER', 'Writer'), ('READER', 'Reader')], default='READER', max_length=10)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='anvil_project_manager.managedgroup')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='anvil_project_manager.workspace')),
            ],
        ),
        migrations.CreateModel(
            name='WorkspaceAuthorizationDomain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='anvil_project_manager.managedgroup')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='anvil_project_manager.workspace')),
            ],
        ),
        migrations.AddField(
            model_name='workspace',
            name='authorization_domains',
            field=models.ManyToManyField(blank=True, through='anvil_project_manager.WorkspaceAuthorizationDomain', to='anvil_project_manager.ManagedGroup'),
        ),
        migrations.AddField(
            model_name='workspace',
            name='billing_project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='anvil_project_manager.billingproject'),
        ),
        migrations.CreateModel(
            name='GroupGroupMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('MEMBER', 'Member'), ('ADMIN', 'Admin')], default='MEMBER', max_length=10)),
                ('child_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parent_memberships', to='anvil_project_manager.managedgroup')),
                ('parent_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='child_memberships', to='anvil_project_manager.managedgroup')),
            ],
        ),
        migrations.CreateModel(
            name='GroupAccountMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('MEMBER', 'Member'), ('ADMIN', 'Admin')], default='MEMBER', max_length=10)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='anvil_project_manager.account')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='anvil_project_manager.managedgroup')),
            ],
        ),
        migrations.AddConstraint(
            model_name='workspacegroupaccess',
            constraint=models.UniqueConstraint(fields=('group', 'workspace'), name='unique_workspace_group_access'),
        ),
        migrations.AddConstraint(
            model_name='workspaceauthorizationdomain',
            constraint=models.UniqueConstraint(fields=('group', 'workspace'), name='unique_workspace_auth_domain'),
        ),
        migrations.AddConstraint(
            model_name='workspace',
            constraint=models.UniqueConstraint(fields=('billing_project', 'name'), name='unique_workspace'),
        ),
        migrations.AddConstraint(
            model_name='groupgroupmembership',
            constraint=models.UniqueConstraint(fields=('parent_group', 'child_group'), name='unique_group_group_membership'),
        ),
        migrations.AddConstraint(
            model_name='groupaccountmembership',
            constraint=models.UniqueConstraint(fields=('account', 'group'), name='unique_group_account_membership'),
        ),
    ]
