# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-11-16 12:49
from __future__ import unicode_literals

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commandes', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='acte_engagement',
            field=models.FileField(upload_to='commandes/'),
        ),
        migrations.AlterField(
            model_name='order',
            name='date',
            field=models.DateField(default=datetime.date(2018, 11, 16), null=True, verbose_name='Date de la demande'),
        ),
        migrations.AlterField(
            model_name='order',
            name='dpo_cnil',
            field=models.FileField(upload_to='commandes/'),
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[(1, 'En cours'), (2, 'Validée'), (3, 'Refusée')], default=0, max_length=30, verbose_name='Staut de la demande'),
        ),
    ]
