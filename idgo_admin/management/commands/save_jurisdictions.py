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


import logging

from django.core.management.base import BaseCommand

from idgo_admin.models import Jurisdiction


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Forcer la sauvegarde de tous les territoires de compétence."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        queryset = Jurisdiction.objects.all().order_by('code')
        total = queryset.count()
        count = 0
        for instance in queryset:
            count += 1
            logger.info("[%d/%d] - Save Jurisdiction '%s'." % (count, total, instance.code))
            try:
                instance.save()
            except Exception as e:
                logger.exception(e)
                logger.info("Continue")

