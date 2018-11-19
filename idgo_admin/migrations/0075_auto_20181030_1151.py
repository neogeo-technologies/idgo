# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-10-30 10:51
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0074_supportedcrs_regex'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='organisation',
            name='financier',
        ),
        migrations.AlterField(
            model_name='supportedcrs',
            name='regex',
            field=models.TextField(blank=True, null=True, verbose_name='Expression régulière'),
        ),
        migrations.DeleteModel(
            name='Financier',
        ),
    ]