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


import csv
from dateutil.relativedelta import relativedelta
from io import StringIO
from uuid import UUID

from celeriac.apps import app as celery_app
from celeriac.models import TaskTracking
from celery.signals import before_task_publish
from celery.signals import task_postrun
from celery.utils.log import get_task_logger

from django.core.mail import EmailMessage
from django.utils import timezone

from idgo_admin.ckan_module import CkanHandler
from idgo_admin.models import AsyncExtractorTask
from idgo_admin.models import Category
from idgo_admin.models import Mail
from idgo_admin.models.mail import get_admins_mails
from idgo_admin.models import Resource

from idgo_admin import DEFAULT_FROM_EMAIL


logger = get_task_logger(__name__)


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
def clean_tasktracking_table(*args, **kwargs):
    TaskTracking.objects.filter(**kwargs).delete()


@celery_app.task()
def save_resource(*args, pk=None, **kwargs):
    resource = Resource.objects.get(pk=pk)
    resource.save(current_user=None, synchronize=True)


@celery_app.task()
def sync_resources(*args, **kwargs):
    resources = Resource.objects.filter(synchronisation=True, **kwargs)
    logger.debug(
        "Synchronize %s >> %s" % (
            str(kwargs), str([(r.pk, r.dataset.pk) for r in resources])
            )
        )
    for resource in resources:
        save_resource.apply_async(kwargs={'pk': resource.pk})


@celery_app.task()
def check_resources_last_update(*args, **kwargs):

    delta_map = {
        '5mn': relativedelta(minutes=5),
        '15mn': relativedelta(minutes=15),
        '20mn': relativedelta(minutes=20),
        '30mn': relativedelta(minutes=30),
        '1hour': relativedelta(hours=1),
        '3hours': relativedelta(hours=3),
        '6hours': relativedelta(hours=6),
        'daily': relativedelta(days=1),
        'weekly': relativedelta(days=7),
        'bimonthly': relativedelta(days=15),
        'monthly': relativedelta(months=1),
        'quarterly': relativedelta(months=3),
        'biannual': relativedelta(months=6),
        'annual': relativedelta(year=1),
        }

    data = []
    for resource in Resource.objects.filter(**kwargs):
        delta = delta_map.get(resource.sync_frequency)
        if not delta:
            continue

        delay = timezone.now() - (resource.last_update + delta)
        if delay.total_seconds() > 0:
            row = (
                resource.dataset.slug,
                resource.ckan_id,
                resource.sync_frequency,
                resource.last_update,
                delay,
                )
            data.append(row)

    if not data:
        return
    # else:

    col = (
        'dataset_slug',
        'resource_uuid',
        'sync_frequency',
        'last_update',
        'delay',
        )
    data.insert(0, col)

    f = StringIO()
    csv.writer(f).writerows(data)

    mail_instance = Mail.objects.get(template_name='resources_update_with_delay')
    mail = EmailMessage(
        mail_instance.subject, mail_instance.message,
        DEFAULT_FROM_EMAIL, get_admins_mails())
    mail.attach('log.csv', f.getvalue(), 'text/csv')
    mail.send()


@celery_app.task()
def sync_categories():
    for category in Category.objects.all():
        if not CkanHandler.is_group_exists(category.slug):
            CkanHandler.add_group(category)


@celery_app.task()
def sync_extractor_tasks():
    for instance in AsyncExtractorTask.objects.filter(success=None):
        logger.info('Check extractor task: %s' % str(instance.uuid))
