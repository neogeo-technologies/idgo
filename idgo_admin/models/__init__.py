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


from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils.text import slugify
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.models.account import AccountActions
from idgo_admin.models.account import LiaisonsContributeurs
from idgo_admin.models.account import LiaisonsReferents
from idgo_admin.models.account import LiaisonsResources
from idgo_admin.models.account import Profile
from idgo_admin.models.dataset import Dataset
from idgo_admin.models.extractor import AsyncExtractorTask
from idgo_admin.models.extractor import ExtractorSupportedFormat
from idgo_admin.models.jurisdiction import Commune
from idgo_admin.models.jurisdiction import Jurisdiction
from idgo_admin.models.jurisdiction import JurisdictionCommune
from idgo_admin.models.layer import Layer
from idgo_admin.models.mail import Mail
from idgo_admin.models.organisation import Organisation
from idgo_admin.models.organisation import OrganisationType
from idgo_admin.models.organisation import RemoteCkan
from idgo_admin.models.organisation import RemoteCkanDataset
from idgo_admin.models.resource import Resource
from idgo_admin.models.resource import ResourceFormats
from idgo_admin.models.resource import upload_resource
import json
import os
import uuid


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
except Exception:
    AUTHORIZED_ISO_TOPIC = None


class BaseMaps(models.Model):

    class Meta(object):
        verbose_name = 'Fond cartographique'
        verbose_name_plural = 'Fonds cartographiques'

    name = models.TextField(verbose_name='Titre', unique=True)

    url = models.URLField(verbose_name='URL')

    options = JSONField(verbose_name='Options')


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
            CkanHandler.update_group(self)
        else:
            CkanHandler.add_group(self)

    def clean(self):
        self.ckan_slug = slugify(self.name)
        try:
            self.sync_ckan()
        except Exception as e:
            raise ValidationError(e.__str__())


@receiver(pre_delete, sender=Category)
def pre_delete_category(sender, instance, **kwargs):
    if CkanHandler.is_group_exists(str(instance.ckan_id)):
        CkanHandler.del_group(str(instance.ckan_id))


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

    order = models.IntegerField(unique=True, blank=True, null=True)

    class Meta(object):
        verbose_name = 'Granularité de la couverture territoriale'
        verbose_name_plural = 'Granularités des couvertures territoriales'

    def __str__(self):
        return self.name


class License(models.Model):

    # MODELE LIE AUX LICENCES CKAN. MODIFIER EGALEMENT DANS LA CONF CKAN
    # QUAND DES ELEMENTS SONT AJOUTES, il faut mettre à jour
    # le fichier /etc/ckan/default/licenses.json

    slug = models.SlugField(
        max_length=100,
        primary_key=True,
        verbose_name="Identifier",
        )

    title = models.TextField(
        verbose_name="Title",
        )

    alternate_titles = ArrayField(
        models.TextField(),
        blank=True,
        null=True,
        size=None,
        verbose_name="Alternate titles",
        )

    url = models.URLField(
        blank=True,
        null=True,
        verbose_name="URL",
        )

    alternate_urls = ArrayField(
        models.URLField(),
        blank=True,
        null=True,
        size=None,
        verbose_name="Alternate URLs",
        )

    domain_content = models.BooleanField(
        default=False,
        verbose_name="Domain Content",
        )

    domain_data = models.BooleanField(
        default=False,
        verbose_name="Domain Data",
        )

    domain_software = models.BooleanField(
        default=False,
        verbose_name="Domain Software",
        )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('deleted', 'Deleted'),
        )

    status = models.CharField(
        default='active',
        choices=STATUS_CHOICES,
        max_length=7,
        verbose_name="Status",
        )

    maintainer = models.TextField(
        blank=True,
        null=True,
        verbose_name="Maintainer",
        )

    CONFORMANCE_CHOICES = (
        ('approved', 'Approved'),
        ('not reviewed', 'Not reviewed'),
        ('rejected', 'Rejected'),
        )

    od_conformance = models.CharField(
        default='not reviewed',
        choices=CONFORMANCE_CHOICES,
        max_length=30,
        verbose_name="Open Definition Conformance",
        )

    osd_conformance = models.CharField(
        default='not reviewed',
        choices=CONFORMANCE_CHOICES,
        max_length=30,
        verbose_name="Open Source Definition Conformance",
        )

    class Meta(object):
        verbose_name = "Licence"
        verbose_name_plural = "Licences"

    def __str__(self):
        return self.title

    @property
    def ckan_id(self):
        return self.slug


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


class SupportedCrs(models.Model):

    auth_name = models.CharField(
        verbose_name='Authority Name', max_length=100, default='EPSG')

    auth_code = models.CharField(
        verbose_name='Authority Code', max_length=100)

    description = models.TextField(
        verbose_name='Description', blank=True, null=True)

    regex = models.TextField(
        verbose_name='Expression régulière', blank=True, null=True)

    class Meta(object):
        verbose_name = "CRS supporté par l'application"
        verbose_name_plural = "CRS supportés par l'application"

    @property
    def authority(self):
        return '{}:{}'.format(self.auth_name, self.auth_code)

    def __str__(self):
        return '{}:{} ({})'.format(
            self.auth_name, self.auth_code, self.description)


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


__all__ = [
    AccountActions, AsyncExtractorTask, BaseMaps, Category, Commune,
    Dataset, DataType, ExtractorSupportedFormat,
    Granularity, Jurisdiction, JurisdictionCommune, Layer, License,
    LiaisonsContributeurs, LiaisonsResources, LiaisonsReferents,
    Mail, Organisation, OrganisationType, Profile,
    RemoteCkan, RemoteCkanDataset, Resource, ResourceFormats,
    Support, SupportedCrs, Task, upload_resource]
