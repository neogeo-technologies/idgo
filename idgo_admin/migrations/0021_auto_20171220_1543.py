# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-12-20 14:43
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0020_auto_20171219_1757'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='organisation',
            options={'ordering': ['name']},
        ),
    ]
