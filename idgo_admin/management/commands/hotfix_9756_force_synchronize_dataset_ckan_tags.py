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


""" HOTFIX """


import logging

from django.core.management.base import BaseCommand

from idgo_admin.ckan_module import CkanHandler
from idgo_admin.models import Dataset


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """Cf. https://redmine.neogeo.fr/issues/9756"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        dataset_qs = Dataset.default.filter(keywords__isnull=False).distinct().order_by('id')
        total = dataset_qs.count()
        count = 0
        for dataset in dataset_qs:
            count += 1
            qs_dataset_keywords = dataset.keywords.all()

            ckan_id = str(dataset.ckan_id)

            logger.info(
                "[%d/%d] - Synchronize Dataset %d (%s) with tags: '%s'." % (
                    count,
                    total,
                    dataset.pk,
                    ckan_id,
                    "', '".join([k.name for k in qs_dataset_keywords]))
                    )

            try:
                CkanHandler.publish_dataset(
                    id=ckan_id,
                    tags=[{'name': k.name} for k in qs_dataset_keywords])
            except Exception as e:
                logger.exception(e)
                logger.warning("Error was ingored.")
