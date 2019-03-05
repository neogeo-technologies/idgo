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
        verbose_name = "Fond cartographique"
        verbose_name_plural = "Fonds cartographiques"

    name = models.TextField(
        verbose_name="Nom",
        unique=True,
        )

    url = models.URLField(
        verbose_name="URL",
        )

    options = JSONField(
        verbose_name="Options",
        )


class Category(models.Model):

    class Meta(object):
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    slug = models.SlugField(
        verbose_name='Slug',
        max_length=100,
        unique=True,
        db_index=True,
        blank=True,
        )

    ckan_id = models.UUIDField(
        verbose_name='Identifiant CKAN',
        editable=False,
        default=uuid.uuid4,
        )

    name = models.CharField(
        verbose_name='Nom',
        max_length=100,
        )

    description = models.CharField(
        verbose_name='Description',
        max_length=1024,
        )

    ISO_TOPIC_CHOICES = AUTHORIZED_ISO_TOPIC

    iso_topic = models.CharField(
        verbose_name="Thème ISO",
        max_length=100,
        choices=ISO_TOPIC_CHOICES,
        blank=True,
        null=True,
        )

    picto = models.ImageField(
        verbose_name="Pictogramme",
        upload_to='logos/',
        blank=True,
        null=True,
        )

    def __str__(self):
        return self.name

    def sync_ckan(self):
        if self.pk:
            CkanHandler.update_group(self)
        else:
            CkanHandler.add_group(self)

    def clean(self):
        self.slug = slugify(self.name)
        try:
            self.sync_ckan()
        except Exception as e:
            raise ValidationError(e.__str__())


@receiver(pre_delete, sender=Category)
def pre_delete_category(sender, instance, **kwargs):
    if CkanHandler.is_group_exists(str(instance.ckan_id)):
        CkanHandler.del_group(str(instance.ckan_id))


class DataType(models.Model):

    class Meta(object):
        verbose_name = "Type de donnée"
        verbose_name_plural = "Types de données"

    slug = models.SlugField(
        verbose_name="Slug",
        max_length=100,
        unique=True,
        db_index=True,
        blank=True,
        )

    name = models.CharField(
        verbose_name="Nom",
        max_length=100,
        )

    description = models.CharField(
        verbose_name='Description',
        max_length=1024,
        )

    def __str__(self):
        return self.name


class Granularity(models.Model):

    class Meta(object):
        verbose_name = "Granularité de la couverture territoriale"
        verbose_name_plural = "Granularités des couvertures territoriales"

    slug = models.SlugField(
        verbose_name="Slug",
        max_length=100,
        unique=True,
        db_index=True,
        blank=True,
        primary_key=True,
        )

    name = models.TextField(
        verbose_name="Nom",
        )

    order = models.IntegerField(
        unique=True,
        blank=True,
        null=True,
        )

    def __str__(self):
        return self.name


class License(models.Model):

    # MODELE LIE AUX LICENCES CKAN. MODIFIER EGALEMENT DANS LA CONF CKAN
    # QUAND DES ELEMENTS SONT AJOUTES, il faut mettre à jour
    # le fichier /etc/ckan/default/licenses.json

    class Meta(object):
        verbose_name = "Licence"
        verbose_name_plural = "Licences"

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

    def __str__(self):
        return self.title

    @property
    def ckan_id(self):
        return self.slug


class Support(models.Model):

    class Meta(object):
        verbose_name = "Support technique"
        verbose_name_plural = "Supports techniques"

    name = models.CharField(
        verbose_name="Nom",
        max_length=100,
        )

    description = models.CharField(
        verbose_name="Description",
        max_length=1024,
        )

    slug = models.SlugField(
        verbose_name="Label court",
        max_length=100,
        unique=True,
        db_index=True,
        blank=True,
        )

    email = models.EmailField(
        verbose_name="Adresse e-mail",
        blank=True,
        null=True,
        )

    def __str__(self):
        return self.name


class SupportedCrs(models.Model):

    class Meta(object):
        verbose_name = "CRS supporté par l'application"
        verbose_name_plural = "CRS supportés par l'application"

    auth_name = models.CharField(
        verbose_name="Authority Name",
        max_length=100,
        default='EPSG',
        )

    auth_code = models.CharField(
        verbose_name="Authority Code",
        max_length=100,
        )

    description = models.TextField(
        verbose_name="Description",
        blank=True,
        null=True,
        )

    regex = models.TextField(
        verbose_name="Expression régulière",
        blank=True,
        null=True,
        )

    @property
    def authority(self):
        return '{}:{}'.format(self.auth_name, self.auth_code)

    def __str__(self):
        return '{}:{} ({})'.format(
            self.auth_name, self.auth_code, self.description)


class Task(models.Model):

    class Meta(object):
        verbose_name = "Tâche de synchronisation"
        verbose_name_plural = "Tâches de synchronisation"

    action = models.TextField(
        verbose_name="Action",
        blank=True,
        null=True,
        )

    extras = JSONField(
        verbose_name="Extras",
        blank=True,
        null=True,
        )

    STATE_CHOICES = (
        ('succesful', "Tâche terminée avec succés"),
        ('failed', "Echec de la tâche"),
        ('running', "Tâche en cours de traitement"))

    state = models.CharField(
        verbose_name="État",
        max_length=20,
        choices=STATE_CHOICES,
        default='running',
        )

    starting = models.DateTimeField(
        verbose_name="Début du traitement",
        auto_now_add=True,
        )

    end = models.DateTimeField(
        verbose_name="Fin du traitement",
        blank=True,
        null=True,
        )


__all__ = [
    AccountActions,
    AsyncExtractorTask,
    BaseMaps,
    Category,
    Commune,
    Dataset,
    DataType,
    ExtractorSupportedFormat,
    Granularity,
    Jurisdiction,
    JurisdictionCommune,
    Layer,
    License,
    LiaisonsContributeurs,
    LiaisonsReferents,
    Mail,
    Organisation,
    OrganisationType,
    Profile,
    RemoteCkan,
    RemoteCkanDataset,
    Resource,
    ResourceFormats,
    Support,
    SupportedCrs,
    Task,
    ]
