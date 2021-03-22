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


""" DEPRECATED

Utiliser django-celery-beat avec la tâche : `sync_extractor_tasks`.
"""


import logging

from django.core.management.base import BaseCommand

from idgo_admin.models import AsyncExtractorTask


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Synchroniser les tâches d'extraction pour l'envoi d'e-mail."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        for instance in AsyncExtractorTask.objects.filter(success=None):
            logger.info("Check extractor task: %s." % str(instance.uuid))
