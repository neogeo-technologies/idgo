from django.core.management.base import BaseCommand
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.forms.resource import get_all_users_for_organizations
from idgo_admin.models import Resource
import json


class Command(BaseCommand):

    help = ''

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
