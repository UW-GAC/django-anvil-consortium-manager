# Generated by Django 3.2.12 on 2023-04-12 23:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anvil_consortium_manager', '0009_alter_anvilprojectmanageraccess_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalmanagedgroup',
            name='email',
            field=models.EmailField(blank=True, default='', help_text='Email for this group.', max_length=254),
        ),
        migrations.AddField(
            model_name='managedgroup',
            name='email',
            field=models.EmailField(blank=True, default='', help_text='Email for this group.', max_length=254),
        ),
    ]
