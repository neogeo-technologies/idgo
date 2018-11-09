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
# from django.db import transaction
from django.http import Http404
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.datagis import drop_table
from idgo_admin.datagis import get_extent
from idgo_admin.datagis import get_gdalogr_object
from idgo_admin.datagis import ogr2postgis
from idgo_admin.datagis import VSI_PROTOCOLES
from idgo_admin.exceptions import ExceedsMaximumLayerNumberFixedError
from idgo_admin.exceptions import NotDataGISError
from idgo_admin.exceptions import NotFoundSrsError
from idgo_admin.exceptions import NotOGRError
from idgo_admin.exceptions import NotSupportedSrsError
from idgo_admin.exceptions import SizeLimitExceededError
from idgo_admin.models import get_all_users_for_organizations
from idgo_admin.utils import download
# from idgo_admin.utils import remove_dir
from idgo_admin.utils import remove_file
from idgo_admin.utils import slugify
from idgo_admin.utils import three_suspension_points
import itertools
import json
import os
from pathlib import Path
import re
from urllib.parse import parse_qs
from urllib.parse import urljoin
from urllib.parse import urlparse
import uuid


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
        AUTHORIZED_PROTOCOL = (
            (protocol['id'], protocol['value']) for protocol
            in MDEDIT_LOCALES['codelists']['MD_LinkageProtocolCode'])
except Exception:
    AUTHORIZED_PROTOCOL = None

OWS_URL_PATTERN = settings.OWS_URL_PATTERN


def upload_resource(instance, filename):
    return slugify(filename, exclude_dot=False)


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
        verbose_name='Rectangle englobant', blank=True, null=True)

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

    class Meta(object):
        verbose_name = 'Ressource'

    def __str__(self):
        return self.name

    @property
    def filename(self):
        if self.up_file:
            return self.up_file.name
        return '{}.{}'.format(slugify(self.name), self.format.lower())

    @property
    def ckan_url(self):
        return urljoin(settings.CKAN_URL, 'dataset/{}/resource/{}'.format(
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

    def save(self, *args, **kwargs):

        SupportedCrs = apps.get_model(app_label='idgo_admin', model_name='SupportedCrs')
        Layer = apps.get_model(app_label='idgo_admin', model_name='Layer')

        organisation = self.dataset.organisation

        # On sauvegarde l'objet avant de le mettre à jour (s'il existe)
        previous, created = self.pk \
            and (Resource.objects.get(pk=self.pk), False) or (None, True)

        # Quelques valeur par défaut à la création de l'instance
        if created:
            self.geo_restriction = False
            self.ogc_services = True
            self.extractable = True

        # La restriction au territoire de compétence désactive toujours les services OGC
        if self.geo_restriction:
            self.ogc_services = False

        # Quelques options :
        sync_ckan = kwargs.pop('sync_ckan', False)
        file_extras = kwargs.pop('file_extras', None)  # Des informations sur la ressource téléversée
        editor = kwargs.pop('editor', None)  # L'éditeur de l'objet `request` (qui peut être celui du jeu de données ou un référent)

        # Quelques contrôles sur les fichiers de données téléversée ou à télécharger
        filename = False
        file_must_be_deleted = False  # permet d'indiquer si les fichiers doivent être supprimés à la fin de la chaine de traitement
        publish_raw_resource = True  # permet d'indiquer si les ressources brutes sont publiées dans CKAN

        if self.ftp_file:
            filename = self.ftp_file.file.name
            # Si la taille de fichier dépasse la limite autorisée,
            # on traite les données en fonciton du type détecté
            if self.ftp_file.size > DOWNLOAD_SIZE_LIMIT:
                extension = self.format_type.extension.lower()
                if extension in VSI_PROTOCOLES.keys():
                    try:
                        gdalogr_obj = get_gdalogr_object(filename, extension)
                    except NotDataGISError:
                        # On essaye de traiter le jeux de données normalement, même si ça peut être long.
                        pass
                    else:
                        if gdalogr_obj.__class__.__name__ == 'GdalOpener':
                            raise ValidationError(
                                'Le fichier raster dépasse la limite autorisée. '
                                "Veuillez contacter l'administrateur du site.")
                        # if gdalogr_obj.__class__.__name__ == 'OgrOpener':
                        # On ne publie que le service OGC dans CKAN
                        publish_raw_resource = False

        elif (self.up_file and file_extras):
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

        # Détection des données SIG
        # =========================

        # /!\ Uniquement si l'utilisateur est membre partenaire du CRIGE
        if filename and editor.profile.crige_membership:

            # On vérifie s'il s'agit de données SIG, uniquement pour
            # les extensions de fichier autorisées..
            extension = self.format_type.extension.lower()
            if extension in VSI_PROTOCOLES.keys():
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
                    gdalogr_obj = get_gdalogr_object(filename, extension)
                except NotDataGISError:
                    pass
                else:
                    if gdalogr_obj.__class__.__name__ == 'OgrOpener':
                        # On convertit les données vectorielles vers Postgis.
                        try:
                            tables = ogr2postgis(
                                gdalogr_obj, update=existing_layers,
                                epsg=self.crs and self.crs.auth_code or None)

                        except NotOGRError as e:
                            file_must_be_deleted and remove_file(filename)
                            msg = (
                                "Le fichier reçu n'est pas reconnu "
                                'comme étant un jeu de données SIG correct.')
                            raise ValidationError(msg, code='__all__')

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
                                    Layer.objects.get_or_create(
                                        name=table['id'], resource=self)
                            except Exception as e:
                                file_must_be_deleted and remove_file(filename)
                                for table in tables:
                                    drop_table(table)
                                raise e

                    if gdalogr_obj.__class__.__name__ == 'GdalOpener':
                        raise Exception('TODO')  # TODO

                        if created:
                            # S'il s'agit d'une création, alors on sauve l'objet.
                            super().save(*args, **kwargs)
                            kwargs['force_insert'] = False

                        # On pousse les données matricielles vers Mapserver?
                        # On référence les données matricielles vers Mapserver?

                # On met à jour les champs de la ressource
                self.crs = [
                    SupportedCrs.objects.get(
                        auth_name='EPSG', auth_code=table['epsg'])
                    for table in tables][0]  # On prend la première valeur (c'est moche)

                # Si les données changent..
                if existing_layers and \
                        previous.get_layers() != self.get_layers():
                    # on supprime les anciens `layers`..
                    for layer in previous.get_layers():
                        layer.delete()

        # Synchronisation avec CKAN
        # =========================

        if sync_ckan:

            # Si l'utilisateur courant n'est pas l'éditeur d'un jeu
            # de données existant mais administrateur ou un référent technique,
            # alors l'admin Ckan édite le jeu de données.
            if editor == self.dataset.editor:
                ckan_user = ckan_me(ckan.get_user(editor.username)['apikey'])
            else:
                ckan_user = ckan_me(ckan.apikey)

            ckan_params = {
                'crs': self.crs and self.crs.description or '',
                'name': self.name,
                'description': self.description,
                'data_type': self.data_type,
                'extracting_service': str(self.extractable),
                'format': self.format_type.extension,
                'view_type': self.format_type.ckan_view,
                'id': str(self.ckan_id),
                'lang': self.lang,
                'restricted_by_jurisdiction': str(self.geo_restriction),
                'url': ''}

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

            if self.ftp_file:  # and publish_raw_resource:
                ckan_params['upload'] = self.ftp_file.file
                ckan_params['size'] = self.ftp_file.size
                ckan_params['mimetype'] = None  # TODO
                ckan_params['resource_type'] = self.ftp_file.name  # TODO

            ckan_package = ckan_user.get_package(str(self.dataset.ckan_id))

            # On publie la ressource brute CKAN
            if publish_raw_resource:
                ckan_user.publish_resource(ckan_package, **ckan_params)

            # Puis on publie dans CKAN les ressources de type service (à déplacer dans Layer ???)
            for layer in self.get_layers():

                # Uniquement si explicitement demandé
                if self.ogc_services:

                    getlegendgraphic = (
                        '{}?&version=1.1.1&service=WMS&request=GetLegendGraphic'
                        '&layer={}&format=image/png').format(
                            OWS_URL_PATTERN.format(
                                organisation=organisation.ckan_slug
                                ).replace('?', ''), layer.name)

                    # Tous les services sont publiés en 4171 (TODO -> configurer dans settings)
                    crs = SupportedCrs.objects.get(
                        auth_name='EPSG', auth_code='4171').description

                    url = '{0}#{1}'.format(
                        OWS_URL_PATTERN.format(
                            organisation=organisation.ckan_slug), layer.name)

                    ckan_params = {
                        'id': layer.name,
                        'name': '{} (OGC:WMS)'.format(self.name),
                        'description': 'Visualiseur cartographique',
                        'getlegendgraphic': getlegendgraphic,
                        'data_type': 'service',
                        'extracting_service': str(self.extractable),
                        'crs': crs,
                        'lang': self.lang,
                        'format': 'WMS',
                        'restricted': restricted,
                        'url': url,
                        'view_type': 'geo_view'}

                    ckan_user.publish_resource(ckan_package, **ckan_params)
                else:
                    # Sinon on force la suppression de la ressource CKAN
                    ckan_user.delete_resource(layer.name)

            ckan_user.close()

        super().save(*args, **kwargs)

        # Puis dans tous les cas..
        # on met à jour le statut des couches du service cartographique..
        if not created:
            self.update_enable_layers_status()

        # on met à jour le jeu de données parent..
        layers = list(itertools.chain.from_iterable([
            qs for qs in [
                resource.get_layers() for resource
                in Resource.objects.filter(dataset=self.dataset)]]))
        self.dataset.bbox = get_extent([layer.name for layer in layers])
        self.dataset.date_modification = timezone.now().date()
        self.dataset.save()

        # on supprime les données téléversées ou téléchargées..
        file_must_be_deleted and remove_file(filename)
