# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-11-14 14:58
from __future__ import unicode_literals

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('idgo_admin', '0080_resource_ftp_file'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=datetime.date(2018, 11, 14), null=True, verbose_name='Date de la demande')),
                ('status', models.CharField(choices=[(1, 'En cours'), (2, 'Validée'), (3, 'Refusée')], default=1, max_length=30, verbose_name='Staut de la demande')),
                ('dpo_cnil', models.FileField(upload_to='')),
                ('acte_engagement', models.FileField(upload_to='')),
                ('applicant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Demandeur')),
                ('organisation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Organisation', verbose_name='Organisation')),
            ],
            options={
                'verbose_name': 'Commande de fichiers fonciers',
                'verbose_name_plural': 'Commandes de fichiers fonciers',
            },
        ),
    ]