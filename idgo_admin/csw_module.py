# Copyright (c) 2017-2019 Datasud.
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


from idgo_admin import logger
from owslib.csw import CatalogueServiceWeb
from owslib.fes import PropertyIsEqualTo


class CswBaseHandler(object):

    def __init__(self, url, username=None, password=None):
        self.url = url
        self.username = username
        self.password = password

        self.remote = CatalogueServiceWeb(
            self.url, timeout=3600, lang='fr-FR', version='2.0.2',
            skip_caps=True, username=self.username, password=self.password)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        # Fake
        logger.info('Close CSW connection')

    def get_all_organisations(self, *args, **kwargs):
        self.remote.getdomain('OrganisationName', dtype='property')
        result = []
        _get_domain = self.remote.results.copy()
        for value in _get_domain.get('values'):
            constraints = [PropertyIsEqualTo('OrganisationName', value)]
            self.remote.getrecords2(resulttype='hits', esn='brief', constraints=constraints)
            package_count = self.remote.results.get('matches')
            result.append({
                'name': value,
                'display_name': value,
                'package_count': package_count,
                })
        return result
