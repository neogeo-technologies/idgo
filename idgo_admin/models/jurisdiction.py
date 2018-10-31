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
from django.contrib.gis.db import models


class Jurisdiction(models.Model):

    code = models.CharField(
        verbose_name='Code INSEE', max_length=10, primary_key=True)

    name = models.CharField(verbose_name='Nom', max_length=100)

    communes = models.ManyToManyField(
        to='Commune', through='JurisdictionCommune',
        verbose_name='Communes',
        related_name='jurisdiction_communes')

    objects = models.GeoManager()

    class Meta(object):
        verbose_name = 'Territoire de compétence'
        verbose_name_plural = 'Territoires de compétence'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        old = kwargs.pop('old', None)
        super().save(*args, **kwargs)

        if old and old != self.code:
            instance_to_del = Jurisdiction.objects.get(code=old)
            JurisdictionCommune.objects.filter(jurisdiction=instance_to_del).delete()
            Organisation = apps.get_model(app_label='idgo_admin', model_name='Organisation')
            Organisation.objects.filter(jurisdiction=instance_to_del).update(jurisdiction=self)
            instance_to_del.delete()

    @property
    def organisations(self):
        Organisation = apps.get_model(app_label='idgo_admin', model_name='Organisation')
        return Organisation.objects.filter(jurisdiction=self)


class Commune(models.Model):

    code = models.CharField(
        verbose_name='Code INSEE', max_length=5, primary_key=True)

    name = models.CharField(verbose_name='Nom', max_length=100)

    geom = models.MultiPolygonField(
        verbose_name='Geometrie', srid=4326, blank=True, null=True)

    objects = models.GeoManager()

    class Meta(object):
        verbose_name = 'Commune'
        verbose_name_plural = 'Communes'
        ordering = ['name']

    def __str__(self):
        return '{} ({})'.format(self.name, self.code)


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
        return '{}: {}'.format(self.jurisdiction, self.commune)
