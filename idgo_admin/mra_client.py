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


import ast
from django.conf import settings
from functools import reduce
from functools import wraps
from idgo_admin.exceptions import GenericException
from requests.exceptions import HTTPError
from requests import request
import timeout_decorator
from urllib.parse import urljoin


MRA = settings.MRA
MRA_TIMEOUT = settings.MRA.get('TIMEOUT', 3600)

DB_SETTINGS = settings.DATABASES[settings.DATAGIS_DB]


def timeout(fun):
    t = MRA_TIMEOUT  # in seconds

    @timeout_decorator.timeout(t, use_signals=False)
    def return_with_timeout(fun, args=tuple(), kwargs=dict()):
        return fun(*args, **kwargs)

    @wraps(fun)
    def wrapper(*args, **kwargs):
        return return_with_timeout(fun, args=args, kwargs=kwargs)

    return wrapper


class MRASyncingError(GenericException):
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


class MRATimeoutError(MRASyncingError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class MRAExceptionsHandler(object):

    def __init__(self, ignore=None):
        self.ignore = ignore or []

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                print(e.__str__())
                if isinstance(e, timeout_decorator.TimeoutError):
                    raise MRATimeoutError
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

    @timeout
    def _req(self, method, url, params, **kwargs):
        kwargs.setdefault('allow_redirects', True)

        print(reduce(urljoin, self.base_url + url))

        r = request(
            method, reduce(urljoin, self.base_url + url),
            params=params, auth=self.auth, **kwargs)

        try:
            self.raise_for_status()
        except HTTPError as e:
            raise MRASyncingError(e.__str__())
        return r

    def get(self, *url, **params):
        return self._req('get', url, params)

    def post(self, *url, **params):
        return self._req('post', url, params)

    def put(self, *url, **params):
        return self._req('put', url, params)

    def delete(self, *url, **params):
        return self._req('delete', url, params)


class MRAHandler(object):

    def __init__(self, *args, **kwargs):
        self.remote = MRAClient(MRA['URL'])

    def get_or_create_workspace(self, ws_name):
        try:
            return self.remote.get('workspaces', ws_name)
        except DoesNotExists as e:
            pass
        body = {'workspace': {'name': ws_name}}
        self.remote.post('workspaces', ws_name, body=body)

        self.add_datastore(ws_name, 'public')

    def add_datastore(self, ws_name, ds_name):
        body = {
            'dataStore': {
                'name': ds_name,
                'enabled': True,
                'connectionParameters': {
                    'host': DB_SETTINGS['HOST'],
                    'user': DB_SETTINGS['USER'],
                    'database': DB_SETTINGS['NAME'],
                    'dbtype': DB_SETTINGS['ENGINE'].split('.')[-1],
                    'password': DB_SETTINGS['PASSWORD'],
                    'port': DB_SETTINGS['PORT']}}}
        self.remote.post(
            'workspaces', ws_name, 'datastores', ds_name, body=body)

    def del_workspace(self, ws_name):
        self.remote.delete('workspaces', ws_name)

    def publish_layers_resource(self, resource):

        ws_name = resource.dataset.organisation.ckan_slug
        ds_name = 'public'

        layers = []
        for data_id in resource.datagis_id:
            try:
                self.remote.get('workspaces', ws_name, 'datastores',
                                ds_name, 'featuretypes', data_id)
            except DoesNotExists:
                self.remote.post('workspaces', ws_name, 'datastores',
                                 ds_name, 'featuretypes', data_id,
                                 body={'featureType': {'name': data_id}})

            layers.append(self.remote.get('layers', data_id))

        return layers

    def del_layers_resource(self, resource):

        ws_name = resource.dataset.organisation.ckan_slug
        ds_name = 'public'

        for data_id in resource.datagis_id:
            self.remote.delete('layer', data_id)
            self.remote.delete('workspaces', ws_name, 'datastores',
                               ds_name, 'featuretypes', data_id)

    def get_all_styles_for_layer(self, l_name):
        return self.remote.get('layers', l_name, 'styles')

    def add_style_for_layer(self, l_name, s_name, sld):
        return self.remote.post('layers', l_name, 'styles', s_name, '.sld?name=', s_name, body=sld)

    def update_style_layer(self, l_name, s_name, sld):
        return self.remote.put('layers', l_name, 'styles', s_name, '.sld?name=', s_name, body=sld)

    def del_style_layer(self, l_name, s_name):
        return self.remote.delete('layers', l_name, 'styles', s_name, '.sld')
