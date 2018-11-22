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

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from idgo_admin.models import Organisation

TODAY = timezone.now().date()


class Order(models.Model):

    STATUS_CHOICES = (
        (0, "En cours"),
        (1, "Validée"),
        (2, "Refusée"))

    date = models.DateField(
        verbose_name='Date de la demande', 
        null=True,
        default=TODAY
        )

    status = models.IntegerField(
        verbose_name='Staut de la demande',
        default=0,
        choices=STATUS_CHOICES
        )

    applicant = models.ForeignKey(
        User, on_delete=models.CASCADE,
        verbose_name='Demandeur'
        )

    organisation = models.ForeignKey(
        Organisation,
        verbose_name='Organisation*'
        )

    dpo_cnil = models.FileField(
        upload_to='commandes/',
        verbose_name='DPO CNIL*')

    acte_engagement = models.FileField(
        upload_to='commandes/',
        verbose_name="Acte d'engagement*")

    class Meta(object):
        verbose_name = 'Commande de fichiers fonciers'
        verbose_name_plural = 'Commandes de fichiers fonciers'
