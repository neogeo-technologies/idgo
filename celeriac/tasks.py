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


from celeriac.apps import app as celery_app
from celeriac.models import TaskTracking
from celery.signals import before_task_publish
from celery.signals import task_postrun
from django.utils import timezone
from idgo_admin.models import Resource
from uuid import UUID


@before_task_publish.connect
def on_beforehand(headers=None, body=None, sender=None, **kwargs):
    TaskTracking.objects.create(
        uuid=UUID(body.get('id')), task=body.get('task'), detail=body)


@task_postrun.connect
def on_task_postrun(state=None, task_id=None, task=None,
                    signal=None, sender=None, retval=None, **kwargs):
    ttracking = TaskTracking.objects.get(uuid=UUID(task_id))

    state = {
        'UNKNOWN': 'unknown',
        'FAILURE': 'failed',
        'SUCCESS': 'succesful',
        }.get(state)
    ttracking.state = state

    if isinstance(retval, Exception):
        ttracking.detail = {**ttracking.detail, **{'error': retval.__str__()}}

    ttracking.end = timezone.now()
    ttracking.save()


# =====================
# DÉFINITION DES TÂCHES
# =====================


@celery_app.task()
def save_resource(*args, pk=None, **kwargs):
    resource = Resource.objects.get(pk=pk)
    resource.save(current_user=None, synchronize=True)


@celery_app.task()
def sync_resources(*args, **kwargs):
    resources = Resource.objects.filter(**kwargs)
    for resource in resources:
        save_resource.apply_async(kwargs={'pk': resource.pk})
