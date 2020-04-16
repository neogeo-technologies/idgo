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
from urllib.parse import urljoin

from django.core.management.base import BaseCommand

from idgo_admin.ckan_module import CkanHandler
from idgo_admin.models import Resource


logger = logging.getLogger('glob')


class Command(BaseCommand):

    help = """Cf. https://redmine.neogeo.fr/issues/8524"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        for resource in Resource.objects.all():
            if not resource.up_file:
                continue

            url = urljoin(resource.ckan_url, 'download/%s' % resource.up_file.name)

            CkanHandler.update_resource(str(resource.ckan_id), url=url)
            try:
                CkanHandler.update_resource(str(resource.ckan_id), url=url)
            except Exception as e:
                self.stdout.write("Error with resource %s: '%s'." % (str(resource.pk), resource.title))
                logger.error(e)

            self.stdout.write("Updated resource %s: '%s' with filename '%s'." % (str(resource.pk), resource.title, resource.up_file.name))
