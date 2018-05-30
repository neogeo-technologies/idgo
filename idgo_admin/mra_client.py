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
from idgo_admin.utils import Singleton
from requests import request
import timeout_decorator
from urllib.parse import urljoin


MRA = settings.MRA
MRA_TIMEOUT = MRA.get('TIMEOUT', 3600)
MRA_DATAGIS_USER = MRA['DATAGIS_DB_USER']
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


class MRANotFoundError(GenericException):
    def __init__(self, *args, **kwargs):
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
                if self.is_ignored(e):
                    return f(*args, **kwargs)
                if e.__class__.__qualname__ == 'HTTPError':
                    if e.response.status_code == 404:
                        raise MRANotFoundError
                if isinstance(e, timeout_decorator.TimeoutError):
                    raise MRATimeoutError
                if self.is_ignored(e):
                    return f(*args, **kwargs)
                print(e)
                raise MRASyncingError(e.__str__())
        return wrapper

    def is_ignored(self, exception):
        return type(exception) in self.ignore


class MRAClient(object):

    def __init__(self, url, username=None, password=None):
        self.base_url = url
        self.auth = (username and password) and (username, password)

    @timeout
    def _req(self, method, url, **kwargs):
        kwargs.setdefault('allow_redirects', True)
        kwargs.setdefault('headers', {'content-type': 'application/json'})
        # TODO pretty:
        url = '{}.json'.format(
            reduce(urljoin, (self.base_url,) + tuple(m + '/' for m in url))[:-1])

        r = request(method, url, auth=self.auth, **kwargs)
        r.raise_for_status()
        return r

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
            MRA['URL'], username=MRA['USERNAME'], password=MRA['PASSWORD'])

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_workspace(self, ws_name):
        return self.remote.get('workspaces', ws_name)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def del_workspace(self, ws_name):
        self.remote.delete('workspaces', ws_name)

    @MRAExceptionsHandler()
    def create_workspace(self, ws_name):
        json = {
            'workspace': {
                'name': ws_name}}

        self.remote.post('workspaces', json=json)

        return self.get_workspace(ws_name)

    def get_or_create_workspace(self, ws_name):
        try:
            return self.get_workspace(ws_name)
        except MRANotFoundError:
            pass
        return self.create_workspace(ws_name)

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
                    'host': DB_SETTINGS['HOST'],
                    'user': MRA_DATAGIS_USER,
                    'database': DB_SETTINGS['NAME'],
                    'dbtype': DB_SETTINGS['ENGINE'].split('.')[-1],
                    'password': DB_SETTINGS['PASSWORD'],
                    'port': DB_SETTINGS['PORT']}}}

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
    def create_featuretype(self, ws_name, ds_name, ft_name):
        json = {
            'featureType': {
                'name': ft_name}}

        self.remote.post('workspaces', ws_name,
                         'datastores', ds_name,
                         'featuretypes', json=json)

        return self.get_featuretype(ws_name, ds_name, ft_name)

    def get_or_create_featuretype(self, ws_name, ds_name, ft_name):
        try:
            return self.get_featuretype(ws_name, ds_name, ft_name)
        except MRANotFoundError:
            pass
        return self.create_featuretype(ws_name, ds_name, ft_name)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def get_layer(self, l_name):
        return self.remote.get('layers', l_name)

    @MRAExceptionsHandler(ignore=[MRANotFoundError])
    def del_layer(self, l_name):
        self.remote.delete('layers', l_name)

    def publish_layers_resource(self, resource):

        ws_name = resource.dataset.organisation.ckan_slug
        self.get_or_create_workspace(ws_name)

        ds_name = 'public'
        self.get_or_create_datastore(ws_name, ds_name)

        for data_id in resource.datagis_id:
            self.get_or_create_featuretype(ws_name, ds_name, str(data_id))


MRAHandler = MRAHandler()
