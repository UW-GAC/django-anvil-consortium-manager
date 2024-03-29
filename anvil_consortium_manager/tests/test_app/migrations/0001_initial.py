# Generated by Django 3.2.12 on 2023-01-05 00:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('anvil_consortium_manager', '0004_add_note_field'),
    ]

    operations = [
        migrations.CreateModel(
            name='TestWorkspaceData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('study_name', models.CharField(max_length=16, unique=True)),
                ('workspace', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='anvil_consortium_manager.workspace')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ProtectedWorkspaceData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('workspace_data', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='anvil_consortium_manager.defaultworkspacedata')),
            ],
        ),
        migrations.CreateModel(
            name='ProtectedWorkspace',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='anvil_consortium_manager.workspace')),
            ],
        ),
        migrations.CreateModel(
            name='ProtectedManagedGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='anvil_consortium_manager.managedgroup')),
            ],
        ),
    ]
