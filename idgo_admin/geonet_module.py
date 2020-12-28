# Copyright (c) 2017-2020 Neogeo-Technologies.
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


import logging

from owslib.csw import CatalogueServiceWeb
import requests
from urllib.parse import urljoin

from idgo_admin.utils import Singleton

from idgo_admin import GEONETWORK_URL
from idgo_admin import GEONETWORK_LOGIN
from idgo_admin import GEONETWORK_PASSWORD
from idgo_admin import GEONETWORK_TIMEOUT


logger = logging.getLogger('idgo_admin.geonet_module')


class GeonetUserHandler(metaclass=Singleton):

    def __init__(self):
        self.username = GEONETWORK_LOGIN
        self.password = GEONETWORK_PASSWORD
        self.remote = CatalogueServiceWeb(
            urljoin(GEONETWORK_URL, 'srv/fre/csw-publication'),
            timeout=GEONETWORK_TIMEOUT, lang='fr-FR',
            version='2.0.2', skip_caps=True,
            username=self.username, password=self.password)

    def _get(self, url, params):
        r = requests.get(
            url, params=params, auth=(self.username, self.password))
        r.raise_for_status()
        return r

    def _q(self, identifier):
        r = self._get(urljoin(GEONETWORK_URL, 'srv/fre/q'),
                      {'uuid': identifier, '_content_type': 'json'})
        metadata = r.json().get('metadata')
        if metadata \
                and len(metadata) == 1 \
                and metadata[0]['uuid'] == identifier:
            return metadata[0]['id']
        # Sinon error ?

    def _md_publish(self, identifier):
        return self._get(
            urljoin(GEONETWORK_URL, 'srv/fre/md.publish'), {'ids': identifier})

    def _transaction(self, ttype, identifier, record=None):
        return self.remote.transaction(
            ttype=ttype, typename='gmd:MD_Metadata',
            identifier=identifier, record=record)

    def is_record_exists(self, id):
        return self.get_record(id) and True or False

    def get_record(self, id):
        try:
            self.remote.getrecordbyid(
                id=[id], outputschema='http://www.isotc211.org/2005/gmd')
        except requests.exceptions.HTTPError as e:
            logger.exception(e)
            if (e.response.status_code == 404):
                logger.warning("Error 404 was ignored.")
                return None
            raise e
        else:
            logger.debug("Get MD record with dc:identifier = '%s'" % id)
            return self.remote.records.get(id)

    def create_record(self, id, record):
        logger.debug("Create MD record with dc:identifier = '%s'" % id)
        return self._transaction('insert', id, record=record)

    def update_record(self, id, record):
        logger.debug("Update MD record with dc:identifier = '%s'" % id)
        return self._transaction('update', id, record=record)

    def delete_record(self, id):
        logger.debug("Delete MD record with dc:identifier = '%s'" % id)
        return self._transaction('delete', id)

    def publish(self, id):
        return self._md_publish(self._q(id))


GeonetUserHandler = GeonetUserHandler()
