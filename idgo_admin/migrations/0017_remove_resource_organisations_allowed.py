# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-07-31 07:36
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0016_auto_20170728_1513'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='resource',
            name='organisations_allowed',
        ),
    ]
