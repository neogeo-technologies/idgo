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

    @property
    def mra_info(self):
        l = MRAHandler.get_layer(self.name)
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

        return {
            'name': l['name'],
            'title': l['title'],
            'type': l['type'],
            'enabled': l['enabled'],
            'bbox': bbox,
            'attributes': attributes,
            'styles': {
                'default': default_style_name,
                'styles': styles}}

    @property
    def id(self):
        return self.name
