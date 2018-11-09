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


import csv
# from datetime import datetime
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils.timezone import datetime as tzdatetime
from idgo_admin.models import Mail
from idgo_admin.models.mail import get_admin_mails
from idgo_admin.models import Resource
from idgo_admin.models import Task
from io import StringIO
# import time


TODAY = tzdatetime.today().date()
# ISO_CALENDAR = datetime.now().isocalendar()


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
        query = Task.objects.filter(starting__gte=TODAY)

        data = [('state', 'starting', 'end', 'dataset_id', 'dataset_name',
                 'resource_id', 'resource_name', 'error')]
        for item in query:
            resource = Resource.objects.get(id=item.extras['resource'])
            dataset = resource.dataset
            data.append((
                item.state, item.starting.isoformat(),
                item.end.isoformat(), dataset.id, dataset.name,
                resource.id, resource.name, item.extras.get('error', None)))

        f = StringIO()
        csv.writer(f).writerows(data)

        mail_instance = Mail.objects.get(template_name='email_task')

        mail = EmailMessage(
            mail_instance.subject, mail_instance.message,
            mail_instance.from_email, get_admin_mails())
        mail.attach('log.csv', f.getvalue(), 'text/csv')
        mail.send()
