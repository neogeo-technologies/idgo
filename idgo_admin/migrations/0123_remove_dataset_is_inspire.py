# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-03-15 15:55
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0122_auto_20190315_1502'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dataset',
            name='is_inspire',
        ),
    ]