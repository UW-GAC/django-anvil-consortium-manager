# Generated by Django 3.2.12 on 2022-02-14 21:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anvil_tracker', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='investigator',
            name='email',
            field=models.EmailField(max_length=254, unique=True),
        ),
    ]
