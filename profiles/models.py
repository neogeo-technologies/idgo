from django.db import models
from django.db.models.signals import pre_delete, pre_save
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

from .ldap_module import LdapHandler as ldap
from .ckan_module import CkanHandler as ckan


def deltatime_2_days():
    return timezone.now() + timezone.timedelta(days=2)


class OrganisationType(models.Model):

    name = models.CharField('Dénomination', max_length=50)
    code = models.CharField('Code', max_length=3)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Type d'organisation"
        verbose_name_plural = "Types d'organisations"


class Organisation(models.Model):

    name = models.CharField('Nom', max_length=150, unique=True, db_index=True)
    organisation_type = models.ForeignKey(
                OrganisationType, verbose_name="Type d'organisme", default='1')
    code_insee = models.CharField(
                'Code INSEE', max_length=20, unique=True, db_index=True)
    parent = models.ForeignKey(
                'self', on_delete=models.CASCADE, blank=True,
                null=True, verbose_name="Organisation parente")
    geom = models.MultiPolygonField(
                'Territoire', srid=4171, blank=True, null=True)
    sync_in_ldap = models.BooleanField(
                'Synchronisé dans le LDAP', default=False)
    sync_in_ckan = models.BooleanField(
                'Synchronisé dans CKAN', default=False)
    ckan_slug = models.SlugField(
                'CKAN ID', max_length=150, unique=True, db_index=True)
    website = models.URLField('Site web', blank=True)
    email = models.EmailField(verbose_name="Adresse mail de l'organisation")
    objects = models.GeoManager()

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):

        if self.id:
            self.sync_in_ckan = ckan.is_organization_exists(self.ckan_slug)
        else:
            self.ckan_slug = slugify(self.name)
            try:
                ckan.add_organization(self)
            except:
                self.sync_in_ckan = False
            else:
                self.sync_in_ckan = True

        # first save which sets the id we need to generate a LDAP gidNumber
        super().save(*args, **kwargs)

        self.sync_in_ldap = ldap.sync_object(
            'organisations', self.name,
            self.id + settings.LDAP_ORGANISATION_ID_INCREMENT, 'add_or_update')

        # then save the current LDAP sync result
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):

        res = ldap.sync_object(
            'organisations', self.name,
            self.id + settings.LDAP_ORGANISATION_ID_INCREMENT, 'delete')

        res_ckan = ckan.del_organization(self.ckan_slug)
        if res and res_ckan:
            super().delete()


class Profile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, blank=True, null=True,
                                     verbose_name="Organisme d'appartenance")
    publish_for = models.ManyToManyField(
                        Organisation, related_name='pub_org',
                        verbose_name='Organisme associé',
                        help_text='Liste des organismes pour lesquels '
                                  "l'utilisateur publie des jeux de données.")
    phone = models.CharField('Téléphone', max_length=10, blank=True, null=True)
    role = models.CharField('Fonction', max_length=150, blank=True, null=True)

    def __str__(self):
        return self.user.username


class PublishRequest(models.Model):

    user = models.ForeignKey(User, verbose_name='Utilisateur')
    organisation = models.ForeignKey(
                            Organisation, verbose_name='Organisme',
                            help_text='Organisme pour lequel le '
                                      'statut de contributeur est demandé')
    date_demande = models.DateField(verbose_name='Date de la demande',
                                    auto_now_add=timezone.now())
    date_acceptation = models.DateField(verbose_name='Date acceptation',
                                        blank=True, null=True)

    # prévoir une action externe ACCEPTER renseignant la date d'acceptation et enregistrant l'orga dans le publish_for du User.

    def save(self, *args, **kwargs):
        if not self.id:
            # alerter les administrateurs (is_superuser=True par mail qu'une demande est déposée
            # = message + liens vers ici (via admin django standard)
            a = 0
        super(PublishRequest, self).save(*args, **kwargs)


class Registration(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activation_key = models.CharField(max_length=40, blank=True)
    key_expires = models.DateTimeField(
                        default=deltatime_2_days, blank=True, null=True)
    profile_fields = JSONField('Champs profile', blank=True, null=True)


# Triggers


@receiver(pre_delete, sender=User)
def delete_user_in_externals(sender, instance, **kwargs):
    ldap.del_user(instance.username)
    ckan.del_user(instance.username)  # ->state='deleted'


@receiver(pre_save, sender=Profile)
def update_externals(sender, instance, **kwargs):
    if instance.id:
        old_instance = Profile.objects.get(pk=instance.id)
        if old_instance.organisation.name != instance.organisation.name:
            ckan.del_user_from_organization(
                    instance.user.username, old_instance.organisation.ckan_slug)
            ldap.del_user_from_organization(
                    instance.user.username, old_instance.organisation.ckan_slug)


@receiver(pre_save, sender=Profile)
def delete_user_expire_date(sender, instance, **kwargs):
    expired_key_reg = Registration.objects.filter(
                                            key_expires__lte=timezone.now())
    for reg in expired_key_reg:
        u = reg.user
        u.delete()
