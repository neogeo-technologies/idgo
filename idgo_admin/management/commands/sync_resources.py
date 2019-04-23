# Copyright (c) 2017-2019 Datasud.
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


from celery.decorators import task
from celery.signals import before_task_publish
from celery.signals import task_failure
from celery.signals import task_postrun
from celery.signals import task_success
from celery.signals import task_unknown
from celery.utils.log import get_task_logger
from django.core.management.base import BaseCommand
from django.utils import timezone
from idgo_admin.models import Resource
from idgo_admin.models import Task
from uuid import UUID
from uuid import uuid4


logger = get_task_logger(__name__)

NOW = timezone.now()


@before_task_publish.connect
def on_beforehand(headers=None, body=None, sender=None, **kwargs):
    uuid = UUID(headers['id'])
    resource_pk = body[1]['resource_pk']
    resource = Resource.objects.get(pk=resource_pk)
    extras = {'dataset': resource.dataset.id, 'resource': resource.id}

    Task.objects.create(uuid=uuid, action=__name__, extras=extras)


@task_unknown.connect
def on_task_unknown(task_id=None, sender=None, request=None, **kwargs):
    task = Task.objects.get(uuid=UUID(request.id))
    task.state = 'failed'
    task.extras = {**task.extras, **{'error': 'unknown'}}
    task.save()


@task_failure.connect
def on_task_failure(task_id=None, sender=None, exception=None, **kwargs):
    task = Task.objects.get(uuid=UUID(task_id))
    task.state = 'failed'
    task.extras = {**task.extras, **{'error': exception.__str__()}}
    task.save()


@task_success.connect
def on_task_success(sender=None, **kwargs):
    task = Task.objects.get(uuid=UUID(sender.request.id))
    task.state = 'succesful'
    task.save()


@task_postrun.connect
def on_task_postrun(task_id=None, **kwargs):
    if task_id:
        uuid = UUID(task_id)
        task = Task.objects.get(uuid=uuid)
        task.end = timezone.now()
        task.save()


@task(name='save_resource', ignore_result=False)
def save_resource(resource_pk=None):
    resource = Resource.objects.get(pk=resource_pk)
    resource.save(current_user=None, synchronize=True)


class Command(BaseCommand):

    help = """Synchroniser les ressources en fonction de la fréquence de
              mise à jour de chacune (pour celles dont le champ 'dl_url'
              est renseigné)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        for resource in Resource.objects.all():
            if resource.dl_url and resource.synchronisation:
                if self.is_to_synchronized(resource):
                    save_resource.apply_async(
                        kwargs={'resource_pk': resource.pk},
                        task_id=str(uuid4()))

    def is_to_synchronized(self, resource):
        return {
            'never': None,
            'daily': True,
            'weekly': NOW.isoweekday() == 1,
            'bimonthly': NOW.day in (1, 15),
            'monthly': NOW.day == 1,
            'quarterly': NOW.day == 1 and NOW.month in (1, 4, 7, 10),
            'biannual': NOW.day == 1 and NOW.month in (1, 7),
            'annual': NOW.day == 1 and NOW.month == 1
            }.get(resource.sync_frequency, None)
