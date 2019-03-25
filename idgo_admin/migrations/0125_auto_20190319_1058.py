# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2019-03-19 09:58
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0124_auto_20190319_0932'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gdpr',
            name='issue_date',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name="Date d'émission"),
        ),
        migrations.AlterField(
            model_name='gdpruser',
            name='validated_on',
            field=models.DateTimeField(blank=True, default=django.utils.timezone.now, null=True, verbose_name='Date de validation'),
        ),
        migrations.AlterField(
            model_name='resourceformats',
            name='protocol',
            field=models.CharField(blank=True, choices=[('OGC:WMS', 'WMS'), ('OGC:WFS', 'WFS'), ('WWW:DOWNLOAD-1.0-http--download', 'ZIP')], max_length=100, null=True, verbose_name='Protocole'),
        ),
    ]