# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-12-04 10:27
from __future__ import unicode_literals

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0087_jurisdiction_geom'),
    ]

    operations = [
        migrations.AddField(
            model_name='layer',
            name='bbox',
            field=django.contrib.gis.db.models.fields.PolygonField(blank=True, null=True, srid=4326, verbose_name='Rectangle englobant'),
        ),
    ]