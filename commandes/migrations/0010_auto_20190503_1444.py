# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-05-03 12:44
from __future__ import unicode_literals

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commandes', '0009_auto_20190327_1442'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='date',
            field=models.DateField(default=datetime.date(2019, 5, 3), null=True, verbose_name='Date de la demande'),
        ),
    ]