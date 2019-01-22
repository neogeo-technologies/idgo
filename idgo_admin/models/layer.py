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
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.ckan_module import CkanUserHandler
from idgo_admin.datagis import drop_table
from idgo_admin import logger
from idgo_admin.managers import RasterLayerManager
from idgo_admin.managers import VectorLayerManager
from idgo_admin.models import get_super_editor
from idgo_admin.mra_client import MraBaseError
from idgo_admin.mra_client import MRAHandler
import itertools
import json
import os
import re
import uuid


MRA = settings.MRA
OWS_URL_PATTERN = settings.OWS_URL_PATTERN
MAPSERV_STORAGE_PATH = settings.MAPSERV_STORAGE_PATH


def get_all_users_for_organizations(list_id):
    Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


class Layer(models.Model):

    # Managers
    # ========

    objects = models.Manager()

    vector = VectorLayerManager()
    raster = RasterLayerManager()

    # Champs atributaires
    # ===================

    name = models.SlugField(
        verbose_name='Nom de la couche', primary_key=True,
        editable=False, max_length=100)

    resource = models.ForeignKey(
        to='Resource', verbose_name='Ressource',
        on_delete=models.CASCADE, blank=True, null=True)

    TYPE_CHOICES = (
        ('raster', 'raster'),
        ('vector', 'vector'))

    type = models.CharField(
        verbose_name='type', max_length=6,
        blank=True, null=True, choices=TYPE_CHOICES)

    attached_ckan_resources = ArrayField(
        models.UUIDField(), size=None, blank=True, null=True)

    bbox = models.PolygonField(
        verbose_name='Rectangle englobant', blank=True, null=True, srid=4171)

    class Meta(object):
        verbose_name = 'Couche de données'

    def __str__(self):
        return self.resource.__str__()

    # Propriétés
    # ==========

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
                MAPSERV_STORAGE_PATH, x[:3], x[3:6], x[6:])
            return filename

    # Méthodes héritées
    # =================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        organisation = self.resource.dataset.organisation
        ws_name = organisation.ckan_slug

        try:
            l = MRAHandler.get_layer(self.name)
        except MraBaseError:
            return

        # Récupération des informations de couche vecteur
        # ===============================================

        if self.type == 'vector':
            try:
                ft = MRAHandler.get_featuretype(ws_name, 'public', self.name)
            except MraBaseError:
                return
            if not l or not ft:
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

        # Récupération des informations de couche raster
        # ==============================================

        elif self.type == 'raster':
            try:
                c = MRAHandler.get_coverage(ws_name, self.name, self.name)
            except MraBaseError:
                return
            if not l or not c:
                return

            ll = c['coverage']['latLonBoundingBox']
            bbox = [[ll['miny'], ll['minx']], [ll['maxy'], ll['maxx']]]
            attributes = []
            default_style_name = None
            styles = []

        # Puis..
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

        # Synchronisation avec le service OGC en fonction du type de données
        if self.type == 'vector':
            self.save_vector_layer()

        elif self.type == 'raster':
            self.save_raster_layer()

        # Puis sauvegarde
        super().save(*args, **kwargs)

        self.handle_enable_ows_status()
        self.handle_layergroup()

        if self.resource.ogc_services:
            attached_ckan_resources = self.synchronize()
            if attached_ckan_resources:
                self.attached_ckan_resources = attached_ckan_resources
                super().save(update_fields=['attached_ckan_resources'])
        else:
            CkanHandler.delete_resource(self.name)

    def delete(self, *args, current_user=None, **kwargs):
        user = current_user or get_super_editor()

        # On supprime la ressource CKAN
        if hasattr(user, 'profile'):
            username = user.username
            apikey = CkanHandler.get_user(username)['apikey']
            with CkanUserHandler(apikey=apikey) as ckan_user:
                ckan_user.delete_resource(self.name)
        else:
            CkanHandler.delete_resource(self.name)

        # Ainsi que toutes celles qui y sont attachées
        if self.attached_ckan_resources:
            for id in self.attached_ckan_resources:
                CkanHandler.delete_resource(id.__str__())

        # On supprime les ressources MRA
        try:
            MRAHandler.del_layer(self.name)
            ws_name = self.resource.dataset.organisation.ckan_slug
            if self.type == 'vector':
                MRAHandler.del_featuretype(ws_name, 'public', self.name)
            if self.type == 'raster':
                MRAHandler.del_coverage(ws_name, self.name, self.name)
                # MRAHandler.del_coveragestore(ws_name, self.name)
        except Exception as e:
            logger.error(e)
            pass

        # On supprime la table de données PostGIS
        try:
            drop_table(self.name)
        except Exception as e:
            logger.error(e)
            pass

        # Puis on supprime l'instance
        super().delete(*args, **kwargs)

    # Autres méthodes
    # ===============

    def save_raster_layer(self, *args, **kwargs):
        """Synchronizer la couche de données matricielle avec le service OGC via MRA."""
        organisation = self.resource.dataset.organisation
        ws_name = organisation.ckan_slug
        cs_name = self.name

        if self.pk:
            try:
                Layer.objects.get(pk=self.pk)
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

    def save_vector_layer(self, *args, **kwargs):
        """Synchronizer la couche de données vectorielle avec le service OGC via MRA."""
        organisation = self.resource.dataset.organisation
        ws_name = organisation.ckan_slug
        ds_name = 'public'

        if self.pk:
            try:
                Layer.objects.get(pk=self.pk)
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

    def synchronize(self, with_user=None):
        """Synchronizer le jeu de données avec l'instance de CKAN."""
        # 'with_user' n'est pas utiliser dans ce contexte

        # Définition des propriétés de la « ressource »
        # =============================================

        id = self.name
        name = '{name} (OGC:WMS)'.format(name=self.resource.name)
        description = self.resource.description
        organisation = self.resource.dataset.organisation

        base_url = OWS_URL_PATTERN.format(organisation=organisation.ckan_slug).replace('?', '')

        getlegendgraphic = (
            '{base_url}?&version=1.1.1&service=WMS&request=GetLegendGraphic&layer={layer}&format=image/png'
            ).format(base_url=base_url, layer=id)

        url = (
            '{base_url}#{layer}'
            ).format(base_url=base_url, layer=id)

        # Définition de l'extra 'restricted'
        if self.resource.restricted_level == '0':
            # Aucune restriction :
            restricted = json.dumps({'level': 'public'})
        elif self.resource.restricted_level == '1':
            # Uniquement pour un utilisateur connecté :
            restricted = json.dumps({'level': 'registered'})
        elif self.resource.restricted_level == '2':
            # Seulement les utilisateurs indiquées :
            restricted = json.dumps({
                'allowed_users': ','.join(
                    self.resource.profiles_allowed.exists() and [
                        profile.user.username for profile
                        in self.resource.profiles_allowed.all()] or []),
                'level': 'only_allowed_users'})
        elif self.resource.restricted_level == '3':
            # Les utilisateurs de cette organisation :
            restricted = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organizations(
                        self.resource.organisations_allowed.all())),
                'level': 'only_allowed_users'})
        elif self.resource.restricted_level == '4':
            # Les utilisateurs des organisations indiquées :
            restricted = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organizations(
                        self.resource.organisations_allowed.all())),
                'level': 'only_allowed_users'})

        SupportedCrs = apps.get_model(app_label='idgo_admin', model_name='SupportedCrs')
        crs = SupportedCrs.objects.get(auth_name='EPSG', auth_code='4171').description

        data = {
            'crs': crs,
            'data_type': 'service',
            'description': description,
            'extracting_service': str(self.resource.extractable),  # I <3 CKAN
            'format': 'WMS',
            'getlegendgraphic': getlegendgraphic,
            'id': id,
            'lang': self.resource.lang,
            'name': name,
            'resource_type': 'api',
            'restricted': restricted,
            'url': url,
            'view_type': 'geo_view'}

        ckan_package = CkanHandler.get_package(str(self.resource.dataset.ckan_id))
        CkanHandler.publish_resource(ckan_package, **data)

        if self.attached_ckan_resources:
            for id in self.attached_ckan_resources:
                CkanHandler.delete_resource(id.__str__())

        attached_ckan_resources = []
        if self.type == 'vector':
            new_ckan_id = uuid.uuid4()
            attached_ckan_resources.append(new_ckan_id)

            data['data_type'] = 'service'
            data['format'] = 'WFS'
            data['id'] = new_ckan_id.__str__()
            data['name'] = '{name} (OGC:WFS)'.format(name=self.resource.name)
            data['url'] = base_url
            data['view_type'] = None

            CkanHandler.publish_resource(ckan_package, **data)

            if self.resource.format_type.extension.lower() in ('json', 'geojson'):

                # Publication d'une ressource service: ShapeZip
                # =============================================

                new_ckan_id = uuid.uuid4()
                attached_ckan_resources.append(new_ckan_id)

                if self.resource.crs:
                    crs = self.resource.crs.description
                    crsname = self.resource.crs.description
                else:
                    crs_obj = SupportedCrs.objects.get(auth_name='EPSG', auth_code='2154')
                    crs = crs_obj.description
                    crsname = crs_obj.authority

                data['crs'] = crs
                data['data_type'] = 'service'
                data['extracting_service'] = str(False)
                data['format'] = 'SHP'
                data['id'] = str(new_ckan_id)
                data['name'] = self.resource.name
                data['url'] = (
                    '{base_url}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAME={typename}&outputFormat=shapezip&CRSNAME={crsname}'
                    ).format(base_url=base_url, typename=id, crsname=crsname)
                data['view_type'] = None

                CkanHandler.publish_resource(ckan_package, **data)

            elif self.resource.format_type.extension.lower() in ('zip', 'tar'):

                # Publication d'une ressource service: GeoJSON
                # ============================================

                new_ckan_id = uuid.uuid4()
                attached_ckan_resources.append(new_ckan_id)

                crs_obj = SupportedCrs.objects.get(auth_name='EPSG', auth_code='2154')
                crs = crs_obj.description

                data['crs'] = crs
                data['data_type'] = 'service'
                data['extracting_service'] = str(False)
                data['format'] = 'GEOJSON'
                data['id'] = str(new_ckan_id)
                data['name'] = self.resource.name
                data['url'] = (
                    '{base_url}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAME={}&outputFormat=geojson'
                    ).format(base_url=base_url, typename=id)
                data['view_type'] = 'geo_view'

                CkanHandler.publish_resource(ckan_package, **data)

        elif self.type == 'raster':
            # TODO?
            pass

        return attached_ckan_resources

    def handle_enable_ows_status(self):
        """Gérer le statut d'activation de la couche de données SIG."""
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


# Signaux
# =======


@receiver(post_save, sender=Layer)
def logging_after_save(sender, instance, **kwargs):
    action = kwargs.get('created', False) and 'created' or 'updated'
    logger.info('Layer "{pk}" has been {action}'.format(pk=instance.pk, action=action))


@receiver(post_delete, sender=Layer)
def logging_after_delete(sender, instance, **kwargs):
    logger.info('Layer "{pk}" has been deleted'.format(pk=instance.pk))
