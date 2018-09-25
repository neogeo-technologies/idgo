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


from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.db.models.signals import pre_init
from django.dispatch import receiver
from django.utils import timezone
from idgo_admin.models.mail import send_extraction_failure_mail
from idgo_admin.models.mail import send_extraction_successfully_mail
import requests
import uuid


class ExtractorSupportedFormat(models.Model):

    class Meta(object):
        verbose_name = "Format pris en charge par le service d'extraction"
        verbose_name_plural = "Formats pris en charge par le service d'extraction"

    name = models.SlugField(verbose_name='Nom', primary_key=True, editable=False)

    description = models.TextField(verbose_name='Description', unique=True)

    details = JSONField(verbose_name='Détails')

    def __str__(self):
        return self.description


class AsyncExtractorTask(models.Model):

    class Meta(object):
        verbose_name = "Tâche exécutée par l'extracteur de données"
        verbose_name_plural = "Tâches exécutées par l'extracteur de données"

    uuid = models.UUIDField(
        verbose_name='UUID', default=uuid.uuid4, primary_key=True, editable=False)

    user = models.ForeignKey(to=User, verbose_name='User')

    layer = models.ForeignKey(
        to='Layer', verbose_name='Layers', on_delete=models.CASCADE)

    success = models.NullBooleanField(verbose_name='Succès')

    submission_datetime = models.DateTimeField(
        verbose_name='Submission', null=True, blank=True)

    start_datetime = models.DateTimeField(
        verbose_name='Start', null=True, blank=True)

    stop_datetime = models.DateTimeField(
        verbose_name='Stop', null=True, blank=True)

    details = JSONField(verbose_name='Details', blank=True, null=True)

    @property
    def status(self):
        if self.success is True:
            return 'Succès'  # Terminé
        elif self.success is False:
            return 'Échec'  # En erreur
        elif self.success is None and not self.start_datetime:
            return 'En attente'
        elif self.success is None and self.start_datetime:
            return 'En cours'
        return 'Inconnu'

    @property
    def elapsed_time(self):
        if self.stop_datetime and self.success in (True, False):
            return self.stop_datetime - self.submission_datetime
        else:
            return timezone.now() - self.submission_datetime


# Triggers


@receiver(pre_init, sender=AsyncExtractorTask)
def synchronize_extractor_task(sender, *args, **kwargs):
    pre_init.disconnect(synchronize_extractor_task, sender=sender)

    doc = sender.__dict__.get('__doc__')
    if doc.startswith(sender.__name__):
        keys = doc[len(sender.__name__) + 1:-1].split(', ')
        values = kwargs.get('args')

        if len(keys) == len(values):
            kvp = dict((k, values[i]) for i, k in enumerate(keys))

            try:
                instance = AsyncExtractorTask.objects.get(uuid=kvp['uuid'])
            except AsyncExtractorTask.DoesNotExist:
                pass
            else:
                if instance.success is None:
                    url = instance.details['possible_requests']['status']['url']
                    r = requests.get(url)
                    if r.status_code == 200:
                        details = r.json()

                        instance.success = {
                            'SUCCESS': True,
                            'FAILED': False
                            }.get(details['status'], None)

                        instance.start_datetime = details.get('start_datetime', None)
                        instance.stop_datetime = details.get('start_datetime', None)
                        instance.save()

                        if instance.success is True:
                            send_extraction_successfully_mail(instance.user, instance)
                        elif instance.success is False:
                            send_extraction_failure_mail(instance.user, instance)

    pre_init.connect(synchronize_extractor_task, sender=sender)
