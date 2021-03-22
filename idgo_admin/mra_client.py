# Copyright (c) 2017-2021 Neogeo-Technologies.
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


import ast
from functools import reduce
from functools import wraps
import inspect
import logging
from lxml import etree
from lxml import objectify
import os
from urllib.parse import urljoin

from requests import request

from django.apps import apps

from idgo_admin.exceptions import GenericException
from idgo_admin.utils import Singleton
from idgo_admin.utils import kill_all_special_characters

from idgo_admin import IDGO_GEOGRAPHIC_LAYER_MRA_URL
from idgo_admin import IDGO_GEOGRAPHIC_LAYER_MRA_USERNAME
from idgo_admin import IDGO_GEOGRAPHIC_LAYER_MRA_PASSWORD
from idgo_admin import IDGO_GEOGRAPHIC_LAYER_MRA_DB_TYPE
from idgo_admin import IDGO_GEOGRAPHIC_LAYER_MRA_DB_PORT
from idgo_admin import IDGO_GEOGRAPHIC_LAYER_MRA_DB_HOST
from idgo_admin import IDGO_GEOGRAPHIC_LAYER_MRA_DB_NAME
from idgo_admin import IDGO_GEOGRAPHIC_LAYER_MRA_DB_USERNAME
from idgo_admin import IDGO_GEOGRAPHIC_LAYER_MRA_DB_PASSWORD


logger = logging.getLogger('idgo_admin')


def preprocessing_sld(data):
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(data, parser)
    for elem in root.getiterator():
        if not hasattr(elem.tag, 'find'):
            continue
        i = elem.tag.find('}')
        if i >= 0:
            elem.tag = elem.tag[i + 1:]
        if elem.tag == 'SvgParameter':
            elem.tag = 'CssParameter'
    objectify.deannotate(root, cleanup_namespaces=True)
    return etree.tostring(root, pretty_print=True)


class MraBaseError(GenericException):
    """MraBaseError"""


class MRASyncingError(MraBaseError):
    def __init__(self, *args, **kwargs):
        for item in self.args:
            try:
                m = ast.literal_eval(item)
            except Exception:
                continue
            if isinstance(m, dict):
                kwargs.update(**m)
            # else: TODO
        super().__init__(*args, **kwargs)


class MRANotFoundError(MraBaseError):

    message = "Erreur MRA : Not Found"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class MRAConflictError(MraBaseError):

    message = "Erreur MRA : Conflict"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class MRATimeoutError(MraBaseError):

    message = "Erreur MRA : Time out"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class MRACriticalError(MraBaseError):

    message = "Erreur MRA : Le jeu de données provoque une erreur critique. Veuillez contacter l'administrateur du site."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class MRAExceptionsHandler(object):

    def __init__(self, ignore=None):
        self.ignore = ignore or []

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):

            root_dir = os.path.dirname(os.path.abspath(__file__))
            info = inspect.getframeinfo(inspect.stack()[1][0])
            logger.debug(
                'Run {} (called by file "{}", line {}, in {})'.format(
                    f.__qualname__,
                    info.filename.replace(root_dir, '.'),
                    info.lineno,
                    info.function))

            try:
                return f(*args, **kwargs)
            except Exception as e:
                if self.is_ignored(e):
                    return f(*args, **kwargs)
                if e.__class__.__qualname__ == 'HTTPError':
                    if e.response.status_code == 404:
                        raise MRANotFoundError()
                    if e.response.status_code == 409:
                        raise MRAConflictError()
                    if e.response.status_code == 500:
                        raise MRACriticalError()
                if self.is_ignored(e):
                    return f(*args, **kwargs)
                raise MRASyncingError(e.__str__())
        return wrapper

    def is_ignored(self, exception):
        return type(exception) in self.ignore


class MRAClient(object):

    def __init__(self, url, username=None, password=None):
        self.base_url = url
        self.auth = (username and password) and (username, password)

    def _req(self, method, url, extension='json', **kwargs):
        kwargs.setdefault('allow_redirects', True)
        kwargs.setdefault('headers', {'content-type': 'application/json; charset=utf-8'})
        # TODO pretty:
        url = '{0}.{1}'.format(
            reduce(urljoin, (self.base_url,) + tuple(m + '/' for m in url))[:-1],
            extension)
        r = request(method, url, auth=self.auth, **kwargs)
        r.raise_for_status()
        if r.status_code == 200:
            if extension == 'json':
                try:
                    return r.json()
                except Exception as e:
                    if e.__class__.__qualname__ == 'JSONDecodeError':
                        return {}
                    raise e
            return r.text

    def get(self, *url, **kwargs):
        return self._req('get', url, **kwargs)

    def post(self, *url, **kwargs):
        return self._req('post', url, **kwargs)

    def put(self, *url, **kwargs):
        return self._req('put', url, **kwargs)

    def delete(self, *url, **kwargs):
        return self._req('delete', url, **kwargs)


class MRAHandler(metaclass=Singleton):

    def __init__(self, *args, **kwargs):
        self.remote = MRAClient(
            IDGO_GEOGRAPHIC_LAYER_MRA_URL,
            username=IDGO_GEOGRAPHIC_LAYER_MRA_USERNAME,
            password=IDGO_GEOGRAPHIC_LAYER_MRA_PASSWORD,
            )

    # Workspace
    # =========

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def is_workspace_exists(self, ws_name):
        try:
            self.get_workspace(ws_name)
        except MRANotFoundError:
            return False
        else:
            return True

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_workspace(self, ws_name):
        return self.remote.get('workspaces', ws_name)['workspace']

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def del_workspace(self, ws_name):
        self.remote.delete('workspaces', ws_name)

    @MRAExceptionsHandler()
    def create_workspace(self, organisation):
        SupportedCrs = apps.get_model(app_label='idgo_admin', model_name='SupportedCrs')
        srs = [crs.authority for crs in SupportedCrs.objects.all()]

        json = {
            'workspace': {
                'name': organisation.slug,
                # TODO: Corriger le problème d'encodage dans MRA
                'title': kill_all_special_characters(organisation.legal_name),
                'abstract': kill_all_special_characters(organisation.description),
                # END TODO
                'srs': srs}}
        self.remote.post('workspaces', json=json)
        return self.get_workspace(organisation.slug)

    def get_or_create_workspace(self, organisation):
        try:
            return self.get_workspace(organisation.slug)
        except MRANotFoundError:
            pass
        return self.create_workspace(organisation)

    # Data store
    # ==========

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_datastore(self, ws_name, ds_name):
        return self.remote.get('workspaces', ws_name,
                               'datastores', ds_name)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def del_datastore(self, ws_name, ds_name):
        self.remote.delete('workspaces', ws_name,
                           'datastores', ds_name)

    @MRAExceptionsHandler()
    def create_datastore(self, ws_name, ds_name):
        json = {
            'dataStore': {
                'name': ds_name,
                'connectionParameters': {
                    'dbtype': IDGO_GEOGRAPHIC_LAYER_MRA_DB_TYPE,
                    'host': IDGO_GEOGRAPHIC_LAYER_MRA_DB_HOST,
                    'port': IDGO_GEOGRAPHIC_LAYER_MRA_DB_PORT,
                    'database': IDGO_GEOGRAPHIC_LAYER_MRA_DB_NAME,
                    'user': IDGO_GEOGRAPHIC_LAYER_MRA_DB_USERNAME,
                    'password': IDGO_GEOGRAPHIC_LAYER_MRA_DB_PASSWORD,
                    }}}

        self.remote.post('workspaces', ws_name,
                         'datastores', json=json)

        return self.get_datastore(ws_name, ds_name)

    def get_or_create_datastore(self, ws_name, ds_name):
        try:
            return self.get_datastore(ws_name, ds_name)
        except MRANotFoundError:
            pass
        return self.create_datastore(ws_name, ds_name)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_featuretype(self, ws_name, ds_name, ft_name):
        return self.remote.get('workspaces', ws_name,
                               'datastores', ds_name,
                               'featuretypes', ft_name)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def del_featuretype(self, ws_name, ds_name, ft_name):
        self.remote.delete('workspaces', ws_name,
                           'datastores', ds_name,
                           'featuretypes', ft_name)

    @MRAExceptionsHandler()
    def create_featuretype(self, ws_name, ds_name, ft_name, **kwargs):
        json = {
            'featureType': {
                'name': ft_name,
                'title': kwargs.get('title', ft_name),
                'abstract': kwargs.get('abstract', ft_name),
                'enabled': kwargs.get('enabled', True)}}

        self.remote.post('workspaces', ws_name,
                         'datastores', ds_name,
                         'featuretypes', json=json)

        return self.get_featuretype(ws_name, ds_name, ft_name)

    def get_or_create_featuretype(self, ws_name, ds_name, ft_name, **kwargs):
        try:
            return self.get_featuretype(ws_name, ds_name, ft_name)
        except MRANotFoundError:
            pass
        return self.create_featuretype(ws_name, ds_name, ft_name, **kwargs)

    # Coverage store
    # ==============

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_coveragestore(self, ws_name, cs_name):
        return self.remote.get('workspaces', ws_name,
                               'coveragestores', cs_name)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def del_coveragestore(self, ws_name, cs_name):
        self.remote.delete('workspaces', ws_name,
                           'coveragestores', cs_name)

    @MRAExceptionsHandler()
    def create_coveragestore(self, ws_name, cs_name, filename=None):
        json = {
            'coverageStore': {
                'name': cs_name,
                'connectionParameters': {
                    'url': 'file://{}'.format(filename)}}}

        self.remote.post('workspaces', ws_name,
                         'coveragestores', json=json)

        return self.get_coveragestore(ws_name, cs_name)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_or_create_coveragestore(self, ws_name, cs_name, **kwargs):
        try:
            return self.get_coveragestore(ws_name, cs_name)
        except MRANotFoundError:
            pass
        return self.create_coveragestore(ws_name, cs_name, **kwargs)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_coverage(self, ws_name, cs_name, c_name):
        return self.remote.get('workspaces', ws_name,
                               'coveragestores', cs_name,
                               'coverages', c_name)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def del_coverage(self, ws_name, cs_name, c_name):
        self.remote.delete('workspaces', ws_name,
                           'coveragestores', cs_name,
                           'coverages', c_name)

    @MRAExceptionsHandler()
    def create_coverage(self, ws_name, cs_name, c_name, **kwargs):
        json = {
            'coverage': {
                'name': c_name,
                'title': kwargs.get('title', c_name),
                'abstract': kwargs.get('abstract', c_name),
                'enabled': kwargs.get('enabled', True)}}

        self.remote.post('workspaces', ws_name,
                         'coveragestores', cs_name,
                         'coverages', json=json)

        return self.get_coverage(ws_name, cs_name, c_name)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_or_create_coverage(self, ws_name, cs_name, c_name, **kwargs):
        try:
            return self.get_coverage(ws_name, cs_name, c_name)
        except MRANotFoundError:
            pass
        return self.create_coverage(ws_name, cs_name, c_name, **kwargs)

    # Style
    # =====

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_style(self, s_name, as_sld=True):
        return self.remote.get('styles', s_name, extension='sld',
                               headers={'content-type': 'application/vnd.ogc.sld+xml; charset=utf-8'})

    @MRAExceptionsHandler()
    def create_style(self, s_name, data):
        return self.remote.post(
            'styles', extension='sld', params={'name': s_name}, data=preprocessing_sld(data),
            headers={'content-type': 'application/vnd.ogc.sld+xml; charset=utf-8'})

    @MRAExceptionsHandler()
    def update_style(self, s_name, data):
        return self.remote.put(
            'styles', s_name, extension='sld', data=preprocessing_sld(data),
            headers={'content-type': 'application/vnd.ogc.sld+xml; charset=utf-8'})

    @MRAExceptionsHandler()
    def delete_style(self, s_name):
        raise NotImplementedError  # Not implemented on MRA!

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def create_or_update_style(self, s_name, data):
        try:
            self.update_style(s_name, data)
        except MRANotFoundError:
            self.create_style(s_name, data)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_layer_styles(self, l_name):
        data = []
        for style in self.remote.get('layers', l_name, 'styles')['styles']:
            data.append(self.remote.get('styles', style['name'])['style'])
        return data

    # Layer
    # =====

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_layer(self, l_name):
        return self.remote.get('layers', l_name)['layer']

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def update_layer_defaultstyle(self, l_name, s_name):
        json = {'layer': self.get_layer(l_name)}
        json['layer'].update({
            'defaultStyle': {
                'name': s_name,
                'href': '{0}styles/{1}.json'.format(
                    IDGO_GEOGRAPHIC_LAYER_MRA_URL, s_name),
                }
            })
        return self.remote.put('layers', l_name, json=json)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def del_layer(self, l_name):
        self.remote.delete('layers', l_name)

    @MRAExceptionsHandler()
    def update_layer(self, l_name, data, ws_name=None):
        if ws_name:
            return self.remote.put('workspaces', ws_name,
                                   'layers', l_name,
                                   json={'layer': data})
        return self.remote.put('layers', l_name, json={'layer': data})

    @MRAExceptionsHandler()
    def enable_layer(self, ws_name, l_name):
        self.update_layer(l_name, {'enabled': True}, ws_name=ws_name)

    @MRAExceptionsHandler()
    def disable_layer(self, ws_name, l_name):
        self.update_layer(l_name, {'enabled': False}, ws_name=ws_name)

    # Service
    # =======

    @MRAExceptionsHandler()
    def get_ows_settings(self, ows, ws_name):
        return self.remote.get('services', ows, 'workspaces', ws_name, 'settings')[ows]

    @MRAExceptionsHandler()
    def update_ows_settings(self, ows, data, ws_name=None):
        if ws_name:
            self.remote.put('services', ows,
                            'workspaces', ws_name,
                            'settings', json={ows: data})
        else:
            self.remote.put('services', ows,
                            'settings', json={ows: data})

    def enable_ows(self, ws_name=None, ows='ows'):
        self.update_ows_settings(ows, {'enabled': True}, ws_name=ws_name)

    def disable_ows(self, ws_name=None, ows='ows'):
        self.update_ows_settings(ows, {'enabled': False}, ws_name=ws_name)

    # def enable_wms(self, ws_name):
    #     self.enable_ows(ws_name, ows='wms')

    # def disable_wms(self, ws_name):
    #     self.disable_ows(ws_name, ows='wms')

    # def enable_wfs(self, ws_name):
    #     self.enable_ows(ws_name, ows='wms')

    # def disable_wfs(self, ws_name):
    #     self.disable_ows(ws_name, ows='wms')

    # def enable_wcs(self, ws_name):
    #     self.enable_ows(ws_name, ows='wms')

    # def disable_wcs(self, ws_name):
    #     self.disable_ows(ws_name, ows='wms')

    # Layergroup
    # ==========

    @MRAExceptionsHandler()
    def get_layergroup(self, ws_name, lg_name):
        self.remote.get('workspaces', ws_name, 'layergroups', lg_name)['layerGroup']

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def is_layergroup_exists(self, ws_name, lg_name):
        try:
            self.get_layergroup(ws_name, lg_name)
        except MRANotFoundError:
            return False
        else:
            return True

    @MRAExceptionsHandler()
    def create_or_update_layergroup(self, ws_name, data):
        lg_name = data.get('name')
        if self.is_layergroup_exists(ws_name, lg_name):
            self.remote.put('workspaces', ws_name,
                            'layergroups', lg_name,
                            json={'layerGroup': data})
        else:
            self.remote.post('workspaces', ws_name,
                             'layergroups', json={'layerGroup': data})

    @MRAExceptionsHandler()
    def del_layergroup(self, ws_name, lg_name):
        if self.is_layergroup_exists(ws_name, lg_name):
            self.remote.delete('workspaces', ws_name, 'layergroups', lg_name)

    # Miscellaneous
    # =============

    @MRAExceptionsHandler()
    def get_fonts(self, ws_name=None):
        return self.remote.get('fonts')['fonts']


MRAHandler = MRAHandler()
