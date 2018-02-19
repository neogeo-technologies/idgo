# Copyright (c) 2017-2018 Datasud.
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


from django.core.management.base import BaseCommand
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.forms.resource import get_all_users_for_organizations
from idgo_admin.models import Resource
import json


class Command(BaseCommand):

    help = "Synchronisation des droits des utilisateur sur les ressources par organisations"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def handle(self, *args, **options):
        for resource in Resource.objects.exclude(organisations_allowed=None):
            dataset = resource.dataset

            ckan_user = ckan_me(
                ckan.get_user(dataset.editor.username)['apikey'])

            ckan_params = {
                'id': str(resource.ckan_id),
                'restricted': json.dumps({
                    'allowed_users': ','.join(
                        get_all_users_for_organizations(
                            [r.pk for r in resource.organisations_allowed.all()])),
                    'level': 'only_allowed_users'})}

            ckan_user.push_resource(
                ckan_user.get_package(str(dataset.ckan_id)), **ckan_params)
            ckan_user.close()
