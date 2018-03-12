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
from django.utils import timezone
from idgo_admin.models import Resource
from idgo_admin.models import Task


NOW = timezone.now()


class Command(BaseCommand):

    help = """Synchroniser les ressources en fonction de la fréquence de
              mise à jour de chacune (pour celles dont le champ 'dl_url'
              est renseigné)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        for instance in Resource.objects.all():
            if instance.dl_url and instance.synchronisation:
                if self.is_to_synchronized(instance):

                    extras = {
                        'dataset': instance.dataset.id,
                        'resource': instance.id}

                    task = Task.objects.create(action=__name__)
                    try:
                        instance.save(sync_ckan=True)
                    except Exception as e:
                        task.extras = {**extras, **{'error': e.__str__()}}
                        task.state = 'failed'
                    finally:
                        task.end = timezone.now()
                        task.extras = extras
                        task.state = 'succesful'
                        task.save()

    def is_to_synchronized(self, instance):
        return {
            'never': None,
            'daily': True,
            'weekly': NOW.isoweekday() == 1,
            'bimonthly': NOW.day in (1, 15),
            'monthly': NOW.day == 1,
            'quarterly': NOW.day == 1 and NOW.month in (1, 4, 7, 10),
            'biannual': NOW.day == 1 and NOW.month in (1, 7),
            'annual': NOW.day == 1 and NOW.month == 1
            }.get(instance.sync_frequency, None)
