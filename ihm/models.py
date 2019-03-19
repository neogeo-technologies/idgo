from django.db import models


class IHMSettings(models.Model):

    TARGET_CHOICES = (
        ('ckan', "Ckan"),
        ('admin', "Admin"),
    )

    name = models.SlugField(
        verbose_name="Identifiant de l'objet",
        unique=True,
        db_index=True,
        max_length=100
    )

    contents = models.TextField(verbose_name='Contenu')

    target = models.CharField(
        verbose_name='Cible',
        max_length=100,
        blank=True,
        null=True,
        choices=TARGET_CHOICES,
        default='ckan'
    )

    class Meta:
        verbose_name = "champs IHM"
        verbose_name_plural = "Éditions des IHM"
        ordering = ("name", )

    def __str__(self):
        return str(self.name)
