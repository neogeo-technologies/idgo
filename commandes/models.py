from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from idgo_admin.models import Organisation

TODAY = timezone.now().date()

#objects = models.Manager()


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
        #max_length=30,
        choices=STATUS_CHOICES
        )

    applicant = models.ForeignKey(
        User, on_delete=models.CASCADE,
        verbose_name='Demandeur'
        )

    organisation = models.ForeignKey(
        Organisation,
        verbose_name='Organisation'
        )

    dpo_cnil = models.FileField(upload_to='commandes/')

    acte_engagement = models.FileField(upload_to='commandes/')

    class Meta(object):
        verbose_name = 'Commande de fichiers fonciers'
        verbose_name_plural = 'Commandes de fichiers fonciers'