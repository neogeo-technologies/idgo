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

from idgo_admin.models import Layer


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "redmine-issues/10986"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('--layer-name', dest='name__in', nargs='*', type=str, default=[])

    def handle(self, *args, **options):
        name__in = options.get('name__in', list())

        queryset = Layer.objects.filter(name__in=name__in)
        total = queryset.count()
        count = 0
        for instance in queryset:
            resource = instance.resource

            count += 1
            logger.info("[%d/%d] - Delete Layer %s." % (count, total, instance.name))
            try:
                instance.delete()
            except Exception as e:
                logger.exception(e)
                logger.info("Continue")

            logger.info("[%d/%d] - Save Resource %s." % (count, total, str(instance)))
            try:
                resource.save()
            except Exception as e:
                logger.exception(e)
                logger.info("Continue")
