# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-03-05 13:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0109_auto_20190305_1252'),
    ]

    operations = [
        migrations.AddField(
            model_name='resourceformats',
            name='name',
            field=models.CharField(blank=True, max_length=10, null=True, unique=True, verbose_name='Nom identifiant'),
        ),
        migrations.AlterField(
            model_name='resourceformats',
            name='ckan_format',
            field=models.CharField(max_length=10, verbose_name='Format CKAN'),
        ),
        migrations.AlterField(
            model_name='resourceformats',
            name='ckan_view',
            field=models.CharField(blank=True, choices=[(None, 'N/A'), ('text_view', 'text_view'), ('geo_view', 'geo_view'), ('recline_view', 'recline_view'), ('pdf_view', 'pdf_view')], max_length=100, null=True, verbose_name='Vue CKAN'),
        ),
        migrations.AlterField(
            model_name='resourceformats',
            name='is_gis_format',
            field=models.BooleanField(default=False, verbose_name='Format de fichier SIG'),
        ),
    ]