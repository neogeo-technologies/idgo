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
from idgo_admin.models import Dataset
from idgo_admin.models import Granularity


class Command(BaseCommand):

    help = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        for instance in Dataset.objects.all():
            print(instance.id, instance.name)
            if instance.geocover == 'jurisdiction':
                continue

            instance.geocover = 'jurisdiction'
            if not instance.granularity:
                instance.granularity = Granularity.objects.get(pk='indefinie')
            instance.save()
