# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-11-02 15:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0007_auto_20171102_1622'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='thumbnail',
            field=models.ImageField(blank=True, null=True, upload_to='thumbnails/'),
        ),
    ]