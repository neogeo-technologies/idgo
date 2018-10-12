# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-10-04 09:54
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('idgo_admin', '0064_auto_20181001_1530'),
    ]

    operations = [
        migrations.CreateModel(
            name='CkanHarvester',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(blank=True, verbose_name='URL')),
                ('sync_with', django.contrib.postgres.fields.ArrayField(base_field=models.SlugField(max_length=100), blank=True, null=True, size=None, verbose_name='Organisations synchronisées')),
                ('sync_frequency', models.CharField(blank=True, choices=[('never', 'Jamais'), ('daily', 'Quotidienne (tous les jours à minuit)'), ('weekly', 'Hebdomadaire (tous les lundi)'), ('bimonthly', 'Bimensuelle (1er et 15 de chaque mois)'), ('monthly', 'Mensuelle (1er de chaque mois)'), ('quarterly', 'Trimestrielle (1er des mois de janvier, avril, juillet, octobre)'), ('biannual', 'Semestrielle (1er janvier et 1er juillet)'), ('annual', 'Annuelle (1er janvier)')], default='never', max_length=20, null=True, verbose_name='Fréquence de synchronisation')),
                ('organisation', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Organisation')),
            ],
        ),
        migrations.AlterField(
            model_name='accountactions',
            name='action',
            field=models.CharField(blank=True, choices=[('confirm_mail', "Confirmation de l'e-mail par l'utilisateur"), ('confirm_new_organisation', "Confirmation par un administrateur de la création d'une organisation par l'utilisateur"), ('confirm_rattachement', "Rattachement d'un utilisateur à une organisation par un administrateur"), ('confirm_referent', "Confirmation du rôle de réferent d'une organisation pour un utilisateur par un administrateur"), ('confirm_contribution', "Confirmation du rôle de contributeur d'une organisation pour un utilisateur par un administrateur"), ('reset_password', 'Réinitialisation du mot de passe'), ('set_password_admin', 'Initialisation du mot de passe suite à une inscription par un administrateur')], default='confirm_mail', max_length=250, null=True, verbose_name='Action de gestion de profile'),
        ),
    ]
