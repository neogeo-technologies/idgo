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


""" SYNCHRONISATION CKAN """


import logging

from django.core.management.base import BaseCommand

from idgo_admin.ckan_module import CkanHandler
from idgo_admin.models import Category


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Synchroniser les catégories IDGO avec CKAN."

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.ckan = CkanManagerHandler()

    def handle(self, *args, **options):
        queryset = Category.objects.all().order_by('id')
        total = queryset.count()
        count = 0
        for instance in queryset:
            count += 1
            logger.info("[%d/%d] - Save Resource %d." % (count, total, instance.pk))

            if CkanHandler.is_group_exists(instance.slug):
                CkanHandler.update_group(instance)
                logger.info("'%s' is udpated." % instance.slug)
            else:
                CkanHandler.add_group(instance)
                logger.info("'%s' is created." % instance.slug)
