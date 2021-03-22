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

Utiliser django-celery-beat avec la tâche : `clean_up_actions_out_of_delay`.
"""


import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from idgo_admin.models import AccountActions
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Nettoyer les demandes obsolètes."

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def n_days_ago(self, n):
        return timezone.now() - timezone.timedelta(days=n)

    def handle(self, *args, **options):

        organisations_to_delete = []
        profiles_to_delete = []

        old_actions = AccountActions.objects.filter(
            closed=None, created_on__lte=self.n_days_ago(2))

        for action in old_actions:
            username = 'N/A'
            org_name = 'N/A'

            if action.profile.user:
                username = action.profile.user.username

            if action.profile.organisation:
                org_name = action.profile.organisation.legal_name

            # if action.action == 'reset_password':
            #     pass TODO ?

            # if action.action == 'confirm_rattachement':
            #     pass TODO ?

            if action.action == 'confirm_mail':
                profiles_to_delete.append(action.profile)

            if action.action == 'confirm_new_organisation':
                organisations_to_delete.append(action.profile.organisation)

            if action.action == 'confirm_contribution':
                liaison = LiaisonsContributeurs.objects.get(
                    profile=action.profile,
                    organisation=action.organisation)
                liaison.delete()

                logger.info("Delete LiaisonsContributeurs: %s / %s" % (
                    username, action.organisation.legal_name))

            if action.action == 'confirm_referent':
                liaison = LiaisonsReferents.objects.get(
                    profile=action.profile, organisation=action.organisation)
                liaison.delete()

                logger.info("Delete LiaisonsReferents: %s / %s" % (
                    username, action.organisation.legal_name))

            action.delete()

        # Fait en second pour ne pas 'casser' la boucle précédente à cause des cascade_on_delete
        for profile in profiles_to_delete:
            profile.delete()
            user.delete()
            logger.info("Delete User/Profile: %s" % profile.user.username)

        for organisation in organisations_to_delete:
            organisation.delete()
            logger.info("Delete Organisation %s" % organisation.name)
