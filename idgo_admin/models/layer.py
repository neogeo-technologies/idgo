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


from django.contrib.gis.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.datagis import drop_table
from idgo_admin.mra_client import MRAHandler
from idgo_admin.mra_client import MRANotFoundError


class Layer(models.Model):

    class Meta(object):
        verbose_name = 'Couche de données'

    def __str__(self):
        return self.name

    name = models.SlugField(
        verbose_name='Nom de la couche', primary_key=True, editable=False)

    resource = models.ForeignKey(
        to='Resource', verbose_name='Ressource',
        on_delete=models.CASCADE, blank=True, null=True)

    # data_source = models.TextField(
    #     verbose_name='Chaîne de connexion à la source de données',
    #     blank=True, null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            l = MRAHandler.get_layer(self.name)
        except MRANotFoundError:
            return

        ft = MRAHandler.get_featuretype(
            self.resource.dataset.organisation.ckan_slug, 'public', self.name)
        if not l or not ft:
            raise MRANotFoundError

        ll = ft['featureType']['latLonBoundingBox']
        bbox = [[ll['miny'], ll['minx']], [ll['maxy'], ll['maxx']]]
        attributes = [item['name'] for item in ft['featureType']['attributes']]

        default_style_name = l['defaultStyle']['name']

        styles = [{
            'name': 'default',
            'text': 'Style par défaut',
            'url': l['defaultStyle']['href'].replace('json', 'sld'),
            'sld': MRAHandler.get_style(l['defaultStyle']['name'])}]

        if l.get('styles'):
            for style in l.get('styles')['style']:
                styles.append({
                    'name': style['name'],
                    'text': style['name'],
                    'url': style['href'].replace('json', 'sld'),
                    'sld': MRAHandler.get_style(style['name'])})

        self.mra_info = {
            'name': l['name'],
            'title': l['title'],
            'type': l['type'],
            'enabled': l['enabled'],
            'abstract': l['abstract'],
            'bbox': bbox,
            'attributes': attributes,
            'styles': {
                'default': default_style_name,
                'styles': styles}}

    def save(self, *args, **kwargs):

        organisation = self.resource.dataset.organisation
        ws_name = organisation.ckan_slug
        ds_name = 'public'

        MRAHandler.get_or_create_workspace(organisation)
        MRAHandler.get_or_create_datastore(ws_name, ds_name)
        MRAHandler.get_or_create_featuretype(ws_name, ds_name, self.name)

        super().save(*args, **kwargs)

        self.handle_enable_ows_status()

    @property
    def layername(self):
        return self.mra_info['name']

    @property
    def geometry_type(self):
        return {
            'POLYGON': 'Polygone',
            'POINT': 'Point',
            'LINESTRING': 'Ligne',
            'RASTER': 'Raster'}.get(self.mra_info['type'])

    def handle_enable_ows_status(self):
        ws_name = self.resource.dataset.organisation.ckan_slug
        if self.resource.ogc_services:
            MRAHandler.enable_layer(ws_name, self.name)
        else:
            MRAHandler.disable_layer(ws_name, self.name)

    @property
    def is_enabled(self):
        return self.mra_info['enabled']

    @property
    def title(self):
        return self.mra_info['title']

    @property
    def abstract(self):
        return self.mra_info['abstract']

    @property
    def styles(self):
        return self.mra_info['styles']['styles']

    @property
    def id(self):
        return self.name


@receiver(pre_delete, sender=Layer)
def delete_ows_layer(sender, instance, **kwargs):
    ft_name = instance.name
    ds_name = 'public'
    ws_name = instance.resource.dataset.organisation.ckan_slug

    # On supprime la ressource CKAN
    ckan_user = ckan_me(
        ckan.get_user(instance.resource.dataset.editor.username)['apikey'])
    ckan_user.delete_resource(ft_name)
    ckan_user.close()

    # On supprime les objets MRA
    MRAHandler.del_layer(ft_name)
    MRAHandler.del_featuretype(ws_name, ds_name, ft_name)

    # On supprime la table de données postgis
    drop_table(ft_name)
