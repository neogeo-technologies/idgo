# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-11-02 15:22
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0006_auto_20171102_1621'),
    ]

    operations = [
        migrations.RenameField(
            model_name='dataset',
            old_name='support_new',
            new_name='support',
        ),
    ]
