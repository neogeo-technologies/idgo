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
from django.apps import apps
from django.conf import settings
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import IntegrityError
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_delete
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.http import Http404
from django.utils import timezone
from functools import reduce
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.datagis import bounds_to_wkt
from idgo_admin.datagis import DataDecodingError
from idgo_admin.datagis import drop_table
from idgo_admin.datagis import gdalinfo
from idgo_admin.datagis import get_gdalogr_object
from idgo_admin.datagis import NotDataGISError
from idgo_admin.datagis import NotFoundSrsError
from idgo_admin.datagis import NotOGRError
from idgo_admin.datagis import NotSupportedSrsError
from idgo_admin.datagis import ogr2postgis
from idgo_admin.exceptions import ExceedsMaximumLayerNumberFixedError
from idgo_admin.exceptions import SizeLimitExceededError
from idgo_admin.utils import download
from idgo_admin.utils import remove_file
from idgo_admin.utils import slugify
from idgo_admin.utils import three_suspension_points
import json
import logging
import os
from pathlib import Path
import re
import shutil
from urllib.parse import parse_qs
from urllib.parse import urljoin
from urllib.parse import urlparse
import uuid


try:
    DOWNLOAD_SIZE_LIMIT = settings.DOWNLOAD_SIZE_LIMIT
except AttributeError:
    DOWNLOAD_SIZE_LIMIT = 104857600

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
        AUTHORIZED_PROTOCOL = (
            (protocol['id'], protocol['value']) for protocol
            in MDEDIT_LOCALES['codelists']['MD_LinkageProtocolCode'])
except Exception:
    AUTHORIZED_PROTOCOL = None

CKAN_STORAGE_PATH = settings.CKAN_STORAGE_PATH
OWS_URL_PATTERN = settings.OWS_URL_PATTERN
CKAN_URL = settings.CKAN_URL


def get_all_users_for_organizations(list_id):
    Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


def upload_resource(instance, filename):
    return slugify(filename, exclude_dot=False)


class ResourceFormats(models.Model):

    CKAN_CHOICES = (
        (None, 'N/A'),
        ('text_view', 'text_view'),
        ('geo_view', 'geo_view'),
        ('recline_view', 'recline_view'),
        ('pdf_view', 'pdf_view'))

    ckan_view = models.CharField(
        verbose_name='Vue', max_length=100,
        choices=CKAN_CHOICES, blank=True, null=True)

    ckan_format = models.CharField(
        verbose_name='type de format CKAN',
        max_length=10, blank=True, null=True)

    description = models.TextField(
        verbose_name='Description', blank=True, null=True)

    extension = models.CharField('Extension du fichier', max_length=10)

    is_gis_format = models.BooleanField(
        verbose_name='Est un format de données SIG',
        blank=False, null=False, default=False)

    PROTOCOL_CHOICES = AUTHORIZED_PROTOCOL

    protocol = models.CharField(
        'Protocole', max_length=100, blank=True, null=True,
        choices=PROTOCOL_CHOICES)

    class Meta(object):
        verbose_name = 'Format de ressource'
        verbose_name_plural = 'Formats de ressource'

    def __str__(self):
        return self.description


def only_reference_filename(instance, filename):
    return filename


class ResourceManager(models.Manager):

    def create(self, **kwargs):
        save_opts = kwargs.pop('save_opts', {})
        obj = self.model(**kwargs)
        self._for_write = True
        obj.save(force_insert=True, using=self.db, **save_opts)
        return obj


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
        ('3', 'Utilisateurs de cette organisation uniquement'),
        ('4', 'Organisations spécifiées'))

    TYPE_CHOICES = (
        ('raw', 'Données brutes'),
        ('annexe', 'Documentation associée'),
        ('service', 'Service'))

    name = models.CharField(
        verbose_name='Nom', max_length=150)

    ckan_id = models.UUIDField(
        verbose_name='Ckan UUID', default=uuid.uuid4, editable=False)

    description = models.TextField(
        verbose_name='Description', blank=True, null=True)

    ftp_file = models.FileField(
        verbose_name='Fichier déposé sur FTP',
        blank=True, null=True,
        upload_to=only_reference_filename)

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
        verbose_name='Rectangle englobant', blank=True, null=True, srid=4171)

    geo_restriction = models.BooleanField(
        verbose_name='Restriction géographique', default=False)

    extractable = models.BooleanField(
        verbose_name='Extractible', default=True)

    ogc_services = models.BooleanField(
        verbose_name='Services OGC', default=True)

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

    objects = models.Manager()
    custom = ResourceManager()  # Renommer car pas très parlant...

    _encoding = 'utf-8'

    class Meta(object):
        verbose_name = 'Ressource'

    def __str__(self):
        return self.name

    def __slug__(self):
        return slugify(self.name)

    @property
    def encoding(self):
        return self._encoding

    @encoding.setter
    def encoding(self, value):
        if value:
            self._encoding = value

    @property
    def filename(self):
        if self.up_file:
            return self.up_file.name
        return '{}.{}'.format(slugify(self.name), self.format.lower())

    @property
    def ckan_url(self):
        return urljoin(settings.CKAN_URL, 'dataset/{}/resource/{}/'.format(
            self.dataset.ckan_slug, self.ckan_id))

    @property
    def datagis_id(self):  # TODO: supprimer et utiliser `get_layers()` exclusivement
        Layer = apps.get_model(app_label='idgo_admin', model_name='Layer')
        qs = Layer.objects.filter(resource=self)
        return [l.name for l in qs]

    @property
    def name_overflow(self):
        return three_suspension_points(self.name)

    def get_layers(self, **kwargs):
        Layer = apps.get_model(app_label='idgo_admin', model_name='Layer')
        return Layer.objects.filter(resource=self, **kwargs)

    def update_enable_layers_status(self):
        for layer in self.get_layers():
            layer.handle_enable_ows_status()

    @classmethod
    def get_resources_by_mapserver_url(cls, url):

        parsed_url = urlparse(url.lower())
        qs = parse_qs(parsed_url.query)

        ows = qs.get('service')
        if not ows:
            raise Http404()

        if ows[-1] == 'wms':
            layers = qs.get('layers')[-1].replace(' ', '').split(',')
        elif ows[-1] == 'wfs':
            layers = qs.get('typenames')[-1].replace(' ', '').split(',')
        else:
            raise Http404()
        return Resource.objects.filter(layer__name__in=layers).distinct()

    @property
    def anonymous_access(self):
        return self.restricted_level == '0'

    def is_profile_authorized(self, user):
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        if not user.pk:
            raise IntegrityError('User does not exists')
        if self.restricted_level == '2':
            return self.profiles_allowed.exists() and user in [
                p.user for p in self.profiles_allowed.all()]
        elif self.restricted_level in ('3', '4'):
            return self.organisations_allowed.exists() and user in [
                p.user for p in Profile.objects.filter(
                    organisation__in=self.organisations_allowed,
                    organisation__is_active=True)]
        return True

    @property
    def is_datagis(self):
        return self.get_layers() and True or False

    def synchronize_ckan(
            self, url=None, filename=None, content_type=None, file_extras=None):

        # Si l'utilisateur courant n'est pas l'éditeur d'un jeu
        # de données existant mais administrateur ou un référent technique,
        # alors l'admin Ckan édite le jeu de données.
        if self.editor == self.dataset.editor:
            ckan_user = ckan_me(ckan.get_user(self.editor.username)['apikey'])
        else:
            ckan_user = ckan_me(ckan.apikey)

        ckan_params = {
            'crs': self.crs and self.crs.description or '',
            'name': self.name,
            'description': self.description,
            'data_type': self.data_type,
            'extracting_service': 'False',  # I <3 CKAN
            'format': self.format_type.ckan_format,
            'view_type': self.format_type.ckan_view,
            'id': str(self.ckan_id),
            'lang': self.lang,
            'restricted_by_jurisdiction': str(self.geo_restriction),
            'url': url and url or ''}

        # TODO: Factoriser

        # (0) Aucune restriction
        if self.restricted_level == '0':
            restricted = json.dumps({'level': 'public'})
        # (1) Uniquement pour un utilisateur connecté
        elif self.restricted_level == '1':
            restricted = json.dumps({'level': 'registered'})
        # (2) Seulement les utilisateurs indiquées
        elif self.restricted_level == '2':
            restricted = json.dumps({
                'allowed_users': ','.join(
                    self.profiles_allowed.exists() and [
                        p.user.username for p
                        in self.profiles_allowed.all()] or []),
                'level': 'only_allowed_users'})
        # (3) Les utilisateurs de cette organisation
        elif self.restricted_level == '3':
            restricted = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organizations(
                        self.organisations_allowed.all())),
                'level': 'only_allowed_users'})
        # (3) Les utilisateurs des organisations indiquées
        elif self.restricted_level == '4':
            restricted = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organizations(
                        self.organisations_allowed.all())),
                'level': 'only_allowed_users'})

        ckan_params['restricted'] = restricted

        if self.referenced_url:
            ckan_params['url'] = self.referenced_url
            ckan_params['resource_type'] = '{0}.{1}'.format(
                self.name, self.format_type.ckan_view)

        if self.dl_url:
            downloaded_file = File(open(filename, 'rb'))
            ckan_params['upload'] = downloaded_file
            ckan_params['size'] = downloaded_file.size
            ckan_params['mimetype'] = content_type
            ckan_params['resource_type'] = Path(filename).name

        if self.up_file and file_extras:
            ckan_params['upload'] = self.up_file.file
            ckan_params['size'] = file_extras.get('size')
            ckan_params['mimetype'] = file_extras.get('mimetype')
            ckan_params['resource_type'] = file_extras.get('resource_type')

        if self.ftp_file:
            if not url:
                ckan_params['upload'] = self.ftp_file.file
            ckan_params['size'] = self.ftp_file.size
            ckan_params['mimetype'] = None  # TODO
            ckan_params['resource_type'] = Path(self.ftp_file.name).name

        ckan_package = ckan_user.get_package(str(self.dataset.ckan_id))

        ckan_user.publish_resource(ckan_package, **ckan_params)

        ckan_user.close()

    def save(self, *args, **kwargs):

        # Modèles
        SupportedCrs = apps.get_model(app_label='idgo_admin', model_name='SupportedCrs')
        Layer = apps.get_model(app_label='idgo_admin', model_name='Layer')
        # Quelques options :
        sync_ckan = kwargs.pop('sync_ckan', False)
        file_extras = kwargs.pop('file_extras', None)  # Des informations sur la ressource téléversée
        self.editor = kwargs.pop('editor', None)  # L'éditeur de l'objet `request` (qui peut être celui du jeu de données ou un référent)

        # On sauvegarde l'objet avant de le mettre à jour (s'il existe)
        previous, created = self.pk \
            and (Resource.objects.get(pk=self.pk), False) or (None, True)

        # Quelques valeur par défaut à la création de l'instance
        if created \
                or not self.editor.profile.crige_membership:
                # Ou si l'éditeur n'est pas partenaire du CRIGE

            # Mais seulement s'il s'agit de données SIG, sauf
            # qu'on ne le sait pas encore...
            self.geo_restriction = False
            self.ogc_services = True
            self.extractable = True

        # La restriction au territoire de compétence désactive toujours les services OGC
        if self.geo_restriction:
            self.ogc_services = False

        # Quelques contrôles sur les fichiers de données téléversée ou à télécharger
        filename = False
        content_type = None
        file_must_be_deleted = False  # permet d'indiquer si les fichiers doivent être supprimés à la fin de la chaine de traitement
        publish_raw_resource = True  # permet d'indiquer si les ressources brutes sont publiées dans CKAN

        if self.ftp_file:
            filename = self.ftp_file.file.name
            # Si la taille de fichier dépasse la limite autorisée,
            # on traite les données en fonction du type détecté
            if self.ftp_file.size > DOWNLOAD_SIZE_LIMIT:
                extension = self.format_type.extension.lower()
                if self.format_type.is_gis_format:
                    try:
                        gdalogr_obj = get_gdalogr_object(filename, extension)
                    except NotDataGISError:
                        # On essaye de traiter le jeux de données normalement, même si ça peut être long.
                        pass
                    else:
                        if gdalogr_obj.__class__.__name__ == 'GdalOpener':
                            s0 = str(self.ckan_id)
                            s1, s2, s3 = s0[:3], s0[3:6], s0[6:]
                            dir = os.path.join(CKAN_STORAGE_PATH, s1, s2)
                            os.makedirs(dir, mode=0o777, exist_ok=True)
                            shutil.copyfile(filename, os.path.join(dir, s3))

                        # if gdalogr_obj.__class__.__name__ == 'OgrOpener':
                        # On ne publie que le service OGC dans CKAN
                        publish_raw_resource = False

        elif (self.up_file and file_extras):
            # GDAL/OGR ne semble pas prendre de fichier en mémoire..
            # ..à vérifier mais si c'est possible comment indiquer le vsi en préfixe du filename ?
            super().save(*args, **kwargs)
            kwargs['force_insert'] = False

            filename = self.up_file.file.name
            file_must_be_deleted = True

        elif self.dl_url:
            try:
                directory, filename, content_type = download(
                    self.dl_url, settings.MEDIA_ROOT, max_size=DOWNLOAD_SIZE_LIMIT)
            except SizeLimitExceededError as e:
                l = len(str(e.max_size))
                if l > 6:
                    m = '{0} mo'.format(Decimal(int(e.max_size) / 1024 / 1024))
                elif l > 3:
                    m = '{0} ko'.format(Decimal(int(e.max_size) / 1024))
                else:
                    m = '{0} octets'.format(int(e.max_size))
                raise ValidationError((
                    'La taille du fichier dépasse '
                    'la limite autorisée : {0}.').format(m), code='dl_url')
            except Exception as e:
                if e.__class__.__name__ == 'HTTPError':
                    if e.response.status_code == 404:
                        msg = ('La ressource distante ne semble pas exister. '
                               "Assurez-vous que l'URL soit correcte.")
                    if e.response.status_code == 403:
                        msg = ("Vous n'avez pas l'autorisation pour "
                               'accéder à la ressource.')
                    if e.response.status_code == 401:
                        msg = ('Une authentification est nécessaire '
                               'pour accéder à la ressource.')
                else:
                    msg = 'Le téléchargement du fichier a échoué.'
                raise ValidationError(msg, code='dl_url')
            file_must_be_deleted = True

        # Synchronisation avec CKAN
        # =========================

        # La synchronisation doit s'effectuer avant la publication des
        # éventuelles couches de données SIG car dans le cas des données
        # de type « raster », nous utilisons le filestore de CKAN.
        if sync_ckan and publish_raw_resource:
            self.synchronize_ckan(
                filename=filename, content_type=content_type, file_extras=file_extras)
        elif sync_ckan and not publish_raw_resource:
            self.synchronize_ckan(
                url=reduce(urljoin, [
                    settings.CKAN_URL,
                    'dataset/', str(self.dataset.ckan_id) + '/',
                    'resource/', str(self.ckan_id) + '/',
                    'download/', Path(self.ftp_file.name).name]))

        # Détection des données SIG
        # =========================

        if filename:
            # On vérifie s'il s'agit de données SIG, uniquement pour
            # les extensions de fichier autorisées..
            extension = self.format_type.extension.lower()
            if self.format_type.is_gis_format:
                # Si c'est le cas, on monte les données dans la base PostGIS dédiée
                # et on déclare la couche au service OGC:WxS de l'organisation.

                # Mais d'abord, on vérifie si la ressource contient
                # déjà des « Layers », auquel cas il faudra vérifier si
                # la table de données a changée.
                existing_layers = {}
                if not created:
                    existing_layers = dict((
                        re.sub('^(\w+)_[a-z0-9]{7}$', '\g<1>', layer.name),
                        layer.name) for layer in self.get_layers())

                try:
                    # C'est carrément moche mais c'est pour aller vite.
                    # Il faudrait factoriser tout ce bazar et créer
                    # un décorateur pour gérer le rool-back sur CKAN.

                    try:
                        gdalogr_obj = get_gdalogr_object(filename, extension)
                    except NotDataGISError:
                        tables = []
                        pass
                    else:

                        try:
                            self.format_type = ResourceFormats.objects.get(
                                extension=extension, ckan_format=gdalogr_obj.format)
                        # except ResourceFormats.MultipleObjectsReturned:
                        #     pass
                        except Exception:
                            pass

                        if gdalogr_obj.__class__.__name__ == 'OgrOpener':
                            # On convertit les données vectorielles vers Postgis.
                            try:
                                tables = ogr2postgis(
                                    gdalogr_obj, update=existing_layers,
                                    epsg=self.crs and self.crs.auth_code or None,
                                    encoding=self.encoding)

                            except NotOGRError as e:
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    "Le fichier reçu n'est pas reconnu "
                                    'comme étant un jeu de données SIG correct.')
                                raise ValidationError(msg, code='__all__')

                            except DataDecodingError as e:
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    'Impossible de décoder correctement les '
                                    "données. Merci d'indiquer l'encodage "
                                    'ci-dessous.')
                                raise ValidationError(msg, code='encoding')

                            except NotFoundSrsError as e:
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    'Votre ressource semble contenir des données SIG '
                                    'mais nous ne parvenons pas à détecter le système '
                                    'de coordonnées. Merci de sélectionner le code du '
                                    'CRS dans la liste ci-dessous.')
                                raise ValidationError(msg, code='crs')

                            except NotSupportedSrsError as e:
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    'Votre ressource semble contenir des données SIG '
                                    'mais le système de coordonnées de celles-ci '
                                    "n'est pas supporté par l'application.")
                                raise ValidationError(msg, code='__all__')

                            except ExceedsMaximumLayerNumberFixedError as e:
                                file_must_be_deleted and remove_file(filename)
                                raise ValidationError(e.__str__(), code='__all__')

                            else:
                                # Avant de créer des relations, l'objet doit exister
                                if created:
                                    # S'il s'agit d'une création, alors on sauve l'objet.
                                    super().save(*args, **kwargs)
                                    kwargs['force_insert'] = False

                                # Ensuite, pour tous les jeux de données SIG trouvés,
                                # on crée le service ows à travers la création de `Layer`
                                try:
                                    for table in tables:
                                        try:
                                            Layer.objects.get(
                                                name=table['id'], resource=self)
                                        except Layer.DoesNotExist:
                                            Layer.vector.create(
                                                name=table['id'],
                                                resource=self,
                                                bbox=table['bbox'],
                                                save_opts={'editor': self.editor})
                                except Exception as e:
                                    file_must_be_deleted and remove_file(filename)
                                    for table in tables:
                                        drop_table(table['id'])
                                    raise e

                        if gdalogr_obj.__class__.__name__ == 'GdalOpener':
                            coverage = gdalogr_obj.get_coverage()
                            try:
                                tables = [gdalinfo(coverage, update=existing_layers)]
                            except NotFoundSrsError as e:
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    'Votre ressource semble contenir des données SIG '
                                    'mais nous ne parvenons pas à détecter le système '
                                    'de coordonnées. Merci de sélectionner le code du '
                                    'CRS dans la liste ci-dessous.')
                                raise ValidationError(msg, code='crs')
                            except NotSupportedSrsError as e:
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    'Votre ressource semble contenir des données SIG '
                                    'mais le système de coordonnées de celles-ci '
                                    "n'est pas supporté par l'application.")
                                raise ValidationError(msg, code='__all__')

                            else:
                                if created:
                                    # S'il s'agit d'une création, alors on sauve l'objet.
                                    super().save(*args, **kwargs)
                                    kwargs['force_insert'] = False

                            try:
                                for table in tables:
                                    try:
                                        Layer.objects.get(
                                            name=table['id'], resource=self)
                                    except Layer.DoesNotExist:
                                        Layer.raster.create(
                                            name=table['id'],
                                            resource=self,
                                            bbox=table['bbox'],
                                            save_opts={'editor': self.editor})
                            except Exception as e:
                                file_must_be_deleted and remove_file(filename)
                                raise e

                except Exception as e:
                    # Roll-back sur la création de la ressource CKAN
                    ckan_user = ckan_me(ckan.apikey)
                    ckan_user.delete_resource(str(self.ckan_id))

                    for layer in self.get_layers():
                        ckan_user.delete_resource(self.name)
                        if layer.attached_ckan_resources:
                            for id in layer.attached_ckan_resources:
                                ckan_user.delete_resource(str(id))

                    ckan_user.close()
                    # Puis on « raise » l'erreur
                    raise e
                # else:

                # On met à jour les champs de la ressource
                crs = [
                    SupportedCrs.objects.get(
                        auth_name='EPSG', auth_code=table['epsg'])
                    for table in tables]
                # On prend la première valeur (c'est moche)
                self.crs = crs and crs[0] or None

                # Si les données changent..
                if existing_layers and \
                        previous.get_layers() != self.get_layers():
                    # on supprime les anciens `layers`..
                    for layer in previous.get_layers():
                        layer.delete()

        # Si la ressource n'est pas de type SIG, on passe les trois arguments
        # qui concernent exclusivement ces dernières à « False ».
        if not self.get_layers():
            self.geo_restriction = False
            self.ogc_services = False
            self.extractable = False

        if self.get_layers():
            extent = self.get_layers().aggregate(models.Extent('bbox')).get('bbox__extent')
            if extent:
                xmin, ymin = extent[0], extent[1]
                xmax, ymax = extent[2], extent[3]

                setattr(self, 'bbox', bounds_to_wkt(xmin, ymin, xmax, ymax))

        super().save(*args, **kwargs)

        # Puis dans tous les cas..
        # on met à jour le statut des couches du service cartographique..
        if not created:
            self.update_enable_layers_status()

        # on supprime les données téléversées ou téléchargées..
        file_must_be_deleted and remove_file(filename)

        # Super crado
        if self.editor == self.dataset.editor:
            ckan_user = ckan_me(ckan.get_user(self.editor.username)['apikey'])
        else:
            ckan_user = ckan_me(ckan.apikey)

        ckan_user.update_resource(
            str(self.ckan_id), extracting_service=str(self.extractable))
        ckan_user.close()
        #

        for layer in self.get_layers():
            layer.save()


@receiver(post_save, sender=Resource)
@receiver(post_delete, sender=Resource)
def force_save_dataset(sender, instance, **kwargs):
    dataset = instance.dataset
    dataset.date_modification = timezone.now().date()
    dataset.save()


# @receiver(post_save, sender=Resource)
# def updated_ckan_ressource(sender, instance, **kwargs):
#     instance.synchronize_ckan(extracting_service=instance.extractable)
#     for layer in instance.get_layers():
#         layer.save()


# Logging
# =======


@receiver(pre_save, sender=Resource)
def logging_before_save(sender, instance, **kwargs):
    if not instance.pk:
        logging.info('Creating resource.. "{}"'.format(instance.__slug__(), instance.pk))
    else:
        logging.info('Updating resource.. "{}" (pk={}, ckan_id={})'.format(instance.__slug__(), instance.pk, instance.ckan_id))


@receiver(post_save, sender=Resource)
def logging_after_save(sender, instance, **kwargs):
    logging.info('Saved resource..... "{}" (pk={}, ckan_id={})'.format(instance.__slug__(), instance.pk, instance.ckan_id))


@receiver(pre_delete, sender=Resource)
def logging_before_delete(sender, instance, **kwargs):
    logging.info('Deleting resource.. "{}" (pk={}, ckan_id={})'.format(instance.__slug__(), instance.pk, instance.ckan_id))


@receiver(post_delete, sender=Resource)
def logging_after_delete(sender, instance, **kwargs):
    logging.info('Deleted resource... "{}" (pk={}, ckan_id={})'.format(instance.__slug__(), instance.pk, instance.ckan_id))
