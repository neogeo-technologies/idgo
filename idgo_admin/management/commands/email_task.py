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

Utiliser django-celery-beat avec la tâche : `send_sync_report_mail`.
"""


import csv
from io import StringIO
import logging

from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils.timezone import datetime as tzdatetime

from idgo_admin.models import Mail
from idgo_admin.models.mail import get_admins_mails
from idgo_admin.models import Resource
from idgo_admin.models import Task

from idgo_admin import DEFAULT_FROM_EMAIL


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """Envoyer un e-mail contenant les dernières Tasks exécutées ;
              par exemple suite un une synchronisation des ressources exécutée
              avec le script `sync_resources`."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):

        # monday = '{} {} 1'.format(ISO_CALENDAR[0], ISO_CALENDAR[1])
        # query = Task.objects.filter(
        #     starting__gte=datetime.fromtimestamp(
        #         time.mktime(time.strptime(monday, '%Y %W %w'))))
        query = Task.objects.filter(starting__gte=tzdatetime.today().date())

        data = [('state', 'starting', 'end', 'dataset_id', 'dataset_name',
                 'resource_id', 'resource_name', 'error')]
        for item in query:
            resource = Resource.objects.get(id=item.extras['resource'])
            dataset = resource.dataset
            data.append((
                item.state, item.starting.isoformat(),
                item.end.isoformat(), dataset.id, dataset.title,
                resource.id, resource.title, item.extras.get('error', None)))

        f = StringIO()
        csv.writer(f).writerows(data)

        mail_instance = Mail.objects.get(template_name='email_task')

        mail = EmailMessage(
            mail_instance.subject, mail_instance.message,
            DEFAULT_FROM_EMAIL, get_admins_mails())
        mail.attach('log.csv', f.getvalue(), 'text/csv')
        mail.send()
