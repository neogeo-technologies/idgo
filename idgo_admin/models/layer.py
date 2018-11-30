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
from django.contrib.postgres.fields import ArrayField
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.datagis import drop_table
from idgo_admin.mra_client import MraBaseError
from idgo_admin.mra_client import MRAHandler
import itertools
import json
import os
import re
import uuid


MRA = settings.MRA
OWS_URL_PATTERN = settings.OWS_URL_PATTERN
CKAN_STORAGE_PATH = settings.CKAN_STORAGE_PATH


def get_all_users_for_organizations(list_id):
    Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


class LayerRasterManager(models.Manager):

    def create(self, **kwargs):
        save_opts = kwargs.pop('save_opts', {})
        kwargs['type'] = 'raster'
        obj = self.model(**kwargs)
        self._for_write = True
        obj.save(
            force_insert=True, using=self.db, **save_opts)
        return obj


class LayerVectorManager(models.Manager):

    def create(self, **kwargs):
        save_opts = kwargs.pop('save_opts', {})
        kwargs['type'] = 'vector'
        obj = self.model(**kwargs)
        self._for_write = True
        obj.save(
            force_insert=True, using=self.db, **save_opts)
        return obj


class Layer(models.Model):

    name = models.SlugField(
        verbose_name='Nom de la couche', primary_key=True, editable=False)

    resource = models.ForeignKey(
        to='Resource', verbose_name='Ressource',
        on_delete=models.CASCADE, blank=True, null=True)

    # data_source = models.TextField(
    #     verbose_name='Chaîne de connexion à la source de données',
    #     blank=True, null=True)

    TYPE_CHOICES = (
        ('raster', 'raster'),
        ('vector', 'vector'))

    type = models.CharField(
        'type', max_length=6, blank=True, null=True, choices=TYPE_CHOICES)

    attached_ckan_resources = ArrayField(
        models.UUIDField(), size=None, blank=True, null=True)

    objects = models.Manager()
    vector = LayerVectorManager()
    raster = LayerRasterManager()

    class Meta(object):
        verbose_name = 'Couche de données'

    def __str__(self):
        # On retourne le __str__() de la ressource.
        return self.resource.__str__()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            l = MRAHandler.get_layer(self.name)
        except MraBaseError:
            return

        if self.type == 'vector':
            try:
                ft = MRAHandler.get_featuretype(
                    self.resource.dataset.organisation.ckan_slug, 'public', self.name)
            except MraBaseError:
                return

            if not l or not ft:
                # raise MRANotFoundError
                return

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

        elif self.type == 'raster':
            try:
                c = MRAHandler.get_coverage(
                    self.resource.dataset.organisation.ckan_slug, self.name, self.name)
            except MraBaseError:
                return

            if not l or not c:
                # raise MRANotFoundError
                return

            ll = c['coverage']['latLonBoundingBox']
            bbox = [[ll['miny'], ll['minx']], [ll['maxy'], ll['maxx']]]
            attributes = []
            default_style_name = None
            styles = []

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

    def save_raster(self, *args, **kwargs):

        organisation = self.resource.dataset.organisation
        ws_name = organisation.ckan_slug
        cs_name = self.name

        if self.pk:
            try:
                previous = Layer.objects.get(pk=self.pk)
            except Layer.DoesNotExist:
                pass
            else:
                # On vérifie si l'organisation du jeu de données a changée,
                # auquel cas il est nécessaire de supprimer les objets MRA
                # afin de les recréer dans le bon workspace (c-à-d Mapfile).
                previous_layer = MRAHandler.get_layer(self.name)
                regex = '/workspaces/(?P<ws_name>[a-z_\-]+)/coveragestores/'

                matched = re.search(regex, previous_layer['resource']['href'])
                if matched:
                    previous_ws_name = matched.group('ws_name')
                    if not ws_name == previous_ws_name:
                        MRAHandler.del_layer(self.name)
                        MRAHandler.del_coverage(
                            previous_ws_name, cs_name, self.name)

        MRAHandler.get_or_create_workspace(organisation)
        MRAHandler.get_or_create_coveragestore(ws_name, cs_name, filename=self.filename)
        MRAHandler.get_or_create_coverage(
            ws_name, cs_name, self.name, enabled=True,
            title=self.resource.name, abstract=self.resource.description)

    def save_vector(self, *args, **kwargs):

        organisation = self.resource.dataset.organisation
        ws_name = organisation.ckan_slug
        ds_name = 'public'

        if self.pk:
            try:
                previous = Layer.objects.get(pk=self.pk)
            except Layer.DoesNotExist:
                pass
            else:
                # On vérifie si l'organisation du jeu de données a changée,
                # auquel cas il est nécessaire de supprimer les objets MRA
                # afin de les recréer dans le bon workspace (c-à-d Mapfile).
                previous_layer = MRAHandler.get_layer(self.name)
                regex = '/workspaces/(?P<ws_name>[a-z_\-]+)/datastores/'

                matched = re.search(regex, previous_layer['resource']['href'])
                if matched:
                    previous_ws_name = matched.group('ws_name')
                    if not ws_name == previous_ws_name:
                        MRAHandler.del_layer(self.name)
                        MRAHandler.del_featuretype(
                            previous_ws_name, ds_name, self.name)

        MRAHandler.get_or_create_workspace(organisation)
        MRAHandler.get_or_create_datastore(ws_name, ds_name)
        MRAHandler.get_or_create_featuretype(
            ws_name, ds_name, self.name, enabled=True,
            title=self.resource.name, abstract=self.resource.description)

    def save(self, *args, **kwargs):

        SupportedCrs = apps.get_model(app_label='idgo_admin', model_name='SupportedCrs')

        editor = kwargs.pop('editor', None)

        if self.type == 'vector':
            self.save_vector()
        elif self.type == 'raster':
            self.save_raster()

        super().save(*args, **kwargs)

        self.handle_enable_ows_status()
        self.handle_layergroup()

        # Synchronisation CKAN
        # ====================

        # Si l'utilisateur courant n'est pas l'éditeur d'un jeu
        # de données existant mais administrateur ou un référent technique,
        # alors l'admin Ckan édite le jeu de données.
        if editor == self.resource.dataset.editor:
            ckan_user = ckan_me(ckan.get_user(editor.username)['apikey'])
        else:
            ckan_user = ckan_me(ckan.apikey)

        if self.resource.ogc_services:
            # TODO: Factoriser

            # (0) Aucune restriction
            if self.resource.restricted_level == '0':
                restricted = json.dumps({'level': 'public'})
            # (1) Uniquement pour un utilisateur connecté
            elif self.resource.restricted_level == '1':
                restricted = json.dumps({'level': 'registered'})
            # (2) Seulement les utilisateurs indiquées
            elif self.resource.restricted_level == '2':
                restricted = json.dumps({
                    'allowed_users': ','.join(
                        self.resource.profiles_allowed.exists() and [
                            profile.user.username for profile
                            in self.resource.profiles_allowed.all()] or []),
                    'level': 'only_allowed_users'})
            # (3) Les utilisateurs de cette organisation
            elif self.resource.restricted_level == '3':
                restricted = json.dumps({
                    'allowed_users': ','.join(
                        get_all_users_for_organizations(
                            self.resource.organisations_allowed.all())),
                    'level': 'only_allowed_users'})
            # (3) Les utilisateurs des organisations indiquées
            elif self.resource.restricted_level == '4':
                restricted = json.dumps({
                    'allowed_users': ','.join(
                        get_all_users_for_organizations(
                            self.resource.organisations_allowed.all())),
                    'level': 'only_allowed_users'})

            organisation = self.resource.dataset.organisation

            getlegendgraphic = (
                '{}?&version=1.1.1&service=WMS&request=GetLegendGraphic'
                '&layer={}&format=image/png').format(
                    OWS_URL_PATTERN.format(
                        organisation=organisation.ckan_slug
                        ).replace('?', ''), self.name)

            url = '{0}#{1}'.format(
                OWS_URL_PATTERN.format(
                    organisation=organisation.ckan_slug), self.name)

            ckan_params = {
                'id': self.name,
                'name': '{} (OGC:WMS)'.format(self.resource.name),
                'description': self.resource.description,
                'getlegendgraphic': getlegendgraphic,
                'data_type': 'service',
                'extracting_service': str(self.resource.extractable),  # I <3 CKAN
                'crs': SupportedCrs.objects.get(
                    auth_name='EPSG', auth_code='4171').description,
                'lang': self.resource.lang,
                'format': 'WMS',
                'restricted': restricted,
                'url': url,
                'view_type': 'geo_view'}

            ckan_package = ckan_user.get_package(str(self.resource.dataset.ckan_id))
            ckan_user.publish_resource(ckan_package, **ckan_params)

            # Ugly time...
            if self.attached_ckan_resources:
                for id in self.attached_ckan_resources:
                    ckan_user.delete_resource(id.__str__())

            attached_ckan_resources = []
            if self.type == 'vector':
                new_ckan_id = uuid.uuid4()
                attached_ckan_resources.append(new_ckan_id)
                ckan_params['id'] = new_ckan_id.__str__()
                ckan_params['name'] = '{} (OGC:WFS)'.format(self.resource.name)
                ckan_params['format'] = 'WFS'
                ckan_params['data_type'] = 'service'
                ckan_params['view_type'] = None
                ckan_params['url'] = OWS_URL_PATTERN.format(organisation=organisation.ckan_slug)
                ckan_user.publish_resource(ckan_package, **ckan_params)

                if self.resource.format_type.extension.lower() in ('json', 'geojson'):
                    if self.resource.crs:
                        crs = self.resource.crs.description
                        crsname = self.resource.crs.description
                    else:
                        crs_obj = SupportedCrs.objects.get(
                            auth_name='EPSG', auth_code='2154')
                        crs = crs_obj.description
                        crsname = crs_obj.authority
                    new_ckan_id = uuid.uuid4()
                    attached_ckan_resources.append(new_ckan_id)
                    ckan_params['id'] = new_ckan_id.__str__()
                    ckan_params['name'] = self.resource.name
                    ckan_params['extracting_service'] = str(False)  # I <3 CKAN
                    ckan_params['format'] = 'ZIP'
                    ckan_params['data_type'] = 'service'
                    ckan_params['view_type'] = None
                    ckan_params['crs'] = crs
                    ckan_params['url'] = '{}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAME={}&outputFormat=shapezip&CRSNAME={}'.format(
                        OWS_URL_PATTERN.format(organisation=organisation.ckan_slug), self.name, crsname)
                    ckan_user.publish_resource(ckan_package, **ckan_params)

                elif self.resource.format_type.extension.lower() in ('zip', 'tar'):
                    new_ckan_id = uuid.uuid4()
                    attached_ckan_resources.append(new_ckan_id)
                    ckan_params['id'] = new_ckan_id.__str__()
                    ckan_params['name'] = self.resource.name
                    ckan_params['extracting_service'] = str(False)  # I <3 CKAN
                    ckan_params['format'] = 'GEOJSON'
                    ckan_params['data_type'] = 'service'
                    ckan_params['view_type'] = 'geo_view'
                    ckan_params['crs'] = SupportedCrs.objects.get(
                        auth_name='EPSG', auth_code='4326').description,
                    ckan_params['url'] = '{}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAME={}&outputFormat=geojson'.format(
                        OWS_URL_PATTERN.format(organisation=organisation.ckan_slug), self.name)
                    ckan_user.publish_resource(ckan_package, **ckan_params)

            elif self.type == 'raster':
                # TODO?
                pass

            # Puis
            if attached_ckan_resources:
                self.attached_ckan_resources = attached_ckan_resources
                kwargs['force_insert'] = False
                super().save(*args, **kwargs)

        else:
            # Sinon on force la suppression de la ressource CKAN
            ckan_user.delete_resource(self.name)

        ckan_user.close()

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

    @property
    def filename(self):
        if self.type == 'vector':
            # Peut-être quelque chose à retourner ici ?
            return None
        if self.type == 'raster':
            x = str(self.resource.ckan_id)
            filename = os.path.join(
                CKAN_STORAGE_PATH, x[:3], x[3:6], x[6:])
            return filename

    def handle_enable_ows_status(self):
        ws_name = self.resource.dataset.organisation.ckan_slug
        if self.resource.ogc_services:
            MRAHandler.enable_layer(ws_name, self.name)
            # TODO: Comment on gère les ressources CKAN service ???
        else:
            MRAHandler.disable_layer(ws_name, self.name)
            # TODO: Comment on gère les ressources CKAN service ???

    def handle_layergroup(self):
        dataset = self.resource.dataset
        layers = list(itertools.chain.from_iterable([
            qs for qs in [
                resource.get_layers() for resource
                in dataset.get_resources()]]))
        # TODO remplacer par `layers = dataset.get_layers()`

        MRAHandler.create_or_update_layergroup(
            dataset.organisation.ckan_slug, {
                'name': dataset.ckan_slug,
                'title': dataset.name,
                'abstract': dataset.description,
                'layers': [layer.name for layer in layers]})


@receiver(pre_delete, sender=Layer)
def delete_ows_layer(sender, instance, **kwargs):
    ft_name = instance.name
    ds_name = 'public'
    ws_name = instance.resource.dataset.organisation.ckan_slug

    ckan_user = ckan_me(
        ckan.get_user(instance.resource.dataset.editor.username)['apikey'])

    # On supprime la ressource CKAN
    ckan_user.delete_resource(ft_name)
    # Puis on supprime les ressources CKAN annexées à la couche
    if instance.attached_ckan_resources:
        for id in instance.attached_ckan_resources:
            ckan_user.delete_resource(id.__str__())
        ckan_user.close()

    # On supprime les objets MRA
    try:
        MRAHandler.del_layer(ft_name)
        MRAHandler.del_featuretype(ws_name, ds_name, ft_name)
    except:
        pass

    # On supprime la table de données postgis
    drop_table(ft_name)
