from django.db import models
from django import forms
from django.utils import timezone
from django.contrib.auth.models import User
from django.apps import apps
from django.conf import settings
from idgo_admin.models import Organisation
from django.core.exceptions import ValidationError

TODAY = timezone.now().date()

objects = models.Manager()

class Order(models.Model):

    STATUS_CHOICES=(
    (1, "En cours"),
    (2, "Validée"),
    (3, "Refusée"))

    date = models.DateField(
        verbose_name = 'Date de la demande',  null=True, default=TODAY)

    status = models.CharField(
        verbose_name='Staut de la demande', default=1,
        max_length=30, choices=STATUS_CHOICES)

    applicant = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name='Demandeur')
    
    organisation = models.ForeignKey(
        Organisation, verbose_name='Organisation'
    )

    dpo_cnil = models.FileField()

    acte_engagement = models.FileField()

    class Meta(object):
        verbose_name='Commande de fichiers fonciers'
        verbose_name_plural='Commandes de fichiers fonciers'
    

    