# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-12-21 08:53
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0022_auto_20171221_0946'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organisation',
            name='financier',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='idgo_admin.Financier'),
        ),
        migrations.AlterField(
            model_name='organisation',
            name='organisation_type',
            field=models.ForeignKey(blank=True, default='1', null=True, on_delete=django.db.models.deletion.SET_NULL, to='idgo_admin.OrganisationType', verbose_name="Type d'organisation"),
        ),
    ]
