# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-07-28 07:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0006_auto_20170727_1353'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='date_creation',
            field=models.DateField(blank=True, null=True, verbose_name='Date de création du jeu de donnée'),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='date_modification',
            field=models.DateField(blank=True, null=True, verbose_name='Date de dernière modification du jeu de donnée'),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='date_publication',
            field=models.DateField(blank=True, null=True, verbose_name='Date de publication du jeu de donnée'),
        ),
    ]
