# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-09-25 10:24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0062_auto_20180914_1048'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mail',
            name='from_email',
        ),
        migrations.AlterField(
            model_name='mail',
            name='template_name',
            field=models.CharField(max_length=100, primary_key=True, serialize=False, verbose_name='Identifiant'),
        ),
    ]