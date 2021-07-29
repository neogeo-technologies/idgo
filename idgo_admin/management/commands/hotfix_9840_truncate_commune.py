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


""" Cf. https://redmine.neogeo.fr/issues/9840 """


import logging

from django.core.management.base import BaseCommand

from idgo_admin.models import Commune


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """Cf. https://redmine.neogeo.fr/issues/9840"""

    def handle(self, *args, **options):
        try:
            Commune.objects.all().delete()
        except BaseException as err:
            logger.exception(err)
            self.stdout.write(
                self.style.ERROR("Command '%s' failed" % self.__module__))
        else:
            self.stdout.write(
                "Command '%s' passed successfully" % self.__module__)
