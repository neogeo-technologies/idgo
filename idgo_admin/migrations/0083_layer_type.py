# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-11-26 12:45
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0082_auto_20181126_1102'),
    ]

    operations = [
        migrations.AddField(
            model_name='layer',
            name='type',
            field=models.CharField(blank=True, choices=[('raster', 'raster'), ('vector', 'vector')], max_length=6, null=True, verbose_name='type'),
        ),
    ]
