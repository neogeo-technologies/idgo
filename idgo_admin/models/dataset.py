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
from django.db.models.signals import post_save
from django.db.models.signals import pre_delete
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.ckan_module import CkanUserHandler
from idgo_admin.datagis import bounds_to_wkt
from idgo_admin import logger
from idgo_admin.managers import DefaultDatasetManager
from idgo_admin.managers import HarvestedDataset
from idgo_admin.models import get_super_editor
from idgo_admin.utils import three_suspension_points
from taggit.managers import TaggableManager
from urllib.parse import urljoin
import uuid


CKAN_URL = settings.CKAN_URL
GEONETWORK_URL = settings.GEONETWORK_URL
OWS_URL_PATTERN = settings.OWS_URL_PATTERN
DEFAULT_CONTACT_EMAIL = settings.DEFAULT_CONTACT_EMAIL
DEFAULT_PLATFORM_NAME = settings.DEFAULT_PLATFORM_NAME


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


class Dataset(models.Model):
    """Modèle de classe d'un jeu de données."""

    # Managers
    # ========

    objects = models.Manager()

    default = DefaultDatasetManager()
    harvested = HarvestedDataset()

    # Champs
    # ======

    name = models.TextField(verbose_name='Titre')                              # TODO: Remplacer par `title`

    ckan_slug = models.SlugField(                                              # TODO: Remplacer par `slug`
        error_messages={
            'invalid': (
                "Le label court ne peut contenir ni majuscule, "
                "ni caractères spéciaux à l'exception le tiret.")},
        verbose_name='Label court', max_length=100,
        unique=True, db_index=True, blank=True, null=True)

    ckan_id = models.UUIDField(                                                # TODO: Voir si possible de remplacer l'`id`
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
        ('semiannual', 'Bi-annuelle'),
        ('annual', 'Annuelle'),
        ('unknow', 'Inconnue'))

    update_freq = models.CharField(
        verbose_name='Fréquence de mise à jour', default='never',
        max_length=30, choices=FREQUENCY_CHOICES)

    GEOCOVER_CHOICES = (
        (None, 'Indéfinie'),
        ('regionale', 'Régionale'),
        ('jurisdiction', 'Territoire de compétence'))

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

    granularity = models.ForeignKey(
        to='Granularity',
        blank=True, null=True,
        verbose_name='Granularité de la couverture territoriale',
        on_delete=models.PROTECT)

    bbox = models.PolygonField(
        verbose_name='Rectangle englobant', blank=True, null=True, srid=4171)

    class Meta(object):
        verbose_name = 'Jeu de données'
        verbose_name_plural = 'Jeux de données'

    def __str__(self):
        return self.name

    def __slug__(self):
        return self.ckan_slug or slugify(self.name)

    def __init__(self, *args, **kwargs):
        self.current_user = None
        super().__init__(*args, **kwargs)

        # On regarde si le jeu de données est moissonnées
        # RemoteCkanDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')
        # try:
        #     remote_ckan_dataset = RemoteCkanDataset.objects.get(dataset=self)
        # except RemoteCkanDataset.DoesNotExist:
        #     self.remote_ckan_dataset = None
        #     self.is_harvested = False
        # else:
        #     self.remote_ckan_dataset = remote_ckan_dataset
        #     self.is_harvested = True

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
        Layer = apps.get_model(app_label='idgo_admin', model_name='Layer')
        return Layer.objects.filter(resource__dataset__pk=self.pk)

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

    @classmethod
    def get_subordinated_datasets(cls, profile):
        Nexus = apps.get_model(app_label='idgo_admin', model_name='LiaisonsReferents')
        organisations = Nexus.get_subordinated_organizations(profile=profile)
        return cls.objects.filter(organisation__in=organisations)

    # Méthodes Django
    # ===============

    def clean(self):

        # Vérifie la disponibilité du « slug » dans CKAN
        slug = self.ckan_slug or slugify(self.name)
        with CkanUserHandler(CkanHandler.apikey) as ckan_me:
            ckan_dataset = ckan_me.get_package(slug)
        if ckan_dataset \
                and uuid.UUID(ckan_dataset.get('id')) != self.ckan_id \
                and ckan_dataset.get('name') == slug:
            raise ValidationError("L'URL du jeu de données est réservé.")

    def save(self, *args, current_user=None, synchronize=True, **kwargs):

        # Utilisateur à l'origine de l'exécution de la fonction :
        self.current_user = current_user

        # Version précédante du jeu de données (avant modification) :
        previous = self.pk and Dataset.objects.get(pk=self.pk)
        if not previous:
            self.editor = self.current_user

        # Quelques valeurs par défaut
        # ===========================
        today = timezone.now().date()
        if not self.date_creation:      # La date de création
            self.date_creation = today
        if not self.date_modification:  # La date de modification
            self.date_modification = today
        if not self.date_publication:   # La date de publication
            self.date_publication = today

        if not self.owner_name:         # Le propriétaire du jeu de données
            self.owner_name = self.editor.get_full_name()
        if not self.owner_email:        # et son e-mail
            self.owner_email = self.editor.email

        # Le rectangle englobant du jeu de données :
        #     Il est calculé en fonction des ressources géographiques et/ou de la couverture
        #     et/ou de la couverture géographique définie
        layers = self.get_layers()
        if layers:
            # On calcule la BBOX de l'ensemble des Layers rattachés au Dataset
            extent = layers.aggregate(models.Extent('bbox')).get('bbox__extent')
            if extent:
                xmin, ymin = extent[0], extent[1]
                xmax, ymax = extent[2], extent[3]
                setattr(self, 'bbox', bounds_to_wkt(xmin, ymin, xmax, ymax))
        else:
            # Sinon, on regarde la valeur de `geocover` renseignée
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
                setattr(self, 'bbox', None)

        # On regarde si le jeu de données est moissonnées
        RemoteCkanDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')
        try:
            remote_ckan_dataset = RemoteCkanDataset.objects.get(dataset=self)
        except RemoteCkanDataset.DoesNotExist:
            self.remote_ckan_dataset = None
            self.is_harvested = False
        else:
            self.remote_ckan_dataset = remote_ckan_dataset
            self.is_harvested = True

        # On sauvegarde le jeu de données
        super().save(*args, **kwargs)

        # Puis...
        if previous:
            # Une organisation CKAN ne contenant plus
            # de jeu de données doit être désactivée.
            if previous.organisation:
                CkanHandler.deactivate_ckan_organization_if_empty(str(previous.organisation.ckan_id))

            # On vérifie si l'organisation du jeu de données change.
            # Si c'est le cas, il est nécessaire de sauvegarder tous
            # les `Layers` rattachés au jeu de données afin de forcer
            # la modification du `Workspace` (c'est-à-dire du Mapfile)
            if previous.organisation != self.organisation:
                for resource in previous.get_resources():
                    for layer in resource.get_layers():
                        layer.save()
                        url = '{0}#{1}'.format(
                            OWS_URL_PATTERN.format(organisation=self.organisation.ckan_slug),
                            layer.name)
                        CkanHandler.update_resource(layer.name, url=url)

        # Enfin...
        if synchronize:
            ckan_dataset = self.synchronize(with_user=self.current_user)
            # puis on met à jour `ckan_id`
            self.ckan_id = uuid.UUID(ckan_dataset['id'])
            super().save(update_fields=['ckan_id'])

    def synchronize(self, with_user=None):
        """Synchronizer le jeu de données avec l'instance de CKAN."""
        user = with_user or get_super_editor()

        # Identifiant du package CKAN :
        id = self.ckan_id and str(self.ckan_id) or None
        # Si la valeur est `None`, alors il s'agit d'une création.

        # Définition des propriétés du « package » :

        datatype = [item.ckan_slug for item in self.data_type.all()]

        dataset_creation_date = self.date_creation and str(self.date_creation) or ''
        dataset_modification_date = self.date_modification and str(self.date_modification) or ''
        dataset_publication_date = self.date_publication and str(self.date_publication) or ''

        broadcaster_name = self.broadcaster_name or \
            self.support and self.support.name or DEFAULT_PLATFORM_NAME
        broadcaster_email = self.broadcaster_email or \
            self.support and self.support.email or DEFAULT_CONTACT_EMAIL

        geocover = self.geocover or ''

        granularity = self.granularity and self.granularity.slug or ''

        if self.geonet_id:
            inspire_url = '{0}srv/fre/catalog.search#/metadata/{1}'.format(GEONETWORK_URL, self.geonet_id or '')
        else:
            inspire_url = ''

        licenses = [license['id'] for license in CkanHandler.get_licenses()]
        if self.license and self.license.ckan_id in licenses:
            license_id = self.license.ckan_id
        else:
            license_id = ''

        ows = False
        Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
        for resource in Resource.objects.filter(dataset=self):
            ows = resource.ogc_services

        private = not self.published

        remote_ckan_url = self.is_harvested and self.remote_ckan_dataset.url or ''

        spatial = self.bbox and self.bbox.geojson or ''

        support = self.support and self.support.ckan_slug or ''

        tags = [{'name': keyword.name} for keyword in self.keywords.all()]

        try:
            thumbnail = urljoin(settings.DOMAIN_NAME, self.thumbnail.url)
        except ValueError:
            thumbnail = ''

        data = {
            'author': self.owner_name,
            'author_email': self.owner_email,
            'datatype': datatype,
            'dataset_creation_date': dataset_creation_date,
            'dataset_modification_date': dataset_modification_date,
            'dataset_publication_date': dataset_publication_date,
            'geocover': geocover,
            'granularity': granularity,
            'groups': [],  # Voir plus bas
            'inspire_url': inspire_url,
            'last_modified': dataset_publication_date,
            'license_id': license_id,
            'maintainer': broadcaster_name,
            'maintainer_email': broadcaster_email,
            'name': self.ckan_slug,
            'notes': self.description,
            'owner_org': str(self.organisation.ckan_id),
            'ows': str(ows),  # I <3 CKAN
            'private': private,
            'remote_ckan_url': remote_ckan_url,
            'spatial': spatial,
            'state': 'active',
            'support': support,
            'tags': tags,
            'title': self.name,
            'thumbnail': thumbnail,
            'update_frequency': self.update_freq,
            'url': ''  # Toujours une chaîne de caractère vide !
            }

        # Synchronisation des catégories :
        for category in self.categories.all():
            data['groups'].append({'name': category.ckan_slug})

        organisation_id = str(self.organisation.ckan_id)

        # Synchronisation de l'organisation ; si l'organisation
        # n'existe pas il faut la créer
        ckan_organization = CkanHandler.get_organization(organisation_id)
        if not ckan_organization:
            CkanHandler.add_organization(self.organisation)
        # et si l'organisation est désactiver il faut l'activer
        elif ckan_organization.get('state') == 'deleted':
            CkanHandler.activate_organization(organisation_id)

        # Si l'utilisateur courant n'est pas l'éditeur d'un jeu
        # de données existant mais le référent technique, alors
        # l'api-key du référent est utilisée.
        if hasattr(user, 'profile'):
            username = user.username

            # ~ ~ ~ #
            # TODO: C'est très lourd de faire cela systématiquement -> voir pour améliorer cela
            CkanHandler.add_user_to_organization(username, organisation_id)
            for category in self.categories.all():
                category_id = str(category.ckan_id)
                CkanHandler.add_user_to_group(username, category_id)
            # ~ ~ ~ #

            apikey = CkanHandler.get_user(username)['apikey']
            with CkanUserHandler(apikey=apikey) as ckan_user:
                return ckan_user.publish_dataset(id=id, **data)
        else:
            return CkanHandler.publish_dataset(id=id, **data)


# Triggers


@receiver(pre_save, sender=Dataset)
def pre_save_dataset(sender, instance, **kwargs):
    if not instance.ckan_slug:
        instance.ckan_slug = slugify(instance.name)


@receiver(pre_delete, sender=Dataset)
def pre_delete_dataset(sender, instance, **kwargs):
    Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
    Resource.objects.filter(dataset=instance).delete()
    CkanHandler.purge_dataset(instance.ckan_slug)


@receiver(post_delete, sender=Dataset)
def post_delete_dataset(sender, instance, **kwargs):
    CkanHandler.deactivate_ckan_organization_if_empty(str(instance.organisation.ckan_id))


# Logging
# =======


@receiver(post_save, sender=Dataset)
def logging_after_save(sender, instance, **kwargs):
    if kwargs.get('created', False):
        logger.info('Dataset `{}` has been created'.format(instance.pk))
    else:
        logger.info('Dataset `{}` has been updated'.format(instance.pk))
