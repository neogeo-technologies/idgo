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


from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete
from django.db.models.signals import pre_delete
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.datagis import get_extent
from idgo_admin.managers import HarvestedDataset
from idgo_admin.utils import three_suspension_points
import itertools
from taggit.managers import TaggableManager
from urllib.parse import urljoin
import uuid


CKAN_URL = settings.CKAN_URL
GEONETWORK_URL = settings.GEONETWORK_URL
OWS_URL_PATTERN = settings.OWS_URL_PATTERN
DEFAULT_CONTACT_EMAIL = settings.DEFAULT_CONTACT_EMAIL
DEFAULT_PLATFORM_NAME = settings.DEFAULT_PLATFORM_NAME


def bounds_to_wkt(xmin, ymin, xmax, ymax):
    return (
        'POLYGON(({xmin} {ymin}, {xmax} {ymin}, {xmax} {ymax}, {xmin} {ymax}, {xmin} {ymin}))'
        ).format(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)

try:
    BOUNDS = settings.DEFAULTS_VALUES['BOUNDS']
except AttributeError:
    xmin, ymin = -180, -90
    xmax, ymax = 180, 90
else:
    xmin, ymin = BOUNDS[0][1], BOUNDS[0][0]
    xmax, ymax = BOUNDS[1][1], BOUNDS[1][0]
finally:
    DEFAULT_BBOX = bounds_to_wkt(xmin, ymin, xmax, ymax)

TODAY = timezone.now().date()


class Dataset(models.Model):

    objects = models.Manager()
    harvested = HarvestedDataset()

    _current_editor = None

    GEOCOVER_CHOICES = (
        (None, 'Indéfinie'),
        ('regionale', 'Régionale'),
        ('jurisdiction', 'Territoire de compétence'))

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
        default=None, max_length=30, choices=GEOCOVER_CHOICES)

    # Mandatory
    organisation = models.ForeignKey(
        to='Organisation',
        verbose_name="Organisation à laquelle est rattaché ce jeu de données",
        blank=True, null=True, on_delete=models.CASCADE)

    # (Not) mandatory
    license = models.ForeignKey(
        to='License', verbose_name='Licence', null=True, blank=True)

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

    # (Not) mandatory
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        RemoteCkanDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')
        try:
            remote_ckan_dataset = RemoteCkanDataset.objects.get(dataset=self)
        except RemoteCkanDataset.DoesNotExist:
            remote_ckan_dataset = None

        self.is_harvested = remote_ckan_dataset and True or False
        self.remote_ckan_dataset = remote_ckan_dataset or None

    @property
    def private(self):
        return not self.published

    @property
    def ckan_url(self):
        return urljoin(settings.CKAN_URL, 'dataset/{}'.format(self.ckan_slug))

    def get_resources(self, **kwargs):
        Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
        return Resource.objects.filter(dataset=self, **kwargs)

    @property
    def name_overflow(self):
        return three_suspension_points(self.name)

    @property
    def bounds(self):
        if self.bbox:
            minx, miny, maxx, maxy = self.bbox.extent
            return [[miny, minx], [maxy, maxx]]

    def get_layers(self):
        return list(itertools.chain.from_iterable([
            qs for qs in [
                resource.get_layers() for resource in self.get_resources()]]))

    def is_contributor(self, profile):
        LiaisonsContributeurs = apps.get_model(
            app_label='idgo_admin', model_name='LiaisonsContributeurs')

        return LiaisonsContributeurs.objects.filter(
            profile=profile, organisation=self.organisation,
            validated_on__isnull=False).exists()

    def is_referent(self, profile):
        LiaisonsReferents = apps.get_model(
            app_label='idgo_admin', model_name='LiaisonsReferents')

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
            self.support and self.support.name or DEFAULT_PLATFORM_NAME
        broadcaster_email = self.broadcaster_email or \
            self.support and self.support.email or DEFAULT_CONTACT_EMAIL

        if not self.bbox:
            if not self.geocover and (
                    self.organisation and self.organisation.jurisdiction):
                setattr(self, 'geocover', 'jurisdiction')

        layers = self.get_layers()
        if not layers:
            # Seulement s'il n'y a pas de layers rattachés au jeu de données.
            # car sinon la bbox devrait être celle des couches
            if self.geocover == 'jurisdiction':
                # Prend l'étendue du territoire de compétence
                if self.organisation:
                    jurisdiction = self.organisation.jurisdiction
                    if jurisdiction and jurisdiction.communes:
                        bounds = jurisdiction.get_bounds()
                        if bounds:
                            xmin, ymin = bounds[0][1], bounds[0][0]
                            xmax, ymax = bounds[1][1], bounds[1][0]
                            setattr(self, 'bbox', bounds_to_wkt(xmin, ymin, xmax, ymax))
            elif self.geocover == 'regionale':
                # Prend l'étendue par défaut définie en settings
                setattr(self, 'bbox', DEFAULT_BBOX)
        else:
            # TODO ajouter les raster !
            bbox = get_extent([layer.name for layer in layers if layer.type == 'vector'])
            setattr(self, 'bbox', bbox)

        super().save(*args, **kwargs)

        if previous and previous.organisation:
            ckan.deactivate_ckan_organization_if_empty(
                str(previous.organisation.ckan_id))

        if sync_ckan:
            ows = False
            Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
            for resource in Resource.objects.filter(dataset=self):
                ows = resource.ogc_services

            if self.license and self.license.ckan_id in [
                    license['id'] for license in ckan.get_licenses()]:
                license_id = self.license.ckan_id
            else:
                license_id = ''

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
                'geocover': self.geocover or '',
                'granularity': self.granularity and self.granularity.slug or None,
                'last_modified':
                    str(self.date_modification) if self.date_modification else '',
                'license_id': license_id,
                'maintainer': broadcaster_name,
                'maintainer_email': broadcaster_email,
                'name': self.ckan_slug,
                'notes': self.description,
                'owner_org': str(self.organisation.ckan_id),
                'ows': str(ows),
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

            LiaisonsContributeurs = apps.get_model(
                app_label='idgo_admin', model_name='LiaisonsContributeurs')

            for profile \
                    in LiaisonsContributeurs.get_contributors(self.organisation):
                ckan.add_user_to_organization(
                    profile.user.username, organisation_ckan_id)

            ckan_dataset = \
                ckan_user.publish_dataset(
                    id=self.ckan_id and str(self.ckan_id), **ckan_params)

            ckan_user.close()

        # On vérifie si l'organisation du jeu de données change.
        # Si c'est le cas, il est nécessaire de sauvegarder tous
        # les `Layers` rattachés au jeu de données afin de forcer
        # la modification du `Workspace` (c'est-à-dire du Mapfile)
        ws_name = self.organisation.ckan_slug
        if previous and not previous.organisation == self.organisation:
            for resource in previous.get_resources():
                for layer in resource.get_layers():
                    layer.save()
                    # TODO: déplacer dans Layer.save()
                    ckan_user.update_resource(
                        layer.name, url='{0}#{1}'.format(
                            OWS_URL_PATTERN.format(organisation=ws_name), layer.name))

        self.ckan_id = uuid.UUID(ckan_dataset['id'])
        super().save()

    @classmethod
    def get_subordinated_datasets(cls, profile):
        LiaisonsReferents = apps.get_model(
            app_label='idgo_admin', model_name='LiaisonsReferents')

        return cls.objects.filter(
            organisation__in=LiaisonsReferents.get_subordinated_organizations(
                profile=profile))


# Triggers


@receiver(pre_save, sender=Dataset)
def pre_save_dataset(sender, instance, **kwargs):
    if not instance.ckan_slug:
        instance.ckan_slug = slugify(instance.name)


@receiver(pre_delete, sender=Dataset)
def pre_delete_dataset(sender, instance, **kwargs):
    Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
    Resource.objects.filter(dataset=instance).delete()
    ckan.purge_dataset(instance.ckan_slug)


@receiver(post_delete, sender=Dataset)
def post_delete_dataset(sender, instance, **kwargs):
    ckan.deactivate_ckan_organization_if_empty(str(instance.organisation.ckan_id))
