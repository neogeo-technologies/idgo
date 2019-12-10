# Copyright (c) 2017-2019 Neogeo-Technologies.
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


from django.conf import settings
from django.core.management.base import BaseCommand
from idgo_admin.models import Profile
from idgo_admin.models import User
import logging


logger = logging.getLogger('django')


class Command(BaseCommand):

    def add_arguments(self, parser):

        parser.add_argument(
            '--password',
            required=False,
            dest='pwd',
            help="ce mot de passe sera utiliser à la place de celui defini dans les settings"
        )

    def handle(self, *args, **options):
        pwd = options['pwd']
        if not pwd:
            password = getattr(settings, "SUPER_PASSWORD", "passpass")

        sid_id = getattr(settings, "SUPER_UID", "UIDMISSING")
        username = getattr(settings, "SUPER_USERNAME", "admin")
        email = getattr(settings, "SUPER_EMAIL", "admin@notdefined.no")

        user = User.objects.create_superuser(
            username=sid_id,
            email=email,
            password=password
        )
        profile = Profile.objects.create(user=user)

        logger.info("Profile created OK: {}".format(profile.user.username))
