# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-02-25 14:59
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0099_auto_20190225_1540'),
    ]

    operations = [
        migrations.AlterField(
            model_name='license',
            name='alternate_titles',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), null=True, size=None, verbose_name='Alternate titles'),
        ),
        migrations.AlterField(
            model_name='license',
            name='alternate_urls',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.URLField(), null=True, size=None, verbose_name='Alternate URLs'),
        ),
        migrations.AlterField(
            model_name='license',
            name='domain_content',
            field=models.BooleanField(default=False, verbose_name='Domain Content'),
        ),
        migrations.AlterField(
            model_name='license',
            name='domain_data',
            field=models.BooleanField(default=False, verbose_name='Domain Data'),
        ),
        migrations.AlterField(
            model_name='license',
            name='domain_software',
            field=models.BooleanField(default=False, verbose_name='Domain Software'),
        ),
        migrations.AlterField(
            model_name='license',
            name='maintainer',
            field=models.TextField(null=True, verbose_name='Maintainer'),
        ),
        migrations.AlterField(
            model_name='license',
            name='od_conformance',
            field=models.CharField(choices=[('approved', 'Approved'), ('not reviewed', 'Not reviewed'), ('rejected', 'Rejected')], default='not reviewed', max_length=30, null=True, verbose_name='Open Definition Conformance'),
        ),
        migrations.AlterField(
            model_name='license',
            name='osd_conformance',
            field=models.CharField(choices=[('approved', 'Approved'), ('not reviewed', 'Not reviewed'), ('rejected', 'Rejected')], default='not reviewed', max_length=30, null=True, verbose_name='Open Source Definition Conformance'),
        ),
        migrations.AlterField(
            model_name='license',
            name='slug',
            field=models.SlugField(max_length=100, null=True, verbose_name='Identifier'),
        ),
        migrations.AlterField(
            model_name='license',
            name='status',
            field=models.CharField(choices=[('active', 'Active'), ('deleted', 'Deleted')], default='active', max_length=7, verbose_name='Status'),
        ),
        migrations.AlterField(
            model_name='license',
            name='title',
            field=models.TextField(verbose_name='Title'),
        ),
        migrations.AlterField(
            model_name='license',
            name='url',
            field=models.URLField(null=True, verbose_name='URL'),
        ),
    ]
