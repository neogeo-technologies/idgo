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


import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from idgo_admin.ckan_module import CkanHandler
from idgo_admin.ckan_module import CkanUserHandler
from idgo_admin.models import Profile
from idgo_admin.models import Resource


NOW = timezone.now()


def get_all_users_for_organisations(list_id):
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


class Command(BaseCommand):

    help = """."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        for resource in Resource.objects.all():

            # (0) Aucune restriction
            if resource.restricted_level == 'public':
                restricted = json.dumps({'level': 'public'})

            # (1) Uniquement pour un utilisateur connecté
            elif resource.restricted_level == 'registered':
                restricted = json.dumps({'level': 'registered'})

            # (2) Seulement les utilisateurs indiquées
            elif resource.restricted_level == 'only_allowed_users':
                restricted = json.dumps({
                    'allowed_users': ','.join(
                        resource.profiles_allowed.exists() and [
                            p.user.username for p
                            in resource.profiles_allowed.all()] or []),
                    'level': 'only_allowed_users'
                })

            # (3) Les utilisateurs de cette organisation
            elif resource.restricted_level == 'same_organization':
                restricted = json.dumps({
                    'allowed_users': ','.join(
                        get_all_users_for_organisations(
                            resource.organisations_allowed.all())),
                    'level': 'only_allowed_users'
                })

            # (3) Les utilisateurs des organisations indiquées
            elif resource.restricted_level == 'any_organization':
                restricted = json.dumps({
                    'allowed_users': ','.join(
                        get_all_users_for_organisations(
                            resource.organisations_allowed.all())),
                    'level': 'only_allowed_users'
                })

            data = CkanHandler.call_action('resource_show', id=str(resource.ckan_id))
            data.update({'restricted': restricted})

            # apikey = CkanHandler.get_user(resource.dataset.editor.username)['apikey']
            # with CkanUserHandler(apikey=apikey) as ckan:
            #     ckan.call_action('resource_update', id=id, **data)
            CkanHandler.call_action('resource_update', **data)

