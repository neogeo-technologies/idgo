# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-10-09 08:02
from __future__ import unicode_literals

from django.conf import settings
import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import taggit.managers
import uuid


class Migration(migrations.Migration):

    replaces = [('idgo_admin', '0001_initial'), ('idgo_admin', '0002_auto_20171003_1418'), ('idgo_admin', '0003_remove_jurisdiction_geom')]

    initial = True

    dependencies = [
        ('taggit', '0002_auto_20150616_2121'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountActions',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('action', models.CharField(blank=True, choices=[('confirm_mail', "Confirmation de l'email par l'utilisateur"), ('confirm_new_organisation', "Confirmation par un administrateur de la création d'une organisation par l'utilisateur"), ('confirm_rattachement', "Rattachement d'un utilisateur à une organsiation par un administrateur"), ('confirm_referent', "Confirmation du rôle de réferent d'une organisation pour un utilisatur par un administrateur"), ('confirm_contribution', "Confirmation du rôle de contributeur d'une organisation pour un utilisatur par un administrateur"), ('reset_password', 'Réinitialisation du mot de passe')], default='confirm_mail', max_length=250, null=True, verbose_name='Action de gestion de profile')),
                ('created', models.DateField(auto_now_add=True)),
                ('closed', models.DateField(blank=True, null=True, verbose_name="Date de validation de l'action")),
            ],
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Nom')),
                ('description', models.CharField(max_length=1024, verbose_name='Description')),
                ('ckan_slug', models.SlugField(blank=True, max_length=100, unique=True, verbose_name='Ckan_ID')),
                ('sync_in_ckan', models.BooleanField(default=False, verbose_name='Synchro CKAN')),
            ],
            options={
                'verbose_name': 'Catégorie',
            },
        ),
        migrations.CreateModel(
            name='Commune',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=5, verbose_name='Code INSEE')),
                ('name', models.CharField(max_length=100, verbose_name='Nom')),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(blank=True, null=True, srid=2154, verbose_name='Geometrie')),
            ],
        ),
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Nom')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('ckan_slug', models.SlugField(blank=True, max_length=100, null=True, unique=True, verbose_name='Ckan_ID')),
                ('ckan_id', models.UUIDField(blank=True, db_index=True, null=True, unique=True, verbose_name='Ckan UUID')),
                ('is_inspire', models.BooleanField(default=False, verbose_name="L'URL Inspire est valide")),
                ('geocover', models.CharField(blank=True, choices=[('regionale', 'Régionale'), ('international', 'Internationale'), ('european', 'Européenne'), ('national', 'Nationale'), ('departementale', 'Départementale'), ('intercommunal', 'Inter-Communale'), ('communal', 'Communale')], default='regionale', max_length=30, null=True, verbose_name='Couverture géographique')),
                ('date_creation', models.DateField(blank=True, null=True, verbose_name='Date de création du jeu de données')),
                ('date_publication', models.DateField(blank=True, null=True, verbose_name='Date de publication du jeu de données')),
                ('date_modification', models.DateField(blank=True, null=True, verbose_name='Date de dernière modification du jeu de données')),
                ('update_freq', models.CharField(choices=[('never', 'Jamais'), ('annualy', 'Annuelle'), ('monthly', 'Mensuelle'), ('weekly', 'Hebdomadaire'), ('daily', 'Quotidienne'), ('continue', 'Continue'), ('realtime', 'Temps réel')], default='never', max_length=30, verbose_name='Fréquence de mise à jour')),
                ('owner_email', models.EmailField(blank=True, max_length=254, null=True, verbose_name='E-mail du producteur de la donnée')),
                ('published', models.BooleanField(default=False, verbose_name='Etat du jeu de donnée')),
                ('geonet_id', models.UUIDField(blank=True, db_index=True, null=True, unique=True, verbose_name='Metadonnées UUID')),
                ('categories', models.ManyToManyField(to='idgo_admin.Category', verbose_name="Catégories d'appartenance")),
                ('editor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('keywords', taggit.managers.TaggableManager(blank=True, help_text='A comma-separated list of tags.', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags')),
            ],
            options={
                'verbose_name': 'Jeu de données',
                'verbose_name_plural': 'Jeux de données',
            },
        ),
        migrations.CreateModel(
            name='Financier',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=250, verbose_name='Nom du financeur')),
                ('code', models.CharField(max_length=250, verbose_name='Code du financeur')),
            ],
            options={
                'verbose_name': "Nom du financeur d'une organisation",
                'verbose_name_plural': 'Noms des financeurs',
            },
        ),
        migrations.CreateModel(
            name='Jurisdiction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=10, verbose_name='Code INSEE')),
                ('name', models.CharField(max_length=100, verbose_name='Nom')),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(blank=True, null=True, srid=2154, verbose_name='Geometrie')),
                ('communes', models.ManyToManyField(to='idgo_admin.Commune')),
            ],
            options={
                'verbose_name': 'Territoire de compétence',
            },
        ),
        migrations.CreateModel(
            name='LiaisonsContributeurs',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateField(auto_now_add=True)),
                ('validated_on', models.DateField(blank=True, null=True, verbose_name="Date de validation de l'action")),
            ],
        ),
        migrations.CreateModel(
            name='LiaisonsReferents',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateField(auto_now_add=True)),
                ('validated_on', models.DateField(blank=True, null=True, verbose_name="Date de validation de l'action")),
            ],
        ),
        migrations.CreateModel(
            name='LiaisonsResources',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateField(auto_now_add=True)),
                ('validated_on', models.DateField(blank=True, null=True, verbose_name="Date de validation de l'action")),
            ],
        ),
        migrations.CreateModel(
            name='License',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('license_id', models.CharField(max_length=30, verbose_name='id')),
                ('domain_content', models.BooleanField(default=False)),
                ('domain_data', models.BooleanField(default=False)),
                ('domain_software', models.BooleanField(default=False)),
                ('status', models.CharField(default='active', max_length=30, verbose_name='Statut')),
                ('maintainer', models.CharField(blank=True, max_length=50, verbose_name='Maintainer')),
                ('od_conformance', models.CharField(blank=True, default='approved', max_length=30, verbose_name='od_conformance')),
                ('osd_conformance', models.CharField(blank=True, default='not reviewed', max_length=30, verbose_name='osd_conformance')),
                ('title', models.CharField(max_length=100, verbose_name='Nom')),
                ('url', models.URLField(blank=True, verbose_name='url')),
            ],
            options={
                'verbose_name': 'Licence',
            },
        ),
        migrations.CreateModel(
            name='Mail',
            fields=[
                ('template_name', models.CharField(max_length=255, primary_key=True, serialize=False, verbose_name='Nom du model du message')),
                ('subject', models.CharField(blank=True, max_length=255, null=True, verbose_name='Objet')),
                ('message', models.TextField(blank=True, null=True, verbose_name='Corps du message')),
                ('from_email', models.EmailField(default='idgo@neogeo-technologies.fr', max_length=254, verbose_name='Adresse expediteur')),
            ],
        ),
        migrations.CreateModel(
            name='Organisation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=150, unique=True, verbose_name='Nom')),
                ('ckan_slug', models.SlugField(max_length=150, unique=True, verbose_name='CKAN ID')),
                ('ckan_id', models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='Ckan UUID')),
                ('website', models.URLField(blank=True, verbose_name='Site web')),
                ('email', models.EmailField(blank=True, max_length=254, null=True, verbose_name="Adresse mail de l'organisation")),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('logo', models.ImageField(blank=True, null=True, upload_to='logos/', verbose_name='Logo')),
                ('address', models.CharField(blank=True, max_length=100, null=True, verbose_name='Adresse')),
                ('postcode', models.CharField(blank=True, max_length=100, null=True, verbose_name='Code postal')),
                ('city', models.CharField(blank=True, max_length=100, null=True, verbose_name='Ville')),
                ('org_phone', models.CharField(blank=True, max_length=10, null=True, verbose_name='Téléphone')),
                ('is_active', models.BooleanField(default=False, verbose_name='Création validée par un administrateur')),
                ('financier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Financier')),
                ('jurisdiction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Jurisdiction', verbose_name='Territoire de compétence')),
                ('license', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.License')),
            ],
        ),
        migrations.CreateModel(
            name='OrganisationType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='Dénomination')),
                ('code', models.CharField(max_length=3, verbose_name='Code')),
            ],
            options={
                'verbose_name': "Type d'organisation",
                'verbose_name_plural': "Types d'organisations",
            },
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(blank=True, max_length=10, null=True, verbose_name='Téléphone')),
                ('is_active', models.BooleanField(default=False, verbose_name='Validation suite à confirmation mail par utilisateur')),
                ('membership', models.BooleanField(default=False, verbose_name="Etat de rattachement profile-organisation d'appartenance")),
                ('contributions', models.ManyToManyField(related_name='profile_contributions', through='idgo_admin.LiaisonsContributeurs', to='idgo_admin.Organisation', verbose_name="Organisations dont l'utiliateur est contributeur")),
                ('organisation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Organisation', verbose_name="Organisation d'appartenance")),
                ('referents', models.ManyToManyField(related_name='profile_referents', through='idgo_admin.LiaisonsReferents', to='idgo_admin.Organisation', verbose_name="Organisations dont l'utiliateur est réferent")),
            ],
        ),
        migrations.CreateModel(
            name='Resource',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='Nom')),
                ('ckan_id', models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='Ckan UUID')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('referenced_url', models.URLField(blank=True, null=True, verbose_name='Référencer une URL')),
                ('dl_url', models.URLField(blank=True, null=True, verbose_name='Télécharger depuis une URL')),
                ('up_file', models.FileField(blank=True, null=True, upload_to='', verbose_name='Téléverser un ou plusieurs fichiers')),
                ('lang', models.CharField(choices=[('french', 'Français'), ('english', 'Anglais'), ('italian', 'Italien'), ('german', 'Allemand'), ('other', 'Autre')], default='french', max_length=10, verbose_name='Langue')),
                ('restricted_level', models.CharField(blank=True, choices=[('0', 'Tous les utilisateurs'), ('1', 'Utilisateurs authentifiés'), ('2', 'Utilisateurs authentifiés avec droits spécifiques'), ('3', 'Utilisateurs de cette organisations uniquements'), ('4', 'Organisations spécifiées')], default='0', max_length=20, null=True, verbose_name="Restriction d'accès")),
                ('bbox', django.contrib.gis.db.models.fields.PolygonField(blank=True, null=True, srid=4326, verbose_name='Rectangle englobant')),
                ('geo_restriction', models.BooleanField(default=False, verbose_name='Restriction géographique')),
                ('created_on', models.DateTimeField(blank=True, default=django.utils.timezone.now, null=True, verbose_name='Date de création de la resource')),
                ('last_update', models.DateTimeField(blank=True, null=True, verbose_name='Date de dernière modification de la resource')),
                ('data_type', models.CharField(choices=[('data', 'Données'), ('resource', 'Resources')], max_length=10, verbose_name='type de resources')),
                ('dataset', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Dataset')),
            ],
            options={
                'verbose_name': 'Ressource',
            },
        ),
        migrations.CreateModel(
            name='ResourceFormats',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('extension', models.CharField(max_length=30, unique=True, verbose_name='Format')),
                ('ckan_view', models.CharField(blank=True, choices=[(None, 'N/A'), ('recline_view', 'recline_view'), ('text_view', 'text_view'), ('geo_view', 'geo_view'), ('recline_view', 'recline_view'), ('pdf_view', 'pdf_view')], max_length=100, null=True, verbose_name='Vue')),
            ],
        ),
        migrations.AddField(
            model_name='resource',
            name='format_type',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.ResourceFormats'),
        ),
        migrations.AddField(
            model_name='resource',
            name='organisations_allowed',
            field=models.ManyToManyField(blank=True, to='idgo_admin.Organisation', verbose_name='Organisations autorisées'),
        ),
        migrations.AddField(
            model_name='resource',
            name='users_allowed',
            field=models.ManyToManyField(blank=True, to=settings.AUTH_USER_MODEL, verbose_name='Utilisateurs autorisés'),
        ),
        migrations.AddField(
            model_name='profile',
            name='resources',
            field=models.ManyToManyField(related_name='profile_resources', through='idgo_admin.LiaisonsResources', to='idgo_admin.Resource', verbose_name="Resources publiées par l'utilisateur"),
        ),
        migrations.AddField(
            model_name='profile',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='organisation',
            name='organisation_type',
            field=models.ForeignKey(blank=True, default='1', null=True, on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.OrganisationType', verbose_name="Type d'organisation"),
        ),
        migrations.AddField(
            model_name='liaisonsresources',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Profile'),
        ),
        migrations.AddField(
            model_name='liaisonsresources',
            name='resource',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Resource'),
        ),
        migrations.AddField(
            model_name='liaisonsreferents',
            name='organisation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Organisation'),
        ),
        migrations.AddField(
            model_name='liaisonsreferents',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Profile'),
        ),
        migrations.AddField(
            model_name='liaisonscontributeurs',
            name='organisation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Organisation'),
        ),
        migrations.AddField(
            model_name='liaisonscontributeurs',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Profile'),
        ),
        migrations.AddField(
            model_name='dataset',
            name='license',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.License', verbose_name="Licence d'utilisation"),
        ),
        migrations.AddField(
            model_name='dataset',
            name='organisation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Organisation', verbose_name="Organisation d'appartenance"),
        ),
        migrations.AddField(
            model_name='accountactions',
            name='org_extras',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Organisation'),
        ),
        migrations.AddField(
            model_name='accountactions',
            name='profile',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='idgo_admin.Profile'),
        ),
        migrations.AlterUniqueTogether(
            name='liaisonsreferents',
            unique_together=set([('profile', 'organisation')]),
        ),
        migrations.AlterUniqueTogether(
            name='liaisonscontributeurs',
            unique_together=set([('profile', 'organisation')]),
        ),
        migrations.RemoveField(
            model_name='category',
            name='sync_in_ckan',
        ),
        migrations.RemoveField(
            model_name='jurisdiction',
            name='geom',
        ),
    ]