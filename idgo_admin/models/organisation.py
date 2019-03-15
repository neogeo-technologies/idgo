# Copyright (c) 2017-2019 Datasud.
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


from datetime import datetime
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.db import transaction
from django.dispatch import receiver
from django.utils.text import slugify
from functools import reduce
from idgo_admin.ckan_module import CkanBaseHandler
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.csw_module import CswBaseHandler
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import CswBaseError
from idgo_admin import logger
from idgo_admin.mra_client import MRAHandler
import inspect
from operator import iand
from operator import ior
from urllib.parse import urljoin
import uuid


DEFAULT_CONTACT_EMAIL = settings.DEFAULT_CONTACT_EMAIL
DEFAULT_PLATFORM_NAME = settings.DEFAULT_PLATFORM_NAME
ISOFORMAT_DATE = '%Y-%m-%d'
ISOFORMAT_DATETIME = '%Y-%m-%dT%H:%M:%S.%f'
OWS_URL_PATTERN = settings.OWS_URL_PATTERN


class OrganisationType(models.Model):

    class Meta(object):
        verbose_name = "Type d'organisation"
        verbose_name_plural = "Types d'organisations"
        ordering = ('name',)

    code = models.CharField(
        verbose_name="Code",
        max_length=100,
        primary_key=True,
        )

    name = models.TextField(
        verbose_name="Type d'organisation",
        )

    def __str__(self):
        return self.name


class Organisation(models.Model):

    class Meta(object):
        verbose_name = "Organisation"
        verbose_name_plural = "Organisations"
        ordering = ('slug',)

    legal_name = models.CharField(
        verbose_name="Dénomination sociale",
        max_length=100,
        unique=True,
        db_index=True,
        )

    organisation_type = models.ForeignKey(
        to='OrganisationType',
        verbose_name="Type d'organisation",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        )

    jurisdiction = models.ForeignKey(
        to='Jurisdiction',
        verbose_name="Territoire de compétence",
        blank=True,
        null=True,
        )

    slug = models.SlugField(
        verbose_name="Slug",
        max_length=100,
        unique=True,
        db_index=True,
        )

    ckan_id = models.UUIDField(
        verbose_name="Ckan UUID",
        default=uuid.uuid4,
        editable=False,
        )

    website = models.URLField(
        verbose_name="Site internet",
        blank=True,
        )

    email = models.EmailField(
        verbose_name="Adresse e-mail",
        blank=True,
        null=True,
        )

    description = models.TextField(
        verbose_name='Description',
        blank=True,
        null=True,
        )

    logo = models.ImageField(
        verbose_name="Logo",
        blank=True,
        null=True,
        upload_to='logos/',
        )

    address = models.TextField(
        verbose_name="Adresse",
        blank=True,
        null=True,
        )

    postcode = models.CharField(
        verbose_name="Code postal",
        max_length=100,
        blank=True,
        null=True,
        )

    city = models.CharField(
        verbose_name="Ville",
        max_length=100,
        blank=True,
        null=True,
        )

    phone = models.CharField(
        verbose_name="Téléphone",
        max_length=10,
        blank=True,
        null=True,
        )

    license = models.ForeignKey(
        to='License',
        verbose_name="Licence",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        )

    is_active = models.BooleanField(
        verbose_name="Organisation active",
        default=False,
        )

    is_crige_partner = models.BooleanField(
        verbose_name="Organisation partenaire du CRIGE",
        default=False,
        )

    geonet_id = models.UUIDField(
        verbose_name="UUID de la métadonnées",
        unique=True,
        db_index=True,
        blank=True,
        null=True,
        )

    def __str__(self):
        return self.legal_name

    @property
    def logo_url(self):
        try:
            return urljoin(settings.DOMAIN_NAME, self.logo.url)
        except (ValueError, Exception):
            return None

    @property
    def full_address(self):
        return "{} - {} {}".format(self.address, self.postcode, self.city)

    @property
    def ows_url(self):
        if MRAHandler.is_workspace_exists(self.slug):
            return OWS_URL_PATTERN.format(organisation=self.slug)
        # else: return None

    def get_datasets(self, **kwargs):
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        return Dataset.objects.filter(organisation=self, **kwargs)

    def get_crige_membership(self):
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        qs = Profile.objects.filter(organisation=self, crige_membership=True)
        return [profile.user for profile in qs]

    def get_members(self):
        """Retourner la liste des utilistateurs membres de l'organisation."""
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        profiles = Profile.objects.filter(organisation=self, membership=True, is_active=True)
        return [e.user for e in profiles]

    def get_contributors(self):
        """Retourner la liste des utilistateurs contributeurs de l'organisation."""
        Nexus = apps.get_model(app_label='idgo_admin', model_name='LiaisonsContributeurs')
        entries = Nexus.objects.filter(organisation=self, validated_on__isnull=False)
        return [e.profile.user for e in entries if e.profile.is_active]

    def get_referents(self):
        """Retourner la liste des utilistateurs référents de l'organisation."""
        Nexus = apps.get_model(app_label='idgo_admin', model_name='LiaisonsReferents')
        entries = Nexus.objects.filter(organisation=self, validated_on__isnull=False)
        return [e.profile.user for e in entries if e.profile.is_active]


# Triggers


@receiver(pre_save, sender=Organisation)
def pre_save_organisation(sender, instance, **kwargs):
    instance.slug = slugify(instance.legal_name)


@receiver(post_save, sender=Organisation)
def post_save_organisation(sender, instance, **kwargs):
    # Mettre à jour en cascade les profiles (utilisateurs)
    Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
    for profile in Profile.objects.filter(organisation=instance):
        profile.crige_membership = instance.is_crige_partner
        profile.save()

    # Synchroniser avec l'organisation CKAN
    if CkanHandler.is_organisation_exists(str(instance.ckan_id)):
        CkanHandler.update_organisation(instance)


@receiver(post_delete, sender=Organisation)
def post_delete_organisation(sender, instance, **kwargs):
    if CkanHandler.is_organisation_exists(str(instance.ckan_id)):
        CkanHandler.purge_organisation(str(instance.ckan_id))


# ================================================
# MODÈLE DE SYNCHRONISATION AVEC UN CATALOGUE CKAN
# ================================================


class RemoteCkan(models.Model):

    class Meta(object):
        verbose_name = "Catalogue CKAN distant"
        verbose_name_plural = "Catalogues CKAN distants"

    organisation = models.OneToOneField(
        to='Organisation',
        on_delete=models.CASCADE,
        )

    url = models.URLField(
        verbose_name="URL",
        blank=True,
        )

    sync_with = ArrayField(
        models.SlugField(max_length=100),
        verbose_name="Organisations synchronisées",
        blank=True,
        null=True,
        )

    FREQUENCY_CHOICES = (
        ('never', "Jamais"),
        ('daily', "Quotidienne (tous les jours à minuit)"),
        ('weekly', "Hebdomadaire (tous les lundi)"),
        ('bimonthly', "Bimensuelle (1er et 15 de chaque mois)"),
        ('monthly', "Mensuelle (1er de chaque mois)"),
        ('quarterly', "Trimestrielle (1er des mois de janvier, avril, juillet, octobre)"),
        ('biannual', "Semestrielle (1er janvier et 1er juillet)"),
        ('annual', "Annuelle (1er janvier)"),
        )

    sync_frequency = models.CharField(
        verbose_name="Fréquence de synchronisation",
        max_length=20,
        blank=True,
        null=True,
        choices=FREQUENCY_CHOICES,
        default='never',
        )

    def __str__(self):
        return self.url

    def save(self, *args, **kwargs):
        Category = apps.get_model(app_label='idgo_admin', model_name='Category')
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        License = apps.get_model(app_label='idgo_admin', model_name='License')
        Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
        ResourceFormats = apps.get_model(app_label='idgo_admin', model_name='ResourceFormats')

        # (1) Supprimer les jeux de données qui ne sont plus synchronisés
        previous = self.pk and RemoteCkan.objects.get(pk=self.pk)

        if previous:
            remote_organisation__in = [
                x for x in (previous.sync_with or [])
                if x not in (self.sync_with or [])]
            filter = {
                'remote_ckan': previous,
                'remote_organisation__in': remote_organisation__in}
            # TODO: 'Dataset.harvested_ckan.filter(**filter).delete()' ne fonctionne pas
            for dataset in Dataset.harvested_ckan.filter(**filter):
                dataset.delete()
        else:
            # Dans le cas d'une création, on vérifie si l'URL CKAN est valide
            try:
                with CkanBaseHandler(self.url):
                    pass
            except CkanBaseError as e:
                raise ValidationError(e.__str__(), code='url')

        # (2) Sauver l'instance
        super().save(*args, **kwargs)

        # (3) Créer/Mettre à jour les jeux de données synchronisés

        # On récupère dans le `stack` l'utilisateur effectuant l'opération
        editor = None
        for entry in inspect.stack():
            try:
                editor = entry[0].f_locals['request'].user._wrapped
            except (KeyError, AttributeError):
                continue
            break

        # Puis on moissonne le catalogue
        if self.sync_with:
            try:
                ckan_ids = []
                with transaction.atomic():

                    # TODO: Factoriser
                    for value in self.sync_with:
                        with CkanBaseHandler(self.url) as ckan:
                            ckan_organisation = ckan.get_organisation(
                                value, include_datasets=True,
                                include_groups=True, include_tags=True)

                        if not ckan_organisation.get('package_count', 0):
                            continue
                        for package in ckan_organisation.get('packages'):
                            if not package['state'] == 'active' \
                                    or not package['type'] == 'dataset':
                                continue
                            with CkanBaseHandler(self.url) as ckan:
                                package = ckan.get_package(package['id'])

                            ckan_id = uuid.UUID(package['id'])

                            update_frequency = dict(Dataset.FREQUENCY_CHOICES).get(
                                package.get('frequency'), 'unknow')
                            update_frequency = package.get('frequency')
                            if not(update_frequency and update_frequency
                                    in dict(Dataset.FREQUENCY_CHOICES).keys()):
                                update_frequency = 'unknow'
                            metadata_created = package.get('metadata_created', None)
                            if metadata_created:
                                metadata_created = datetime.strptime(metadata_created, ISOFORMAT_DATETIME)
                            metadata_modified = package.get('metadata_modified', None)
                            if metadata_modified:
                                metadata_modified = datetime.strptime(metadata_modified, ISOFORMAT_DATETIME)

                            # Licence
                            filters = [
                                Q(slug=package.get('license_id')),
                                Q(title=package.get('license_title')),
                                Q(alternate_titles__contains=[package.get('license_title')]),
                                ]
                            try:
                                license = License.objects.get(reduce(ior, filters))
                            except License.DoesNotExist:
                                try:
                                    license = License.objects.get(slug='notspecified')
                                except License.DoesNotExist:
                                    license = None

                            kvp = {
                                'slug': 'sync--{}--{}'.format(value, package.get('name'))[:100],
                                'title': package.get('title'),
                                'description': package.get('notes'),
                                'date_creation': metadata_created and metadata_created.date(),
                                'date_modification': metadata_modified and metadata_modified.date(),
                                'editor': editor,
                                'license': license,
                                'owner_email': self.organisation.email or DEFAULT_CONTACT_EMAIL,
                                'owner_name': self.organisation.legal_name or DEFAULT_PLATFORM_NAME,
                                'organisation': self.organisation,
                                'published': not package.get('private'),
                                'remote_ckan': self,
                                'remote_dataset': ckan_id,
                                'remote_organisation': value,
                                'update_frequency': update_frequency,
                                # bbox
                                # broadcaster_email
                                # broadcaster_name
                                # date_publication
                                # data_type
                                # geocover
                                # geonet_id
                                # granularity
                                # is_inspire
                                # thumbnail
                                # support
                                }

                            dataset, created = Dataset.harvested_ckan.update_or_create(**kvp)

                            categories = Category.objects.filter(
                                slug__in=[m['name'] for m in package.get('groups', [])])
                            if categories:
                                dataset.categories = categories

                            if not created:
                                dataset.keywords.clear()
                            keywords = [tag['display_name'] for tag in package.get('tags')]
                            dataset.keywords.add(*keywords)
                            dataset.save(current_user=None, synchronize=True)

                            ckan_ids.append(dataset.ckan_id)

                            for resource in package.get('resources', []):
                                try:
                                    ckan_id = uuid.UUID(resource['id'])
                                except ValueError as e:
                                    logger.exception(e)
                                    logger.error("I can't crash here, so I do not pay any attention to this error.")
                                    continue

                                try:
                                    ckan_format = resource['format'].upper()
                                    format_type = ResourceFormats.objects.get(ckan_format=ckan_format)
                                except ResourceFormats.DoesNotExist:
                                    format_type = ''

                                kvp = {
                                    'ckan_id': ckan_id,
                                    'dataset': dataset,
                                    'format_type': format_type,
                                    'title': resource['name'],
                                    'referenced_url': resource['url'],
                                    }

                                try:
                                    resource = Resource.objects.get(ckan_id=ckan_id)
                                except Resource.DoesNotExist:
                                    resource = Resource.default.create(
                                        save_opts={'current_user': editor, 'synchronize': True}, **kvp)
                                else:
                                    for k, v in kvp.items():
                                        setattr(resource, k, v)
                                resource.save(current_user=editor, synchronize=True)

            except Exception as e:
                for id in ckan_ids:
                    CkanHandler.purge_dataset(str(id))
                raise e

    def delete(self, *args, **kwargs):
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        for dataset in Dataset.harvested_ckan.filter(remote_ckan=self):
            dataset.delete()
        return super().delete(*args, **kwargs)


class RemoteCkanDataset(models.Model):

    class Meta(object):
        verbose_name = "Jeu de données moissonné"
        verbose_name_plural = "Jeux de données moissonnés"
        unique_together = ('remote_ckan', 'dataset')

    remote_ckan = models.ForeignKey(
        to='RemoteCkan',
        on_delete=models.CASCADE,
        to_field='id',
        )

    dataset = models.ForeignKey(
        to='Dataset',
        on_delete=models.CASCADE,
        to_field='id',
        )

    remote_dataset = models.UUIDField(
        verbose_name="Ckan UUID",
        editable=False,
        null=True,
        blank=True,
        unique=True,
        )

    remote_organisation = models.SlugField(
        verbose_name="Organisation distante",
        max_length=100,
        blank=True,
        null=True,
        )

    created_by = models.ForeignKey(
        User,
        related_name='creates_dataset_from_remote_ckan',
        verbose_name="Utilisateur",
        null=True,
        on_delete=models.SET_NULL,
        )

    created_on = models.DateTimeField(
        verbose_name="Créé le",
        auto_now_add=True,
        )

    updated_on = models.DateTimeField(
        verbose_name="Mis-à-jour le",
        auto_now_add=True,
        )

    def __str__(self):
        return '{0} - {1}'.format(self.remote_ckan, self.dataset)

    @property
    def url(self):
        base_url = self.remote_ckan.url
        if not base_url.endswith('/'):
            base_url += '/'
        return reduce(urljoin, [base_url, 'dataset/', str(self.remote_dataset)])


# ===============================================
# MODÈLE DE SYNCHRONISATION AVEC UN CATALOGUE CWS
# ===============================================


class RemoteCsw(models.Model):

    class Meta(object):
        verbose_name = "Catalogue CSW distant"
        verbose_name_plural = "Catalogues CSW distants"

    organisation = models.OneToOneField(
        to='Organisation',
        on_delete=models.CASCADE,
        )

    url = models.URLField(
        verbose_name="URL",
        blank=True,
        )

    sync_with = ArrayField(
        models.SlugField(max_length=100),
        verbose_name="Organisations synchronisées",
        blank=True,
        null=True,
        )

    FREQUENCY_CHOICES = (
        ('never', "Jamais"),
        ('daily', "Quotidienne (tous les jours à minuit)"),
        ('weekly', "Hebdomadaire (tous les lundi)"),
        ('bimonthly', "Bimensuelle (1er et 15 de chaque mois)"),
        ('monthly', "Mensuelle (1er de chaque mois)"),
        ('quarterly', "Trimestrielle (1er des mois de janvier, avril, juillet, octobre)"),
        ('biannual', "Semestrielle (1er janvier et 1er juillet)"),
        ('annual', "Annuelle (1er janvier)"),
        )

    sync_frequency = models.CharField(
        verbose_name="Fréquence de synchronisation",
        max_length=20,
        blank=True,
        null=True,
        choices=FREQUENCY_CHOICES,
        default='never',
        )

    def __str__(self):
        return self.url

    def save(self, *args, **kwargs):
        Category = apps.get_model(app_label='idgo_admin', model_name='Category')
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        License = apps.get_model(app_label='idgo_admin', model_name='License')
        Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
        ResourceFormats = apps.get_model(app_label='idgo_admin', model_name='ResourceFormats')

        # (1) Supprimer les jeux de données qui ne sont plus synchronisés
        previous = self.pk and RemoteCsw.objects.get(pk=self.pk)

        if previous:
            remote_organisation__in = [
                x for x in (previous.sync_with or [])
                if x not in (self.sync_with or [])]
            filter = {
                'remote_instance': previous,
                'remote_organisation__in': remote_organisation__in}
            # TODO: 'Dataset.harvested_csw.filter(**filter).delete()' ne fonctionne pas
            for dataset in Dataset.harvested_csw.filter(**filter):
                dataset.delete()
        else:
            # Dans le cas d'une création, on vérifie si l'URL CSW est valide
            try:
                with CswBaseHandler(self.url):
                    pass
            except CswBaseError as e:
                raise ValidationError(e.__str__(), code='url')

        # (2) Sauver l'instance
        super().save(*args, **kwargs)

        # (3) Créer/Mettre à jour les jeux de données synchronisés

        # On récupère dans le `stack` l'utilisateur effectuant l'opération
        editor = None
        for entry in inspect.stack():
            try:
                editor = entry[0].f_locals['request'].user._wrapped
            except (KeyError, AttributeError):
                continue
            break

        # Puis on moissonne le catalogue
        if self.sync_with:
            try:
                ckan_ids = []
                with transaction.atomic():

                    # TODO: Factoriser
                    for value in self.sync_with:
                        with CswBaseHandler(self.url) as csw:
                            csw_organisation = csw.get_organisation(
                                value, include_datasets=True)
                        if not csw_organisation.get('package_count', 0):
                            continue
                        for package in csw_organisation.get('packages'):
                            if not package['state'] == 'active' \
                                    or not package['type'] == 'dataset':
                                continue
                            with CswBaseHandler(self.url) as csw:
                                package = csw.get_package(package['id'])

                            geonet_id = uuid.UUID(package['id'])

                            update_frequency = dict(Dataset.FREQUENCY_CHOICES).get(
                                package.get('frequency'), 'unknow')
                            update_frequency = package.get('frequency')
                            if not(update_frequency and update_frequency
                                    in dict(Dataset.FREQUENCY_CHOICES).keys()):
                                update_frequency = 'unknow'
                            metadata_created = package.get('metadata_created', None)
                            if metadata_created:
                                metadata_created = datetime.strptime(metadata_created, ISOFORMAT_DATE)
                            metadata_modified = package.get('metadata_modified', None)
                            if metadata_modified:
                                metadata_modified = datetime.strptime(metadata_modified, ISOFORMAT_DATE)

                            # Licence
                            filters = [
                                Q(slug=package.get('license_id')),
                                Q(title=package.get('license_title')),
                                Q(alternate_titles__contains=[package.get('license_title')]),
                                ]
                            try:
                                license = License.objects.get(reduce(ior, filters))
                            except License.DoesNotExist:
                                try:
                                    license = License.objects.get(slug='notspecified')
                                except License.DoesNotExist:
                                    license = None

                            kvp = {
                                'slug': 'sync--{}--{}'.format(slugify(value), package.get('name'))[:100],
                                'title': package.get('title'),
                                'description': package.get('notes'),
                                'date_creation': metadata_created and metadata_created.date(),
                                'date_modification': metadata_modified and metadata_modified.date(),
                                'editor': editor,
                                'license': license,
                                'owner_email': self.organisation.email or DEFAULT_CONTACT_EMAIL,
                                'owner_name': self.organisation.legal_name or DEFAULT_PLATFORM_NAME,
                                'organisation': self.organisation,
                                'published': not package.get('private'),
                                'remote_instance': self,
                                'remote_dataset': geonet_id,
                                'remote_organisation': value,
                                'update_frequency': update_frequency,
                                # bbox
                                # broadcaster_email
                                # broadcaster_name
                                # date_publication
                                # data_type
                                # geocover
                                # geonet_id
                                # granularity
                                # is_inspire
                                # thumbnail
                                # support
                                }

                            dataset, created = Dataset.harvested_csw.update_or_create(**kvp)

                            categories = Category.objects.filter(
                                slug__in=[m['name'] for m in package.get('groups', [])])
                            if categories:
                                dataset.categories = categories

                            if not created:
                                dataset.keywords.clear()
                            keywords = [tag['display_name'] for tag in package.get('tags')]
                            dataset.keywords.add(*keywords)
                            dataset.save(current_user=None, synchronize=True)

                            ckan_ids.append(dataset.ckan_id)

                            for resource in package.get('resources', []):
                                try:
                                    ckan_id = uuid.uuid4()
                                except ValueError as e:
                                    logger.exception(e)
                                    logger.error("I can't crash here, so I do not pay any attention to this error.")
                                    continue

                                filters = []
                                protocol = resource.get('protocol')
                                protocol and filters.append(Q(protocol=protocol))
                                mimetype = resource.get('mimetype')
                                mimetype and filters.append(Q(mimetype__overlap=[mimetype]))
                                try:
                                    format_type = ResourceFormats.objects.get(reduce(iand, filters))
                                except (ResourceFormats.MultipleObjectsReturned, ResourceFormats.DoesNotExist):
                                    format_type = None

                                kvp = {
                                    'ckan_id': ckan_id,
                                    'dataset': dataset,
                                    'format_type': format_type,
                                    'title': resource['name'],
                                    'referenced_url': resource['url'],
                                    }

                                try:
                                    resource = Resource.objects.get(ckan_id=ckan_id)
                                except Resource.DoesNotExist:
                                    resource = Resource.default.create(
                                        save_opts={'current_user': editor, 'synchronize': True}, **kvp)
                                else:
                                    for k, v in kvp.items():
                                        setattr(resource, k, v)
                                resource.save(current_user=editor, synchronize=True)

            except Exception as e:
                for id in ckan_ids:
                    CkanHandler.purge_dataset(str(id))
                raise e

    def delete(self, *args, **kwargs):
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        for dataset in Dataset.harvested.filter(remote_instance=self):
            dataset.delete()
        return super().delete(*args, **kwargs)


class RemoteCswDataset(models.Model):

    class Meta(object):
        verbose_name = "Jeu de données moissonné"
        verbose_name_plural = "Jeux de données moissonnés"
        unique_together = ('remote_instance', 'dataset')

    remote_instance = models.ForeignKey(
        to='RemoteCsw',
        on_delete=models.CASCADE,
        to_field='id',
        )

    dataset = models.ForeignKey(
        to='Dataset',
        on_delete=models.CASCADE,
        to_field='id',
        )

    remote_dataset = models.UUIDField(
        verbose_name="UUID",
        editable=False,
        null=True,
        blank=True,
        unique=True,
        )

    remote_organisation = models.SlugField(
        verbose_name="Organisation distante",
        max_length=100,
        blank=True,
        null=True,
        )

    created_by = models.ForeignKey(
        User,
        related_name='creates_dataset_from_remote_csw',
        verbose_name="Utilisateur",
        null=True,
        on_delete=models.SET_NULL,
        )

    created_on = models.DateTimeField(
        verbose_name="Créé le",
        auto_now_add=True,
        )

    updated_on = models.DateTimeField(
        verbose_name="Mis-à-jour le",
        auto_now_add=True,
        )

    def __str__(self):
        return '{0} - {1}'.format(self.remote_instance, self.dataset)

    @property
    def url(self):
        base_url = self.remote_instance.url
        if not base_url.endswith('/'):
            base_url += '/'
        return reduce(urljoin, [base_url, 'dataset/', str(self.remote_dataset)])
