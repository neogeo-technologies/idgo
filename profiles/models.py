from .ckan_module import CkanHandler as ckan
from .ldap_module import LdapHandler as ldap
from django.conf import settings
from django.contrib.auth.models import User
# from django.db import models  # ???
from django.db.models.signals import post_save
from django.db.models.signals import pre_delete
from django.db.models.signals import pre_save
from django.contrib.gis.db import models  # TODO(@m431m)
from django.contrib.postgres.fields import JSONField
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils import timezone
import uuid


def deltatime_2_days():
    return timezone.now() + timezone.timedelta(days=2)


class OrganisationType(models.Model):

    name = models.CharField('Dénomination', max_length=50)
    code = models.CharField('Code', max_length=3)

    class Meta(object):
        verbose_name = "Type d'organisation"
        verbose_name_plural = "Types d'organisations"

    def __str__(self):
        return self.name


class Organisation(models.Model):

    STATUS_CHOICES = (
        ('commune', 'Commune'),
        ('communaute_de_communes', 'Communauté de Commune'),
        ('communaute_d_agglomeration', "Communauté d'Agglomération"),
        ('communaute_urbaine', 'Communauté Urbaine'),
        ('metrople', 'Métropoles'),
        ('conseil_departemental', 'Conseil Départemental'),
        ('conseil_regional', 'Conseil Régional'),
        ('organisme_de_recherche', 'Organisme de recherche'),
        ('universite', 'Université'))

    FINANCEUR_CHOICES = (
        ('etat', 'Etat'),
        ('region_PACA', 'Région PACA'),
        ('epci', 'EPCI'),
        ('cd02', 'CD02'))

    name = models.CharField('Nom', max_length=150, unique=True, db_index=True)
    organisation_type = models.ForeignKey(
        OrganisationType, verbose_name="Type d'organisme", default='1')
    code_insee = models.CharField(
        'Code INSEE', max_length=20, unique=False, db_index=True)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, blank=True,
        null=True, verbose_name="Organisation parente")

    # Territoire de compétence
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

    # Nouveaux Champs à valider:
    # communes = models.ManyToManyField(Commune) # Territoires de compétence
    # id_url_unique = models.URLField('URL unique', blank=True)
    # titre = models.CharField('Nom', max_length=100, unique=True)  # Titre CKAN
    # description = models.CharField('Description', max_length=1024, blank=True, null=True)  # Description CKAN
    # Logo = models.ImageField('Logo')
    # statut = models.CharField('Statut', blank=True, null=True, default='conseil_regional',
    #                           max_length=30, choices=STATUS_CHOICES)
    # financeur = models.CharField('Financeur', blank=True, null=True, default='conseil_regional',
    #                           max_length=30, choices=FINANCEUR_CHOICES)

    def __str__(self):
        return self.name

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
        Organisation, related_name='pub_org', verbose_name='Organisme associé',
        help_text='Liste des organismes pour lesquels '
                  "l'utilisateur publie des jeux de données.")
    phone = models.CharField('Téléphone', max_length=10, blank=True, null=True)
    role = models.CharField('Fonction', max_length=150, blank=True, null=True)

    def __str__(self):
        return self.user.username


class PublishRequest(models.Model):  # Demande de contribution

    user = models.ForeignKey(User, verbose_name='Utilisateur')
    organisation = models.ForeignKey(
        Organisation, verbose_name='Organisme',
        help_text='Organisme pour lequel le '
        'statut de contributeur est demandé')

    date_demande = models.DateField(verbose_name='Date de la demande',
                                    auto_now_add=timezone.now())
    date_acceptation = models.DateField(verbose_name='Date acceptation',
                                        blank=True, null=True)
    pub_req_key = models.UUIDField(default=uuid.uuid4, editable=False)


class Registration(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # User validation email
    activation_key = models.UUIDField(default=uuid.uuid4, editable=False)
    # Admin validation profile
    affiliate_orga_key = models.UUIDField(default=uuid.uuid4, editable=False)
    key_expires = models.DateTimeField(default=deltatime_2_days,
                                       blank=True, null=True)
    profile_fields = JSONField('Champs profile', blank=True, null=True)
    date_validation_user = models.DateField(
            verbose_name="Date validation par l'utilisateur",
            blank=True, null=True)
    date_affiliate_admin = models.DateField(
            verbose_name="Date activation par un administrateur",
            blank=True, null=True)


# Triggers


@receiver(pre_delete, sender=User)
def delete_user_in_externals(sender, instance, **kwargs):
    try:
        ldap.del_user(instance.username)
        ckan.del_user(instance.username)  # ->state='deleted'
    except Exception:
        pass


@receiver(pre_save, sender=Profile)
def update_externals(sender, instance, **kwargs):

    # TODO: Possibilité d'inscrire un profile sans organisation
    # et possiblité de modifier un abonnment apres inscription
    # et possiblité de suppremier ancienne organisation par nouvelle

    end_trigger = False
    if instance.id:
        try:
            old_instance = Profile.objects.get(pk=instance.id)
        except Profile.DoesNotExist:
            end_trigger = True

        if end_trigger is False and old_instance.organisation is None:
            end_trigger = True

        if instance.organisation is None and old_instance.organisation:
            ckan.del_user_from_organization(
                instance.user.username, old_instance.organisation.ckan_slug)
            ldap.del_user_from_organization(
                instance.user.username, old_instance.organisation.ckan_slug)
            end_trigger = True

        if end_trigger is False and \
                old_instance.organisation != instance.organisation:
            ckan.del_user_from_organization(
                instance.user.username, old_instance.organisation.ckan_slug)
            ldap.del_user_from_organization(
                instance.user.username, old_instance.organisation.ckan_slug)


@receiver(pre_save, sender=Profile)
def delete_user_expire_date(sender, instance, **kwargs):
    expired_key_reg = Registration.objects.filter(
        key_expires__lte=timezone.now()).exclude(key_expires=None)
    for reg in expired_key_reg:
        u = reg.user
        u.delete()


@receiver(pre_save, sender=Organisation)
def orga_ckan_presave(sender, instance, **kwargs):

    instance.sync_in_ckan = ckan.is_organization_exists(instance.ckan_slug)
    instance.ckan_slug = slugify(instance.name)
    try:
        ckan.add_organization(instance)
    except Exception:
        instance.sync_in_ckan = False
    else:
        instance.sync_in_ckan = True


@receiver(post_save, sender=Organisation)
def orga_ldap_postsave(sender, instance, **kwargs):
    instance.sync_in_ldap = ldap.sync_object(
        'organisations', instance.name,
        instance.id + settings.LDAP_ORGANISATION_ID_INCREMENT, 'add_or_update')
