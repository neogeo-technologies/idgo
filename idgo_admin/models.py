# Copyright (c) 2017-2018 Datasud.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.mail import send_mail
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_delete
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.datagis import drop_table
from idgo_admin.datagis import get_extent
from idgo_admin.datagis import ogr2postgis
from idgo_admin.exceptions import ExceedsMaximumLayerNumberFixedError
from idgo_admin.exceptions import NotOGRError
from idgo_admin.exceptions import NotSupportedSrsError
from idgo_admin.exceptions import SizeLimitExceededError
from idgo_admin.mra_client import MRAConflictError
from idgo_admin.mra_client import MRAHandler
from idgo_admin.mra_client import MRANotFoundError
from idgo_admin.utils import download
from idgo_admin.utils import PartialFormatter
from idgo_admin.utils import remove_dir
from idgo_admin.utils import remove_file
from idgo_admin.utils import slugify as _slugify  # Pas forcement utile de garder l'original
import json
import os
from pathlib import Path
import re
from taggit.managers import TaggableManager
from urllib.parse import urljoin
import uuid


TODAY = timezone.now().date()
GEONETWORK_URL = settings.GEONETWORK_URL
try:
    DOWNLOAD_SIZE_LIMIT = settings.DOWNLOAD_SIZE_LIMIT
except AttributeError:
    DOWNLOAD_SIZE_LIMIT = 104857600  # 100Mio


if settings.STATIC_ROOT:
    locales_path = os.path.join(
        settings.STATIC_ROOT, 'mdedit/config/locales/fr/locales.json')
else:
    locales_path = os.path.join(
        settings.BASE_DIR,
        'idgo_admin/static/mdedit/config/locales/fr/locales.json')

try:
    with open(locales_path, 'r', encoding='utf-8') as f:
        MDEDIT_LOCALES = json.loads(f.read())

        AUTHORIZED_ISO_TOPIC = (
            (iso_topic['id'], iso_topic['value']) for iso_topic
            in MDEDIT_LOCALES['codelists']['MD_TopicCategoryCode'])

        AUTHORIZED_PROTOCOL = (
            (protocol['id'], protocol['value']) for protocol
            in MDEDIT_LOCALES['codelists']['MD_LinkageProtocolCode'])
except Exception:
    MDEDIT_LOCALES = ''
    AUTHORIZED_ISO_TOPIC = ''
    AUTHORIZED_PROTOCOL = ''


OWS_URL_PATTERN = settings.OWS_URL_PATTERN
MRA = settings.MRA


class SupportedCrs(models.Model):

    auth_name = models.CharField(
        verbose_name='Authority Name', max_length=100, default='EPSG')

    auth_code = models.CharField(
        verbose_name='Authority Code', max_length=100)

    description = models.TextField(
        verbose_name='Description', blank=True, null=True)

    class Meta(object):
        verbose_name = "CRS supporté par l'application"
        verbose_name_plural = "CRS supportés par l'application"

    def __str__(self):
        return '{}:{} ({})'.format(
            self.auth_name, self.auth_code, self.description)


class ResourceFormats(models.Model):

    PROTOCOL_CHOICES = AUTHORIZED_PROTOCOL

    CKAN_CHOICES = (
        (None, 'N/A'),
        ('text_view', 'text_view'),
        ('geo_view', 'geo_view'),
        ('recline_view', 'recline_view'),
        ('pdf_view', 'pdf_view'))

    extension = models.CharField('Format', max_length=30, unique=True)

    ckan_view = models.CharField(
        'Vue', max_length=100, choices=CKAN_CHOICES, blank=True, null=True)

    protocol = models.CharField(
        'Protocole', max_length=100, blank=True, null=True, choices=PROTOCOL_CHOICES)

    class Meta(object):
        verbose_name = 'Format de ressource'
        verbose_name_plural = 'Formats de ressource'

    def __str__(self):
        return self.extension


def upload_resource(instance, filename):
    return _slugify(filename, exclude_dot=False)


class Resource(models.Model):

    FREQUENCY_CHOICES = (
        ('never', 'Jamais'),
        ('daily', 'Quotidienne (tous les jours à minuit)'),
        ('weekly', 'Hebdomadaire (tous les lundi)'),
        ('bimonthly', 'Bimensuelle (1er et 15 de chaque mois)'),
        ('monthly', 'Mensuelle (1er de chaque mois)'),
        ('quarterly', 'Trimestrielle (1er des mois de janvier, avril, juillet, octobre)'),
        ('biannual', 'Semestrielle (1er janvier et 1er juillet)'),
        ('annual', 'Annuelle (1er janvier)'))

    LANG_CHOICES = (
        ('french', 'Français'),
        ('english', 'Anglais'),
        ('italian', 'Italien'),
        ('german', 'Allemand'),
        ('other', 'Autre'))

    LEVEL_CHOICES = (
        ('0', 'Tous les utilisateurs'),
        ('1', 'Utilisateurs authentifiés'),
        ('2', 'Utilisateurs authentifiés avec droits spécifiques'),
        ('3', 'Utilisateurs de cette organisations uniquements'),
        ('4', 'Organisations spécifiées'))

    TYPE_CHOICES = (
        ('raw', 'Données brutes'),
        ('annexe', 'Documentation associée'),
        ('service', 'Service'))

    name = models.CharField(
        verbose_name='Nom', max_length=150)

    ckan_id = models.UUIDField(
        verbose_name='Ckan UUID', default=uuid.uuid4, editable=False)

    datagis_id = ArrayField(
        models.CharField(max_length=150),
        verbose_name='DataGIS IDs', blank=True, null=True, editable=False)

    description = models.TextField(
        verbose_name='Description', blank=True, null=True)

    referenced_url = models.URLField(
        verbose_name='Référencer une URL',
        max_length=2000, blank=True, null=True)

    dl_url = models.URLField(
        verbose_name='Télécharger depuis une URL',
        max_length=2000, blank=True, null=True)

    up_file = models.FileField(
        verbose_name='Téléverser un ou plusieurs fichiers',
        blank=True, null=True, upload_to=upload_resource)

    lang = models.CharField(
        verbose_name='Langue', choices=LANG_CHOICES,
        default='french', max_length=10)

    format_type = models.ForeignKey(
        ResourceFormats, verbose_name='Format', default=0)

    restricted_level = models.CharField(
        verbose_name="Restriction d'accès", choices=LEVEL_CHOICES,
        default='0', max_length=20, blank=True, null=True)

    profiles_allowed = models.ManyToManyField(
        to='Profile', verbose_name='Utilisateurs autorisés', blank=True)

    organisations_allowed = models.ManyToManyField(
        to='Organisation', verbose_name='Organisations autorisées', blank=True)

    dataset = models.ForeignKey(
        to='Dataset', verbose_name='Jeu de données',
        on_delete=models.SET_NULL, blank=True, null=True)

    bbox = models.PolygonField(
        verbose_name='Rectangle englobant', blank=True, null=True)

    geo_restriction = models.BooleanField(
        verbose_name='Restriction géographique', default=False)

    extractable = models.BooleanField(
        verbose_name='Extractible', default=True)

    ogc_services = models.BooleanField(
        verbose_name='Services OGC', default=False)

    created_on = models.DateTimeField(
        verbose_name='Date de création de la resource',
        blank=True, null=True, default=timezone.now)

    last_update = models.DateTimeField(
        verbose_name='Date de dernière modification de la resource',
        blank=True, null=True)

    data_type = models.CharField(
        verbose_name='Type de la ressource',
        choices=TYPE_CHOICES, max_length=10, default='raw')

    synchronisation = models.BooleanField(
        verbose_name='Synchronisation de données distante',
        default=False)

    sync_frequency = models.CharField(
        verbose_name='Fréquence de synchronisation',
        max_length=20,
        blank=True,
        null=True,
        choices=FREQUENCY_CHOICES,
        default='never')

    crs = models.ForeignKey(
        to='SupportedCrs', verbose_name='CRS',
        on_delete=models.SET_NULL, blank=True, null=True)

    class Meta(object):
        verbose_name = 'Ressource'

    def __str__(self):
        return self.name

    def disable_layers(self):
        if self.datagis_id:
            for l_name in self.datagis_id:
                MRAHandler.disable_layer(l_name)

    def enable_layers(self):
        if self.datagis_id:
            for l_name in self.datagis_id:
                MRAHandler.enable_layer(l_name)

    @property
    def is_datagis(self):
        return self.datagis_id and True or False

    def save(self, *args, **kwargs):

        previous = self.pk and Resource.objects.get(pk=self.pk) or None

        sync_ckan = 'sync_ckan' in kwargs and kwargs.pop('sync_ckan') or False
        file_extras = 'file_extras' in kwargs and kwargs.pop('file_extras') or None
        editor = 'editor' in kwargs and kwargs.pop('editor') or None

        # La restriction au territoire de compétence désactive tout service OGC
        self.ogc_services = not self.geo_restriction and True or False

        super().save(*args, **kwargs)

        self.dataset.date_modification = timezone.now().date()

        if sync_ckan:

            ckan_params = {
                'name': self.name,
                'description': self.description,
                'data_type': self.data_type,
                'format': self.format_type.extension,
                'view_type': self.format_type.ckan_view,
                'id': str(self.ckan_id),
                'lang': self.lang,
                # 'restricted_by_jurisdiction': self.geo_restriction,
                'url': ''}

            if self.restricted_level == '0':  # Public
                ckan_params['restricted'] = json.dumps({'level': 'public'})

            if self.restricted_level == '1':  # Registered users
                ckan_params['restricted'] = json.dumps({'level': 'registered'})

            if self.restricted_level == '2':  # Only allowed users
                ckan_params['restricted'] = json.dumps({
                    'allowed_users': ','.join(
                        self.profiles_allowed.exists() and [
                            p.user.username for p in self.profiles_allowed.all()] or []),
                    'level': 'only_allowed_users'})

            if self.restricted_level == '3':  # This organization
                ckan_params['restricted'] = json.dumps({
                    'allowed_users': ','.join(
                        get_all_users_for_organizations(self.organisations_allowed)),
                    'level': 'only_allowed_users'})

            if self.restricted_level == '4':  # Any organization
                ckan_params['restricted'] = json.dumps({
                    'allowed_users': ','.join(
                        get_all_users_for_organizations(self.organizations_allowed)),
                    'level': 'only_allowed_users'})

            if self.referenced_url:
                ckan_params['url'] = self.referenced_url
                ckan_params['resource_type'] = '{0}.{1}'.format(
                    self.name, self.format_type.ckan_view)

            if self.dl_url:
                try:
                    directory, filename, content_type = download(
                        self.dl_url, settings.MEDIA_ROOT,
                        max_size=DOWNLOAD_SIZE_LIMIT)
                except SizeLimitExceededError as e:
                    l = len(str(e.max_size))
                    if l > 6:
                        m = '{0} mo'.format(Decimal(int(e.max_size) / 1024 / 1024))
                    elif l > 3:
                        m = '{0} ko'.format(Decimal(int(e.max_size) / 1024))
                    else:
                        m = '{0} octets'.format(int(e.max_size))
                    raise ValidationError(
                        "La taille du fichier dépasse la limite autorisée : {0}.".format(m), code='dl_url')
                except Exception as e:
                    if e.__class__.__name__ == 'HTTPError':
                        if e.response.status_code == 404:
                            msg = "La ressource distante ne semble pas exister. Assurez-vous que l'URL soit correcte."
                        if e.response.status_code == 403:
                            msg = "Vous n'avez pas l'autorisation pour accéder à la ressource."
                        if e.response.status_code == 401:
                            msg = "Une authentification est nécessaire pour accéder à la ressource."
                    else:
                        msg = 'Le téléchargement du fichier a échoué.'
                    raise ValidationError(msg, code='dl_url')

                downloaded_file = File(open(filename, 'rb'))
                ckan_params['upload'] = downloaded_file
                ckan_params['size'] = downloaded_file.size
                ckan_params['mimetype'] = content_type
                ckan_params['resource_type'] = Path(filename).name

            if self.up_file and file_extras:  # Si nouveau fichier (uploaded)
                ckan_params['upload'] = self.up_file.file
                ckan_params.update(file_extras)

                filename = self.up_file.file.name

            if self.dl_url or (self.up_file and file_extras):
                extension = self.format_type.extension.lower()
                # Pour les archives, toujours vérifier si contient des données SIG.
                # Si c'est le cas, monter les données dans la base PostGIS dédiée,
                # puis ajouter au service OGC:WxS de l'organisation.
                if extension in ('zip', 'tar', 'geojson'):
                    existing_layers = {}
                    if previous and previous.datagis_id:
                        existing_layers = dict(
                            (re.sub('^(\w+)_[a-z0-9]{7}$', '\g<1>', table_name), table_name)
                            for table_name in previous.datagis_id)
                    try:
                        tables = ogr2postgis(
                            filename, extension=extension, update=existing_layers,
                            epsg=self.crs and self.crs.auth_code or None)
                    except (ExceedsMaximumLayerNumberFixedError,
                            NotOGRError, NotSupportedSrsError) as e:
                        if self.dl_url:
                            remove_dir(directory)
                        if self.up_file and file_extras:
                            remove_file(filename)
                        raise ValidationError(e.__str__(), code='__all__')
                    else:
                        datagis_id = []
                        crs = []
                        for table in tables:
                            datagis_id.append(table['id'])
                            crs.append(SupportedCrs.objects.get(
                                auth_name='EPSG', auth_code=table['epsg']))
                        self.datagis_id = datagis_id
                        self.crs = crs[0]
                        try:
                            MRAHandler.publish_layers_resource(self)
                        except Exception as e:
                            for table_id in self.datagis_id:
                                drop_table(str(table_id))
                            raise e
                    ckan_params['crs'] = self.crs.description
                else:
                    self.datagis_id = None
                super().save()

            # Puis supprimer les données
            if self.dl_url:
                remove_dir(directory)
            if self.up_file and file_extras:
                remove_file(filename)
            # TODO FACTORISER

            # Si l'utilisateur courant n'est pas l'éditeur d'un jeu
            # de données existant mais administrateur ou un référent technique,
            # alors l'admin Ckan édite le jeu de données..
            if editor == self.dataset.editor:
                ckan_user = ckan_me(ckan.get_user(editor.username)['apikey'])
            else:
                ckan_user = ckan_me(ckan.apikey)

            ws_name = self.dataset.organisation.ckan_slug
            ds_name = 'public'

            # TODO Gérer les erreurs + factoriser
            if previous and previous.datagis_id and \
                    set(previous.datagis_id) != set(self.datagis_id):
                # Nettoyer les anciennes resources SIG..
                for datagis_id in previous.datagis_id:
                    ft_name = str(datagis_id)
                    # Supprimer les objects MRA  (TODO en cascade dans MRA)
                    try:
                        MRAHandler.del_layer(ft_name)
                        MRAHandler.del_featuretype(ws_name, ds_name, ft_name)
                    except MRANotFoundError:
                        pass
                    # Supprimer la ressource CKAN
                    ckan_user.delete_resource(ft_name)
                    # Supprimer les anciennes tables GIS
                    drop_table(ft_name)

            ckan_package = ckan_user.get_package(str(self.dataset.ckan_id))
            ckan_user.publish_resource(ckan_package, **ckan_params)

            if self.datagis_id:
                # Publier les nouvelles resources SIG..
                for datagis_id in self.datagis_id:
                    ft_name = str(datagis_id)
                    ckan_params = {
                        'id': ft_name,
                        'name': '{} (OGC:WMS)'.format(self.name),
                        'description': 'Visualiseur cartographique',
                        'data_type': 'service',
                        'crs': SupportedCrs.objects.get(
                            auth_name='EPSG', auth_code='4171').description,
                        'lang': self.lang,
                        'format': 'WMS',
                        # 'restricted_by_jurisdiction': self.geo_restriction,
                        'url': '{0}#{1}'.format(
                            OWS_URL_PATTERN.format(organisation=ws_name), ft_name),
                        'view_type': 'geo_view'}
                    ckan_user.publish_resource(ckan_package, **ckan_params)

                resources = Resource.objects.filter(dataset=self.dataset)
                self.dataset.bbox = get_extent(
                    [item for sub in [r.datagis_id for r in resources] for item in sub])

            ckan_user.close()
            # Endif sync_ckan

        # if not previous or (
        #         previous and previous.ogc_services != self.ogc_services):
        if self.ogc_services:
            self.enable_layers()
        else:
            self.disable_layers()

        self.dataset.save()


class Commune(models.Model):

    code = models.CharField(
        verbose_name='Code INSEE', max_length=5, primary_key=True)

    name = models.CharField(verbose_name='Nom', max_length=100)

    geom = models.MultiPolygonField(
        verbose_name='Geometrie', srid=2154, blank=True, null=True)

    objects = models.GeoManager()

    class Meta(object):
        verbose_name = 'Commune'
        verbose_name_plural = 'Communes'
        ordering = ['name']

    def __str__(self):
        return '{} ({})'.format(self.name, self.code)


class Jurisdiction(models.Model):

    code = models.CharField(
        verbose_name='Code INSEE', max_length=10, primary_key=True)

    name = models.CharField(verbose_name='Nom', max_length=100)

    objects = models.GeoManager()

    class Meta(object):
        verbose_name = 'Territoire de compétence'
        verbose_name_plural = 'Territoires de compétence'

    def __str__(self):
        return self.name


class JurisdictionCommune(models.Model):

    jurisdiction = models.ForeignKey(
        to='Jurisdiction', on_delete=models.CASCADE,
        verbose_name='Territoire de compétence', to_field='code')

    commune = models.ForeignKey(
        to='Commune', on_delete=models.CASCADE,
        verbose_name='Commune', to_field='code')

    created_on = models.DateField(auto_now_add=True)

    created_by = models.ForeignKey(
        to="Profile", null=True, on_delete=models.SET_NULL,
        verbose_name="Profil de l'utilisateur",
        related_name='creates_jurisdiction')

    class Meta(object):
        verbose_name = 'Territoire de compétence / Commune'
        verbose_name_plural = 'Territoires de compétence / Communes'

    def __str__(self):
        return '{0}: {1}'.format(self.jurisdiction, self.commune)


class Financier(models.Model):

    name = models.CharField('Nom du financeur', max_length=250)

    code = models.CharField('Code du financeur', max_length=250)

    class Meta(object):
        verbose_name = "Financeur d'une action"
        verbose_name_plural = "Financeurs"
        ordering = ('name', )

    def __str__(self):
        return self.name


class OrganisationType(models.Model):

    name = models.CharField(verbose_name="Type d'organisation", max_length=250)

    code = models.CharField(verbose_name="Code", max_length=250)

    class Meta(object):
        verbose_name = "Type d'organisation"
        verbose_name_plural = "Types d'organisations"
        ordering = ('name', )

    def __str__(self):
        return self.name


def get_all_users_for_organizations(list_id):
    print(list_id)
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


class Organisation(models.Model):

    name = models.CharField(
        verbose_name='Nom', max_length=100, unique=True, db_index=True)

    organisation_type = models.ForeignKey(
        to='OrganisationType', verbose_name="Type d'organisation",
        default='1', blank=True, null=True, on_delete=models.SET_NULL)

    jurisdiction = models.ForeignKey(
        to='Jurisdiction', blank=True, null=True,
        verbose_name="Territoire de compétence")

    ckan_slug = models.SlugField(
        verbose_name='CKAN ID', max_length=100, unique=True, db_index=True)

    ckan_id = models.UUIDField(
        verbose_name='Ckan UUID', default=uuid.uuid4, editable=False)

    website = models.URLField(verbose_name='Site web', blank=True)

    email = models.EmailField(
        verbose_name="Adresse mail de l'organisation", blank=True, null=True)

    description = models.TextField(
        verbose_name='Description', blank=True, null=True)

    logo = models.ImageField(
        verbose_name='Logo', upload_to='logos/', blank=True, null=True)

    address = models.TextField(
        verbose_name='Adresse', blank=True, null=True)

    postcode = models.CharField(
        verbose_name='Code postal', max_length=100, blank=True, null=True)

    city = models.CharField(
        verbose_name='Ville', max_length=100, blank=True, null=True)

    org_phone = models.CharField(
        verbose_name='Téléphone', max_length=10, blank=True, null=True)

    license = models.ForeignKey(
        to='License', on_delete=models.CASCADE,
        verbose_name='Licence', blank=True, null=True)

    financier = models.ForeignKey(
        to='Financier', on_delete=models.SET_NULL,
        verbose_name="Financeur", blank=True, null=True)

    is_active = models.BooleanField('Organisation active', default=False)

    is_crige_partner = models.BooleanField(
        verbose_name='Organisation partenaire du CRIGE', default=False)

    class Meta(object):
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def ows_url(self):
        if MRAHandler.is_workspace_exists(self.ckan_slug):
            return OWS_URL_PATTERN.format(organisation=self.ckan_slug)
        # else: return None


class Profile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    organisation = models.ForeignKey(
        to='Organisation', on_delete=models.SET_NULL,
        verbose_name="Organisation d'appartenance", blank=True, null=True)

    referents = models.ManyToManyField(
        to='Organisation', through='LiaisonsReferents',
        verbose_name="Organisations dont l'utilisateur est réferent",
        related_name='profile_referents')

    contributions = models.ManyToManyField(
        to='Organisation', through='LiaisonsContributeurs',
        verbose_name="Organisations dont l'utilisateur est contributeur",
        related_name='profile_contributions')

    resources = models.ManyToManyField(
        to='Resource', through='LiaisonsResources',
        verbose_name="Resources publiées par l'utilisateur",
        related_name='profile_resources')

    phone = models.CharField(
        verbose_name='Téléphone', max_length=10, blank=True, null=True)

    is_active = models.BooleanField(
        verbose_name='Validation suite à confirmation mail par utilisateur',
        default=False)

    membership = models.BooleanField(
        verbose_name="Etat de rattachement profile-organisation d'appartenance",
        default=False)

    crige_membership = models.BooleanField(
        verbose_name='Utilisateur affilié au CRIGE', default=False)

    is_admin = models.BooleanField(
        verbose_name="Administrateur IDGO",
        default=False)

    class Meta(object):
        verbose_name = 'Profil utilisateur'
        verbose_name_plural = 'Profils des utilisateurs'

    def __str__(self):
        return self.user.username

    def nb_datasets(self, organisation):
        return Dataset.objects.filter(
            editor=self.user, organisation=organisation).count()

    def get_roles(self, organisation=None, dataset=None):

        if organisation:
            is_referent = LiaisonsReferents.objects.filter(
                profile=self,
                organisation=organisation,
                validated_on__isnull=False).exists()
        else:
            is_referent = LiaisonsReferents.objects.filter(
                profile=self,
                validated_on__isnull=False).exists()

        return {"is_admin": self.is_admin,
                "is_referent": is_referent,
                "is_editor": (self.user == dataset.editor) if dataset else False}


class LiaisonsReferents(models.Model):

    profile = models.ForeignKey(
        to='Profile', on_delete=models.CASCADE,
        verbose_name='Profil')

    organisation = models.ForeignKey(
        to='Organisation', on_delete=models.CASCADE,
        verbose_name='Organisation')

    created_on = models.DateField(auto_now_add=True)

    validated_on = models.DateField(
        verbose_name="Date de validation de l'action",
        blank=True, null=True, default=timezone.now)

    class Meta(object):
        unique_together = (('profile', 'organisation'),)

    def __str__(self):
        return '{full_name} ({username})--{organisation}'.format(
            full_name=self.profile.user.get_full_name(),
            username=self.profile.user.username,
            organisation=self.organisation.name)

    @classmethod
    def get_subordinated_organizations(cls, profile):
        if profile.is_admin:
            return Organisation.objects.filter(is_active=True)
        return [e.organisation for e
                in LiaisonsReferents.objects.filter(
                    profile=profile, validated_on__isnull=False)]

    @classmethod
    def get_pending(cls, profile):
        return [e.organisation for e
                in LiaisonsReferents.objects.filter(
                    profile=profile, validated_on=None)]


class LiaisonsContributeurs(models.Model):

    profile = models.ForeignKey(
        to='Profile', on_delete=models.CASCADE)

    organisation = models.ForeignKey(
        to='Organisation', on_delete=models.CASCADE)

    created_on = models.DateField(auto_now_add=True)

    validated_on = models.DateField(
        verbose_name="Date de validation de l'action", blank=True, null=True)

    class Meta(object):
        unique_together = (('profile', 'organisation'),)

    def __str__(self):
        return '{full_name} ({username})--{organisation}'.format(
            full_name=self.profile.user.get_full_name(),
            username=self.profile.user.username,
            organisation=self.organisation.name)

    @classmethod
    def get_contribs(cls, profile):
        return [e.organisation for e
                in LiaisonsContributeurs.objects.filter(
                    profile=profile, validated_on__isnull=False)]

    @classmethod
    def get_contributors(cls, organization):
        return [e.profile for e
                in LiaisonsContributeurs.objects.filter(
                    organisation=organization, validated_on__isnull=False)]

    @classmethod
    def get_pending(cls, profile):
        return [e.organisation for e
                in LiaisonsContributeurs.objects.filter(
                    profile=profile, validated_on=None)]


class LiaisonsResources(models.Model):

    profile = models.ForeignKey(to='Profile', on_delete=models.CASCADE)

    resource = models.ForeignKey(to='Resource', on_delete=models.CASCADE)

    created_on = models.DateField(auto_now_add=True)

    validated_on = models.DateField(
        verbose_name="Date de validation de l'action", blank=True, null=True)


class AccountActions(models.Model):

    ACTION_CHOICES = (
        ('confirm_mail', "Confirmation de l'email par l'utilisateur"),
        ('confirm_new_organisation', "Confirmation par un administrateur de la création d'une organisation par l'utilisateur"),
        ('confirm_rattachement', "Rattachement d'un utilisateur à une organisation par un administrateur"),
        ('confirm_referent', "Confirmation du rôle de réferent d'une organisation pour un utilisateur par un administrateur"),
        ('confirm_contribution', "Confirmation du rôle de contributeur d'une organisation pour un utilisateur par un administrateur"),
        ('reset_password', "Réinitialisation du mot de passe"),
        ('set_password_admin', "Initialisation du mot de passe suite à une inscription par un administrateur"))

    profile = models.ForeignKey(
        to='Profile', on_delete=models.CASCADE, blank=True, null=True)

    # Pour pouvoir reutiliser AccountActions pour demandes post-inscription
    organisation = models.ForeignKey(
        to='Organisation', on_delete=models.CASCADE, blank=True, null=True)

    key = models.UUIDField(default=uuid.uuid4, editable=False)

    action = models.CharField(
        verbose_name='Action de gestion de profile', blank=True, null=True,
        default='confirm_mail', max_length=250, choices=ACTION_CHOICES)

    created_on = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    closed = models.DateTimeField(
        verbose_name="Date de validation de l'action",
        blank=True, null=True)

    # Utilisées dans admin/user.py
    def orga_name(self):
        return str(self.organisation.name) if self.organisation else str('N/A')
    orga_name.short_description = "Nom de l'organsiation concernée"

    def get_path(self):
        choices = {
            'confirm_mail': ('confirmation_mail', {'key': self.key}),
            'confirm_new_organisation': ('confirm_new_orga', {'key': self.key}),
            'confirm_rattachement': ('confirm_rattachement', {'key': self.key}),
            'confirm_referent': ('confirm_referent', {'key': self.key}),
            'confirm_contribution': ('confirm_contribution', {'key': self.key}),
            'reset_password': ('password_manager', {'key': self.key, 'process': 'reset'}),
            'set_password_admin': ('password_manager', {'key': self.key, 'process': 'initiate'}),
            }
        return reverse('idgo_admin:{action}'.format(action=choices[self.action][0]), kwargs=choices[self.action][1])
    get_path.short_description = "Adresse de validation"


class Mail(models.Model):

    template_name = models.CharField(
        verbose_name='Nom du model du message',
        primary_key=True, max_length=255)

    subject = models.CharField(
        verbose_name='Objet', max_length=255, blank=True, null=True)

    message = models.TextField(
        verbose_name='Corps du message', blank=True, null=True)

    from_email = models.EmailField(
        verbose_name='Adresse expediteur',
        default=settings.DEFAULT_FROM_EMAIL)

    class Meta(object):
        verbose_name = 'e-mail'
        verbose_name_plural = 'e-mails'

    def __str__(self):
        return self.template_name

    @classmethod
    def superuser_mails(cls, receip_list):
        receip_list = receip_list + [
            usr.email for usr in User.objects.filter(
                is_superuser=True, is_active=True)]
        return receip_list

    @classmethod
    def admin_mails(cls, receip_list):
        receip_list = receip_list + [
            p.user.email for p in Profile.objects.filter(
                is_active=True, is_admin=True)]
        return receip_list

    @classmethod
    def referents_mails(cls, receip_list, organisation):
        receip_list = receip_list + [
            lr.profile.user.email for lr in LiaisonsReferents.objects.filter(
                organisation=organisation, validated_on__isnull=False)]
        return receip_list

    @classmethod
    def receivers_list(cls, organisation=None):
        receip_list = []
        receip_list = cls.superuser_mails(receip_list)
        receip_list = cls.admin_mails(receip_list)
        if organisation:
            receip_list = cls.referents_mails(receip_list, organisation)

        # Pour retourner une liste de valeurs uniques
        return list(set(receip_list))

    @classmethod
    def send_credentials_user_creation_admin(cls, cleaned_data):
        msg_on_create = """Bonjour, {last_name}, {first_name},
Un compte vous a été créé par les services d'administration sur la plateforme Datasud .
+ Identifiant de connexion: {username}

Veuillez initializer votre mot de passe en suivant le lien suivant.
+ Url de connexion: {url}

Ce message est envoyé automatiquement. Veuillez ne pas répondre. """
        sub_on_create = "Un nouveau compte vous a été crée sur la plateforme Datasud"

        mail_template, created = cls.objects.get_or_create(
            template_name='credentials_user_creation_admin',
            defaults={
                'message': msg_on_create,
                'subject': sub_on_create})

        fmt = PartialFormatter()
        data = {'first_name': cleaned_data.get('first_name'),
                'last_name': cleaned_data.get('last_name').upper(),
                'username': cleaned_data.get('username'),
                'url': cleaned_data.get('url')}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject, message=message,
                  from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[cleaned_data.get('email')])

    @classmethod
    def validation_user_mail(cls, request, action):

        user = action.profile.user
        mail_template = Mail.objects.get(template_name='validation_user_mail')
        from_email = mail_template.from_email
        subject = mail_template.subject

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirmation_mail',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=subject, message=message,
                  from_email=from_email, recipient_list=[user.email])

    @classmethod
    def confirmation_user_mail(cls, user):
        """E-mail de confirmation.

        E-mail confirmant la creation d'une nouvelle organisation
        suite à une inscription.
        """
        mail_template = \
            Mail.objects.get(template_name='confirmation_user_mail')

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])

    @classmethod
    def confirm_new_organisation(cls, request, action):  # A revoir complétement !
        """E-mail de validation.

        E-mail permettant de valider la création d'une nouvelle organisation
        suite à une inscription.
        """
        user = action.profile.user
        organisation = action.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name='confirm_new_organisation')

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_new_orga',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def confirm_rattachement(cls, request, action):

        user = action.profile.user
        organisation = action.profile.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = Mail.objects.get(template_name='confirm_rattachement')

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_rattachement',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def confirm_updating_rattachement(cls, request, action):

        user = action.profile.user
        organisation = action.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name="confirm_updating_rattachement")

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_rattachement',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def confirm_referent(cls, request, action):
        user = action.profile.user
        organisation = action.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name="confirm_referent")

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_referent',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list())

    @classmethod
    def confirm_contribution(cls, request, action):

        user = action.profile.user
        organisation = action.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name="confirm_contribution")

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_contribution',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def affiliate_confirmation_to_user(cls, profile):

        mail_template = \
            Mail.objects.get(template_name="affiliate_confirmation_to_user")

        fmt = PartialFormatter()
        data = {'organisation_name': profile.organisation.name}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[profile.user.email])

    @classmethod
    def confirm_contrib_to_user(cls, action):

        organisation = action.organisation
        user = action.profile.user

        mail_template = \
            Mail.objects.get(template_name="confirm_contrib_to_user")

        fmt = PartialFormatter()
        data = {'organisation_name': organisation.name}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])

    @classmethod
    def conf_deleting_dataset_res_by_user(cls, user, dataset=None, resource=None):

        fmt = PartialFormatter()
        if dataset:
            mail_template = \
                Mail.objects.get(template_name="conf_deleting_dataset_by_user")

            data = {'dataset_name': dataset.name}

        elif resource:
            mail_template = \
                Mail.objects.get(template_name="conf_deleting_res_by_user")

            data = {'dataset_name': dataset.name,
                    'resource_name': resource.name}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])

    @classmethod
    def conf_deleting_profile_to_user(cls, user_copy):

        mail_template = \
            Mail.objects.get(template_name="conf_deleting_profile_to_user")

        fmt = PartialFormatter()
        data = {'first_name': user_copy["first_name"],
                'last_name': user_copy["last_name"],
                'username': user_copy["username"]}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user_copy["email"]])

    @classmethod
    def send_reset_password_link_to_user(cls, request, action):

        mail_template = \
            Mail.objects.get(template_name="send_reset_password_link_to_user")
        user = action.profile.user

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:password_manager',
                            kwargs={'process': 'reset', 'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])


class Category(models.Model):

    ISO_TOPIC_CHOICES = AUTHORIZED_ISO_TOPIC

    # A chaque déploiement
    # python manage.py sync_ckan_categories

    name = models.CharField(
        verbose_name='Nom', max_length=100)

    description = models.CharField(
        verbose_name='Description', max_length=1024)

    ckan_slug = models.SlugField(
        verbose_name='Ckan slug', max_length=100,
        unique=True, db_index=True, blank=True)

    ckan_id = models.UUIDField(
        verbose_name='Ckan UUID', default=uuid.uuid4, editable=False)

    iso_topic = models.CharField(
        verbose_name='Thème ISO', max_length=100,
        choices=ISO_TOPIC_CHOICES, blank=True, null=True)

    picto = models.ImageField(
        verbose_name='Pictogramme', upload_to='logos/',
        blank=True, null=True)

    class Meta(object):
        verbose_name = 'Catégorie'

    def __str__(self):
        return self.name

    def sync_ckan(self):
        if self.pk:
            ckan.update_group(self)
        else:
            ckan.add_group(self)

    def clean(self):
        self.ckan_slug = slugify(self.name)
        try:
            self.sync_ckan()
        except Exception as e:
            raise ValidationError(e.__str__())


class License(models.Model):

    # MODELE LIE AUX LICENCES CKAN. MODIFIER EGALEMENT DANS LA CONF CKAN
    # QUAND DES ELEMENTS SONT AJOUTES, il faut mettre à jour
    # le fichier /etc/ckan/default/licenses.json

    domain_content = models.BooleanField(default=False)

    domain_data = models.BooleanField(default=False)

    domain_software = models.BooleanField(default=False)

    status = models.CharField(
        verbose_name='Statut', max_length=30, default='active')

    maintainer = models.CharField(
        verbose_name='Maintainer', max_length=50, blank=True)

    od_conformance = models.CharField(
        verbose_name='od_conformance', max_length=30,
        blank=True, default='approved')

    osd_conformance = models.CharField(
        verbose_name='osd_conformance', max_length=30,
        blank=True, default='not reviewed')

    title = models.CharField(verbose_name='Nom', max_length=100)

    url = models.URLField(verbose_name='url', blank=True)

    class Meta(object):
        verbose_name = 'Licence'

    def __str__(self):
        return self.title

    @property
    def ckan_id(self):
        return 'license-{0}'.format(self.pk)


class Support(models.Model):

    name = models.CharField(
        verbose_name='Nom', max_length=100)

    description = models.CharField(
        verbose_name='Description', max_length=1024)

    ckan_slug = models.SlugField(
        verbose_name='Label court', max_length=100,
        unique=True, db_index=True, blank=True)

    email = models.EmailField(
        verbose_name='E-mail', blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = 'Support technique'
        verbose_name_plural = 'Supports techniques'


class DataType(models.Model):

    name = models.CharField(verbose_name='Nom', max_length=100)

    description = models.CharField(verbose_name='Description', max_length=1024)

    ckan_slug = models.SlugField(
        verbose_name='Ckan_ID', max_length=100,
        unique=True, db_index=True, blank=True)

    class Meta(object):
        verbose_name = 'Type de donnée'
        verbose_name_plural = 'Types de données'

    def __str__(self):
        return self.name


class Granularity(models.Model):

    slug = models.SlugField(
        verbose_name='Slug', max_length=100,
        unique=True, db_index=True, blank=True,
        primary_key=True)

    name = models.TextField(verbose_name='Nom')

    class Meta(object):
        verbose_name = 'Granularité de la couverture territoriale'
        verbose_name_plural = 'Granularités des couvertures territoriales'

    def __str__(self):
        return self.name


class Dataset(models.Model):

    _current_editor = None

    GEOCOVER_CHOICES = (
        ('regionale', 'Régionale'),
        ('international', 'Internationale'),
        ('european', 'Européenne'),
        ('national', 'Nationale'),
        ('departementale', 'Départementale'),
        ('intercommunal', 'Inter-Communale'),
        ('communal', 'Communale'))

    FREQUENCY_CHOICES = (
        ('asneeded', 'Lorsque nécessaire'),
        ('never', 'Non planifiée'),
        ('intermittently', 'Irrégulière'),
        ('continuously', 'Continue'),
        ('realtime', 'Temps réel'),
        ('daily', 'Journalière'),
        ('weekly', 'Hebdomadaire'),
        ('bimonthly', 'Bi-mensuelle'),
        ('monthly', 'Mensuelle'),
        ('quarterly', 'Trimestrielle'),
        ('biannual', 'Bi-annuelle'),
        ('annual', 'Annuelle'),
        ('unknow', 'Inconnue'))

    # Mandatory
    name = models.TextField(verbose_name='Titre', unique=True)  # unique=False est préférable...

    ckan_slug = models.SlugField(
        error_messages={
            'invalid': "Le label court ne peut contenir ni majuscule, ni caractères spéciaux à l'exception le tiret."},
        verbose_name='Label court', max_length=100,
        unique=True, db_index=True, blank=True, null=True)

    ckan_id = models.UUIDField(
        verbose_name='Identifiant CKAN', unique=True,
        db_index=True, editable=False, blank=True, null=True)

    description = models.TextField(
        verbose_name='Description', blank=True, null=True)

    thumbnail = models.ImageField(
        verbose_name='Illustration',
        upload_to='thumbnails/', blank=True, null=True)

    keywords = TaggableManager('Liste de mots-clés', blank=True)

    categories = models.ManyToManyField(
        to='Category', verbose_name="Catégories d'appartenance", blank=True)

    date_creation = models.DateField(
        verbose_name='Date de création', blank=True, null=True)

    date_modification = models.DateField(
        verbose_name='Date de dernière modification', blank=True, null=True)

    date_publication = models.DateField(
        verbose_name='Date de publication', blank=True, null=True)

    update_freq = models.CharField(
        verbose_name='Fréquence de mise à jour', default='never',
        max_length=30, choices=FREQUENCY_CHOICES)

    geocover = models.CharField(
        verbose_name='Couverture géographique', blank=True, null=True,
        default='regionale', max_length=30, choices=GEOCOVER_CHOICES)

    # Mandatory
    organisation = models.ForeignKey(
        to='Organisation',
        verbose_name="Organisation à laquelle est rattaché ce jeu de données",
        blank=True, null=True, on_delete=models.CASCADE)

    # Mandatory
    license = models.ForeignKey(License, verbose_name='Licence')

    support = models.ForeignKey(
        to='Support', verbose_name='Support technique', null=True, blank=True)

    data_type = models.ManyToManyField(
        to='DataType', verbose_name='Type de données', blank=True)

    published = models.BooleanField(
        verbose_name='Publier le jeu de données', default=False)

    is_inspire = models.BooleanField(
        verbose_name='Le jeu de données est soumis à la règlementation INSPIRE',
        default=False)

    geonet_id = models.UUIDField(
        verbose_name='UUID de la métadonnées', unique=True,
        db_index=True, blank=True, null=True)

    editor = models.ForeignKey(
        User, verbose_name='Producteur (propriétaire)')

    owner_name = models.CharField(
        verbose_name='Nom du producteur',
        max_length=100, blank=True, null=True)

    owner_email = models.EmailField(
        verbose_name='E-mail du producteur', blank=True, null=True)

    broadcaster_name = models.CharField(
        verbose_name='Nom du diffuseur',
        max_length=100, blank=True, null=True)

    broadcaster_email = models.EmailField(
        verbose_name='E-mail du diffuseur', blank=True, null=True)

    # Mandatory
    granularity = models.ForeignKey(
        to='Granularity',
        blank=True, null=True,  # blank=False, null=False, default='commune-francaise',
        verbose_name='Granularité de la couverture territoriale',
        on_delete=models.PROTECT)

    bbox = models.PolygonField(
        verbose_name='Rectangle englobant', blank=True, null=True, srid=4171)

    class Meta(object):
        verbose_name = 'Jeu de données'
        verbose_name_plural = 'Jeux de données'

    def __str__(self):
        return self.name

    def is_contributor(self, profile):
        return LiaisonsContributeurs.objects.filter(
            profile=profile, organisation=self.organisation,
            validated_on__isnull=False).exists()

    def is_referent(self, profile):
        return LiaisonsReferents.objects.filter(
            profile=profile, organisation=self.organisation,
            validated_on__isnull=False).exists()

    def clean(self):
        slug = self.ckan_slug or slugify(self.name)
        ckan_dataset = ckan_me(ckan.apikey).get_package(slug)
        if ckan_dataset \
                and uuid.UUID(ckan_dataset.get('id')) != self.ckan_id \
                and ckan_dataset.get('name') == slug:
            raise ValidationError("L'URL du jeu de données est réservé.")

    def save(self, *args, sync_ckan=True, **kwargs):
        previous = self.pk and Dataset.objects.get(pk=self.pk)

        self._current_editor = 'editor' in kwargs \
            and kwargs.pop('editor') or None

        if not self.date_creation:
            self.date_creation = TODAY
        if not self.date_modification:
            self.date_modification = TODAY
        if not self.date_publication:
            self.date_publication = TODAY

        if not self.owner_name:
            self.owner_name = self.editor.get_full_name()
        if not self.owner_email:
            self.owner_email = self.editor.email

        broadcaster_name = self.broadcaster_name or \
            self.support and self.support.name or 'Plateforme DataSud'
        broadcaster_email = self.broadcaster_email or \
            self.support and self.support.email or 'contact@datasud.fr'

        super().save(*args, **kwargs)

        if previous and previous.organisation:
            ckan.deactivate_ckan_organization_if_empty(
                str(previous.organisation.ckan_id))

        if not sync_ckan:  # STOP
            return

        for resource in Resource.objects.filter(dataset=self):
            ows = resource.ogc_services

        ckan_params = {
            'author': self.owner_name,
            'author_email': self.owner_email,
            'datatype': [item.ckan_slug for item in self.data_type.all()],
            'dataset_creation_date':
                str(self.date_creation) if self.date_creation else '',
            'dataset_modification_date':
                str(self.date_modification) if self.date_modification else '',
            'dataset_publication_date':
                str(self.date_publication) if self.date_publication else '',
            'groups': [],
            'geocover': self.geocover,
            'granularity': self.granularity.slug,
            'last_modified':
                str(self.date_modification) if self.date_modification else '',
            'license_id': (
                self.license.ckan_id
                in [license['id'] for license in ckan.get_licenses()]
                ) and self.license.ckan_id or '',
            'maintainer': broadcaster_name,
            'maintainer_email': broadcaster_email,
            'name': self.ckan_slug,
            'notes': self.description,
            'owner_org': str(self.organisation.ckan_id),
            'ows': ows,
            'private': not self.published,
            'spatial': self.bbox and self.bbox.geojson or None,
            'state': 'active',
            'support': self.support and self.support.ckan_slug,
            'tags': [
                {'name': keyword.name} for keyword in self.keywords.all()],
            'title': self.name,
            'update_frequency': self.update_freq,
            'url': ''}  # Laisser vide

        try:
            ckan_params['thumbnail'] = urljoin(
                settings.DOMAIN_NAME, self.thumbnail.url)
        except ValueError:
            pass

        if self.geonet_id:
            ckan_params['inspire_url'] = \
                '{0}srv/fre/catalog.search#/metadata/{1}'.format(
                    GEONETWORK_URL, self.geonet_id or '')

        user = self._current_editor or self.editor

        for category in self.categories.all():
            ckan.add_user_to_group(user.username, str(category.ckan_id))
            ckan_params['groups'].append({'name': category.ckan_slug})

        # Si l'utilisateur courant n'est pas l'éditeur d'un jeu
        # de données existant mais administrateur ou un référent technique,
        # alors l'admin Ckan édite le jeu de données..
        if user == self.editor:
            ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        else:
            ckan_user = ckan_me(ckan.apikey)

        # Synchronisation de l'organisation
        organisation_ckan_id = str(self.organisation.ckan_id)
        ckan_organization = ckan.get_organization(organisation_ckan_id)
        if not ckan_organization:
            ckan.add_organization(self.organisation)
        elif ckan_organization.get('state') == 'deleted':
            ckan.activate_organization(organisation_ckan_id)

        for profile \
                in LiaisonsContributeurs.get_contributors(self.organisation):
            ckan.add_user_to_organization(
                profile.user.username, organisation_ckan_id)

        ckan_dataset = \
            ckan_user.publish_dataset(
                id=self.ckan_id and str(self.ckan_id), **ckan_params)

        ckan_user.close()

        # Si l'organisation change
        ws_name = self.organisation.ckan_slug
        if previous and previous.organisation != self.organisation:
            resources = Resource.objects.filter(dataset=previous)
            prev_ws_name = previous.organisation.ckan_slug
            ds_name = 'public'
            for resource in resources:
                if resource.datagis_id:
                    for datagis_id in resource.datagis_id:
                        ft_name = str(datagis_id)
                        try:
                            MRAHandler.del_layer(ft_name)
                            MRAHandler.del_featuretype(prev_ws_name, ds_name, ft_name)
                        except MRANotFoundError:
                            pass
                        try:
                            MRAHandler.publish_layers_resource(resource)
                        except MRAConflictError:
                            pass
                        ckan_user.update_resource(
                            ft_name,
                            url='{0}#{1}'.format(
                                OWS_URL_PATTERN.format(organisation=ws_name), ft_name))

        set = [r.datagis_id for r in
               Resource.objects.filter(dataset=self, datagis_id__isnull=False)]
        if set:
            data = {
                'name': self.ckan_slug,
                'title': self.name,
                'layers': [item for sub in set for item in sub]}
            MRAHandler.create_or_update_layergroup(ws_name, data)
        else:
            MRAHandler.del_layergroup(ws_name, self.ckan_slug)

        self.ckan_id = uuid.UUID(ckan_dataset['id'])
        super().save()  # self.save(sync_ckan=False)

    @classmethod
    def get_subordinated_datasets(cls, profile):
        return cls.objects.filter(
            organisation__in=LiaisonsReferents.get_subordinated_organizations(
                profile=profile))


class Task(models.Model):

    STATE_CHOICES = (
        ('succesful', "Tâche terminée avec succés"),
        ('failed', "Echec de la tâche"),
        ('running', "Tâche en cours de traitement"))

    action = models.TextField("Action", blank=True, null=True)

    extras = JSONField("Extras", blank=True, null=True)

    state = models.CharField(
        verbose_name='Etat de traitement', default='running',
        max_length=20, choices=STATE_CHOICES)

    starting = models.DateTimeField(
        verbose_name="Timestamp de début de traitement",
        auto_now_add=True)

    end = models.DateTimeField(
        verbose_name="Timestamp de fin de traitement",
        blank=True, null=True)

    class Meta(object):
        verbose_name = 'Tâche de synchronisation'


# Triggers


@receiver(pre_save, sender=Dataset)
def pre_save_dataset(sender, instance, **kwargs):
    if not instance.ckan_slug:
        instance.ckan_slug = slugify(instance.name)


@receiver(pre_delete, sender=Dataset)
def pre_delete_dataset(sender, instance, **kwargs):
    Resource.objects.filter(dataset=instance).delete()
    ckan.purge_dataset(instance.ckan_slug)


@receiver(post_delete, sender=Dataset)
def post_delete_dataset(sender, instance, **kwargs):
    ckan.deactivate_ckan_organization_if_empty(str(instance.organisation.ckan_id))


# @receiver(post_save, sender=Resource)
# def post_save_resource(sender, instance, **kwargs):
#     resources = Resource.objects.filter(dataset=instance.dataset)
#     instance.dataset.bbox = get_extent(
#         [item for sub in [r.datagis_id for r in resources] for item in sub])
#
#     instance.dataset.date_modification = timezone.now().date()
#     instance.dataset.save()


@receiver(post_delete, sender=Resource)
def post_delete_resource(sender, instance, **kwargs):
    ckan_user = ckan_me(ckan.get_user(instance.dataset.editor.username)['apikey'])
    ws_name = instance.dataset.organisation.ckan_slug
    ds_name = 'public'
    if instance.datagis_id:
        for datagis_id in instance.datagis_id:
            ft_name = str(datagis_id)
            # Supprimer les objects MRA  (TODO en cascade dans MRA)
            try:
                MRAHandler.del_layer(ft_name)
                MRAHandler.del_featuretype(ws_name, ds_name, ft_name)
            except MRANotFoundError:
                pass
            # Supprimer la ressource CKAN
            ckan_user.delete_resource(ft_name)
            # Supprimer les anciennes tables GIS
            drop_table(ft_name)


@receiver(pre_delete, sender=User)
def pre_delete_user(sender, instance, **kwargs):
    ckan.del_user(instance.username)


@receiver(pre_save, sender=LiaisonsContributeurs)
def pre_save_contribution(sender, instance, **kwargs):
    if not instance.validated_on:
        return
    user = instance.profile.user
    organisation = instance.organisation
    if ckan.get_organization(str(organisation.ckan_id)):
        ckan.add_user_to_organization(user.username, str(organisation.ckan_id))


@receiver(pre_delete, sender=LiaisonsContributeurs)
def pre_delete_contribution(sender, instance, **kwargs):
    user = instance.profile.user
    organisation = instance.organisation
    if ckan.get_organization(str(organisation.ckan_id)):
        ckan.del_user_from_organization(user.username, str(organisation.ckan_id))


@receiver(pre_save, sender=Organisation)
def pre_save_organisation(sender, instance, **kwargs):
    instance.ckan_slug = slugify(instance.name)


@receiver(post_save, sender=Organisation)
def post_save_organisation(sender, instance, **kwargs):
    # Mettre à jour en cascade les profiles (utilisateurs)
    for profile in Profile.objects.filter(organisation=instance):
        profile.crige_membership = instance.is_crige_partner
        profile.save()

    # Synchroniser avec l'organisation CKAN
    if ckan.is_organization_exists(str(instance.ckan_id)):
        ckan.update_organization(instance)


@receiver(post_delete, sender=Organisation)
def post_delete_organisation(sender, instance, **kwargs):
    if ckan.is_organization_exists(str(instance.ckan_id)):
        ckan.purge_organization(str(instance.ckan_id))


@receiver(pre_delete, sender=Category)
def pre_delete_category(sender, instance, **kwargs):
    if ckan.is_group_exists(str(instance.ckan_id)):
        ckan.del_group(str(instance.ckan_id))


@receiver(post_save, sender=Profile)
def post_save_profile(sender, instance, **kwargs):
    if instance.crige_membership:
        ckan.add_user_to_partner_group(instance.user.username, 'crige-partner')
    else:
        ckan.del_user_from_partner_group(instance.user.username)
