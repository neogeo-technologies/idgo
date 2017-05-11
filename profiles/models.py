import requests
from datetime import timedelta

from django.db import models
from django.contrib.gis.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.db import IntegrityError
from django.db.models.signals import pre_save, post_save, pre_delete, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.postgres.fields import JSONField

from .ldap_module import LdapHandler as ldap
from .ckan_module import CkanHandler as ckan


class OrganisationType(models.Model):

    name = models.CharField("Dénomination", max_length=50)
    code = models.CharField("Code", max_length=3)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Type d'organisation"
        verbose_name_plural = "Types d'organisations"


class Organisation(models.Model):

    name = models.CharField("Nom", max_length=150, unique=True, db_index=True)
    organisation_type = models.ForeignKey(OrganisationType, verbose_name="Type d'organisme")
    code_insee = models.CharField("Code INSEE", max_length=20, unique=True, db_index=True)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, blank=True, null=True, verbose_name="Organisation parente")
    geom = models.MultiPolygonField("Territoire", srid=4171, blank=True, null=True)
    sync_in_ldap = models.BooleanField("Synchronisé dans le LDAP", default=False)
    sync_in_ckan = models.BooleanField("Synchronisé dans CKAN", default=False)
    ckan_slug = models.SlugField("CKAN ID", max_length=150, unique=True, db_index=True)
    website = models.URLField("Site web", blank=True)
    objects = models.GeoManager()

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.id:
            created = False
            self.sync_in_ckan = ckan.test_organization(self)
        else:
            created = True
            self.ckan_slug = slugify(self.name)
            # now try to push this organization to CKAN ..
            self.sync_in_ckan = ckan.add_organization(self)

        # first save which sets the id we need to generate a LDAP gidNumber
        super(Organisation, self).save(*args, **kwargs)
        self.sync_in_ldap = ldap.sync_object("organisations", self.name, self.id + settings.LDAP_ORGANISATION_ID_INCREMENT, "add_or_update")
        # then save the current LDAP sync result
        super(Organisation, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        res = ldap.sync_object("organisations", self.name, self.id + settings.LDAP_ORGANISATION_ID_INCREMENT, "delete")
        res_ckan = ckan.del_organization(self)
        if res and res_ckan:
            super(Organisation, self).delete()


def deltatime_2_days():
    return timezone.now() + timezone.timedelta(days=2)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, verbose_name="Organisme d'appartenance", blank=True, null=True)
    phone = models.CharField('Téléphone', max_length=10, blank=True, null=True)
    role = models.CharField('Fonction', max_length=150, blank=True, null=True)

    # activation_key = models.CharField(max_length=40, blank=True)
    # key_expires = models.DateTimeField(default=deltatime_2_days, blank=True, null=True)
    # address = models.CharField("Adresse", max_length=150, blank=True)
    # city = models.CharField("Ville", max_length=150, blank=True)
    # zipcode = models.CharField("Code Postal", max_length=5, blank=True)
    # country = models.CharField("Pays", max_length=100, blank=True)

    def __str__(self):
        return self.user.username

    def save(self, *args, **kwargs):
        # first save which sets the id we need to generate a LDAP gidNumber
        super(Profile, self).save(*args, **kwargs)
        # ckan.add_user_to_organization(cn, self.organisation)
        ldap.add_user_to_group(self.user, 'cn={0},ou=organisations,dc=idgo,dc=local'.format(self.organisation.name))
        try:
            ldap.add_user_to_group(self.user, 'cn=active,ou=groups,dc=idgo,dc=local')
            ldap.add_user_to_group(self.user, 'cn=staff,ou=groups,dc=idgo,dc=local')
            ldap.add_user_to_group(self.user, 'cn=superuser,ou=groups,dc=idgo,dc=local')
            ldap.add_user_to_group(self.user, 'cn=enabled,ou=django,ou=groups,dc=idgo,dc=local')
        except:
            pass

class Registration(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activation_key = models.CharField(max_length=40, blank=True)
    key_expires = models.DateTimeField(
                        default=deltatime_2_days, blank=True, null=True)
    profile_fields = JSONField('Champs profile', blank=True, null=True)


class Application(models.Model):

    name = models.CharField('Nom', max_length=150, unique=True, db_index=True)
    short_name = models.CharField(
                        'Nom abrégé', max_length=20, unique=True, db_index=True)
    url = models.URLField('URL publique', blank=True)
    host = models.CharField('Serveur interne', max_length=50, blank=True)
    sync_in_ldap = models.BooleanField(
                        'Synchronisé dans le LDAP', default=False)
    users = models.ManyToManyField(User, verbose_name='Utilisateurs')

    def save(self, *args, **kwargs):
        # first save which sets the id we need to generate a LDAP gidNumber
        super(Application, self).save(*args, **kwargs)
        self.sync_in_ldap = ldap.sync_object('applications', self.short_name, self.id + settings.LDAP_APPLICATION_ID_INCREMENT, 'add_or_update')
        # then save the current LDAP sync result
        super(Application, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        res = ldap.sync_object('organisations', self.short_name, self.id + settings.LDAP_APPLICATION_ID_INCREMENT, 'delete')
        if res:
            super(Application, self).delete()


# Signaux


@receiver(pre_save, sender=User)
def is_existing_user(sender, instance, **kwargs):
    if ckan.is_user_exists(instance) \
            or ldap.is_user_exists(instance):
        raise IntegrityError('User {0} already exists.'.format(
                                                        instance.username))


@receiver(pre_delete, sender=User)
def delete_user_in_externals(sender, instance, **kwargs):
    ldap.del_user(instance)
    ckan.del_user(instance)  # ->state='deleted'


@receiver(pre_save, sender=Profile)
def update_externals(sender, instance, **kwargs):
    if instance.id:
        old_instance = Profile.objects.get(pk=instance.id)
        if old_instance.organisation.name != instance.organisation.name:
            ckan.del_user_from_organization(
                                    instance.user, old_instance.organisation)
            group_dn = 'cn={0},ou=organisations,dc=idgo,dc=local'.format(
                                                old_instance.organisation.name)
            ldap.del_user_from_group(instance.user, group_dn)


@receiver(pre_save, sender=Profile)
def delete_user_expire_date(sender, instance, **kwargs):
    expired_key_reg = Registration.objects.filter(key_expires__lte=timezone.now())
    for reg in expired_key_reg:
        u = reg.user
        u.delete()


@receiver(post_save, sender=User)
def create_registration(sender, instance, **kwargs):
    attrs_needed = ['_profile_fields', '_activation_key']
    if all(hasattr(instance, attr) for attr in attrs_needed):
        Registration.objects.create(
            user=instance,
            activation_key=instance._activation_key,
            profile_fields=instance._profile_fields)


# @receiver(pre_delete, sender=User)
# def clean_registration(sender, instance, **kwargs):
#     Registration.objects.filter(user=instance).delete()