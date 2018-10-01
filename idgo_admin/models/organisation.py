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
from django.contrib.gis.db import models
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.mra_client import MRAHandler
import uuid


OWS_URL_PATTERN = settings.OWS_URL_PATTERN


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
    Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
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

    phone = models.CharField(
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

    geonet_id = models.UUIDField(
        verbose_name='UUID de la métadonnées', unique=True,
        db_index=True, blank=True, null=True)

    class Meta(object):
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def full_address(self):
        return '{} - {} {}'.format(self.address, self.postcode, self.city)

    @property
    def ows_url(self):
        if MRAHandler.is_workspace_exists(self.ckan_slug):
            return OWS_URL_PATTERN.format(organisation=self.ckan_slug)
        # else: return None

    def get_datasets(self, **kwargs):
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        return Dataset.objects.filter(organisation=self, **kwargs)


# Triggers


@receiver(pre_save, sender=Organisation)
def pre_save_organisation(sender, instance, **kwargs):
    instance.ckan_slug = slugify(instance.name)


@receiver(post_save, sender=Organisation)
def post_save_organisation(sender, instance, **kwargs):
    # Mettre à jour en cascade les profiles (utilisateurs)
    Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
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
