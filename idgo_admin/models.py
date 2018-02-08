from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_delete
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.utils import PartialFormatter
from idgo_admin.utils import slugify as _slugify  # Pas forcement utile de garder l'original
import json
import os
from taggit.managers import TaggableManager
import uuid
# from django.contrib.auth.views import redirect_to_login


GEONETWORK_URL = settings.GEONETWORK_URL


if settings.STATIC_ROOT:
    locales_path = os.path.join(
        settings.STATIC_ROOT, 'mdedit/config/locales/fr/locales.json')
else:
    locales_path = os.path.join(
        settings.BASE_DIR,
        'idgo_admin/static/mdedit/config/locales/fr/locales.json')

try:
    with open(locales_path, 'r', encoding='utf-8') as f:
        MDEDIT_LOCALES = json.loads(f.read())

        AUTHORIZED_ISO_TOPIC = (
            (iso_topic['id'], iso_topic['value']) for iso_topic
            in MDEDIT_LOCALES['codelists']['MD_TopicCategoryCode'])

        AUTHORIZED_PROTOCOL = (
            (protocol['id'], protocol['value']) for protocol
            in MDEDIT_LOCALES['codelists']['MD_LinkageProtocolCode'])
except Exception:
    MDEDIT_LOCALES = ''
    AUTHORIZED_ISO_TOPIC = ''
    AUTHORIZED_PROTOCOL = ''


class ResourceFormats(models.Model):

    PROTOCOL_CHOICES = AUTHORIZED_PROTOCOL

    CKAN_CHOICES = (
        (None, 'N/A'),
        ('text_view', 'text_view'),
        ('geo_view', 'geo_view'),
        ('recline_view', 'recline_view'),
        ('pdf_view', 'pdf_view'))

    extension = models.CharField('Format', max_length=30, unique=True)

    ckan_view = models.CharField(
        'Vue', max_length=100, choices=CKAN_CHOICES, blank=True, null=True)

    protocol = models.CharField(
        'Protocole', max_length=100, blank=True, null=True, choices=PROTOCOL_CHOICES)

    class Meta(object):
        verbose_name = 'Format de ressource'
        verbose_name_plural = 'Formats de ressource'

    def __str__(self):
        return self.extension


def upload_resource(instance, filename):
    return _slugify(filename, exclude_dot=False)


class Resource(models.Model):

    # PENSER A SYNCHRONISER CETTE LISTE DES LANGUES
    # AVEC LE STRUCTURE DECRITE DANS CKAN
    # cf. /usr/lib/ckan/default/lib/python2.7/site-packages/ckanext/scheming/ckan_dataset.json

    LANG_CHOICES = (
        ('french', 'Français'),
        ('english', 'Anglais'),
        ('italian', 'Italien'),
        ('german', 'Allemand'),
        ('other', 'Autre'))

    TYPE_CHOICES = (
        ('data', 'Données'),
        ('resource', 'Resources'))

    LEVEL_CHOICES = (
        ('0', 'Tous les utilisateurs'),
        ('1', 'Utilisateurs authentifiés'),
        ('2', 'Utilisateurs authentifiés avec droits spécifiques'),
        ('3', 'Utilisateurs de cette organisations uniquements'),
        ('4', 'Organisations spécifiées'))

    name = models.CharField(
        verbose_name='Nom', max_length=150)

    ckan_id = models.UUIDField(
        verbose_name='Ckan UUID', default=uuid.uuid4, editable=False)

    description = models.TextField(
        verbose_name='Description', blank=True, null=True)

    referenced_url = models.URLField(
        verbose_name='Référencer une URL',
        max_length=2000, blank=True, null=True)

    dl_url = models.URLField(
        verbose_name='Télécharger depuis une URL',
        max_length=2000, blank=True, null=True)

    up_file = models.FileField(
        verbose_name='Téléverser un ou plusieurs fichiers',
        blank=True, null=True, upload_to=upload_resource)

    lang = models.CharField(
        verbose_name='Langue', choices=LANG_CHOICES,
        default='french', max_length=10)

    format_type = models.ForeignKey(
        ResourceFormats, verbose_name='Format', default=0)

    restricted_level = models.CharField(
        verbose_name="Restriction d'accès", choices=LEVEL_CHOICES,
        default='0', max_length=20, blank=True, null=True)

    profiles_allowed = models.ManyToManyField(
        to='Profile', verbose_name='Utilisateurs autorisés', blank=True)

    organisations_allowed = models.ManyToManyField(
        to='Organisation', verbose_name='Organisations autorisées', blank=True)

    dataset = models.ForeignKey(
        to='Dataset', verbose_name='Jeu de données',
        on_delete=models.CASCADE, blank=True, null=True)

    bbox = models.PolygonField(
        verbose_name='Rectangle englobant', blank=True, null=True)

    # Dans le formulaire de saisie, ne montrer que si AccessLevel = 2
    geo_restriction = models.BooleanField(
        verbose_name='Restriction géographique', default=False)

    created_on = models.DateTimeField(
        verbose_name='Date de création de la resource',
        blank=True, null=True, default=timezone.now)

    last_update = models.DateTimeField(
        verbose_name='Date de dernière modification de la resource',
        blank=True, null=True)

    data_type = models.CharField(
        verbose_name='type de resources',
        choices=TYPE_CHOICES, max_length=10)

    class Meta(object):
        verbose_name = 'Ressource'

    def __str__(self):
        return self.name


class Commune(models.Model):

    code = models.CharField(
        verbose_name='Code INSEE', max_length=5)

    name = models.CharField(
        verbose_name='Nom', max_length=100)

    geom = models.MultiPolygonField(
        verbose_name='Geometrie', srid=2154, blank=True, null=True)

    objects = models.GeoManager()

    class Meta(object):
        ordering = ['name']

    def __str__(self):
        return self.name


class Jurisdiction(models.Model):

    code = models.CharField(verbose_name='Code INSEE', max_length=10)

    name = models.CharField(verbose_name='Nom', max_length=100)

    communes = models.ManyToManyField(to='Commune')

    objects = models.GeoManager()

    class Meta(object):
        verbose_name = 'Territoire de compétence'

    def __str__(self):
        return self.name


class Financier(models.Model):

    name = models.CharField('Nom du financeur', max_length=250)

    code = models.CharField('Code du financeur', max_length=250)

    class Meta(object):
        verbose_name = "Financeur d'une organisation"
        verbose_name_plural = "Financeurs"
        ordering = ('name', )

    def __str__(self):
        return self.name


class OrganisationType(models.Model):

    name = models.CharField(verbose_name="Type d'organisation", max_length=250)

    code = models.CharField(verbose_name="Code", max_length=250)

    class Meta(object):
        verbose_name = "Type d'organisation"
        verbose_name_plural = "Types d'organisations"
        ordering = ('name', )

    def __str__(self):
        return self.name


class Organisation(models.Model):

    name = models.CharField(
        verbose_name='Nom', max_length=150, unique=True, db_index=True)

    organisation_type = models.ForeignKey(
        to='OrganisationType', verbose_name="Type d'organisation",
        default='1', blank=True, null=True, on_delete=models.SET_NULL)

    # Territoire de compétence
    jurisdiction = models.ForeignKey(
        to='Jurisdiction', blank=True, null=True,
        verbose_name="Territoire de compétence")

    ckan_slug = models.SlugField(
        verbose_name='CKAN ID', max_length=150, unique=True, db_index=True)

    ckan_id = models.UUIDField(
        verbose_name='Ckan UUID', default=uuid.uuid4, editable=False)

    website = models.URLField(verbose_name='Site web', blank=True)

    email = models.EmailField(
        verbose_name="Adresse mail de l'organisation", blank=True, null=True)

    description = models.TextField(
        verbose_name='Description', blank=True, null=True)

    logo = models.ImageField(
        verbose_name='Logo', upload_to='logos/', blank=True, null=True)

    address = models.CharField(
        verbose_name='Adresse', max_length=100, blank=True, null=True)

    postcode = models.CharField(
        verbose_name='Code postal', max_length=100, blank=True, null=True)

    city = models.CharField(
        verbose_name='Ville', max_length=100, blank=True, null=True)

    org_phone = models.CharField(
        verbose_name='Téléphone', max_length=10, blank=True, null=True)

    license = models.ForeignKey(
        to='License', on_delete=models.CASCADE,
        verbose_name='Licence', blank=True, null=True)

    financier = models.ForeignKey(
        to='Financier', on_delete=models.SET_NULL,
        verbose_name="Financeur", blank=True, null=True)

    is_active = models.BooleanField('Organisation active', default=False)

    class Meta(object):
        ordering = ['name']

    def __str__(self):
        return self.name


class Profile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    organisation = models.ForeignKey(
        to='Organisation', on_delete=models.SET_NULL,
        verbose_name="Organisation d'appartenance", blank=True, null=True)

    referents = models.ManyToManyField(
        to='Organisation', through='LiaisonsReferents',
        verbose_name="Organisations dont l'utiliateur est réferent",
        related_name='profile_referents')

    contributions = models.ManyToManyField(
        to='Organisation', through='LiaisonsContributeurs',
        verbose_name="Organisations dont l'utiliateur est contributeur",
        related_name='profile_contributions')

    resources = models.ManyToManyField(
        to='Resource', through='LiaisonsResources',
        verbose_name="Resources publiées par l'utilisateur",
        related_name='profile_resources')

    phone = models.CharField(
        verbose_name='Téléphone', max_length=10, blank=True, null=True)

    is_active = models.BooleanField(
        verbose_name='Validation suite à confirmation mail par utilisateur',
        default=False)

    membership = models.BooleanField(
        verbose_name="Etat de rattachement profile-organisation d'appartenance",
        default=False)

    is_admin = models.BooleanField(
        verbose_name="Administrateur IDGO",
        default=False)

    class Meta(object):
        verbose_name = 'Profil utilisateur'
        verbose_name_plural = 'Profils des utilisateurs'

    def __str__(self):
        return self.user.username

    def nb_datasets(self, organisation):
        return Dataset.objects.filter(
            editor=self.user, organisation=organisation).count()

    def get_roles(self, organisation=None, dataset=None):

        if organisation:
            is_referent = LiaisonsReferents.objects.filter(
                profile=self,
                organisation=organisation,
                validated_on__isnull=False).exists()
        else:
            is_referent = LiaisonsReferents.objects.filter(
                profile=self,
                validated_on__isnull=False).exists()

        return {"is_admin": self.is_admin,
                "is_referent": is_referent,
                "is_editor": (self.user == dataset.editor) if dataset else False}

    # @classmethod
    # def active_users(cls):
    #     active_profiles = Profile.objects.filter(is_active=True)
    #     return User.objects.filter(pk__in=[])


class LiaisonsReferents(models.Model):

    profile = models.ForeignKey(
        to='Profile', on_delete=models.CASCADE,
        verbose_name='Profil')

    organisation = models.ForeignKey(
        to='Organisation', on_delete=models.CASCADE,
        verbose_name='Organisation')

    created_on = models.DateField(auto_now_add=True)

    validated_on = models.DateField(
        verbose_name="Date de validation de l'action",
        blank=True, null=True, default=timezone.now)

    class Meta(object):
        unique_together = (('profile', 'organisation'),)

    def __str__(self):
        return '{full_name} ({username})--{organisation}'.format(
            full_name=self.profile.user.get_full_name(),
            username=self.profile.user.username,
            organisation=self.organisation.name)

    @classmethod
    def get_subordinated_organizations(cls, profile):
        if profile.is_admin:
            return Organisation.objects.filter(is_active=True)
        return [e.organisation for e
                in LiaisonsReferents.objects.filter(
                    profile=profile, validated_on__isnull=False)]

    @classmethod
    def get_pending(cls, profile):
        return [e.organisation for e
                in LiaisonsReferents.objects.filter(
                    profile=profile, validated_on=None)]


class LiaisonsContributeurs(models.Model):

    profile = models.ForeignKey(
        to='Profile', on_delete=models.CASCADE)

    organisation = models.ForeignKey(
        to='Organisation', on_delete=models.CASCADE)

    created_on = models.DateField(auto_now_add=True)

    validated_on = models.DateField(
        verbose_name="Date de validation de l'action", blank=True, null=True)

    class Meta(object):
        unique_together = (('profile', 'organisation'),)

    def __str__(self):
        return '{full_name} ({username})--{organisation}'.format(
            full_name=self.profile.user.get_full_name(),
            username=self.profile.user.username,
            organisation=self.organisation.name)

    @classmethod
    def get_contribs(cls, profile):
        return [e.organisation for e
                in LiaisonsContributeurs.objects.filter(
                    profile=profile, validated_on__isnull=False)]

    @classmethod
    def get_contributors(cls, organization):
        return [e.profile for e
                in LiaisonsContributeurs.objects.filter(
                    organisation=organization, validated_on__isnull=False)]

    @classmethod
    def get_pending(cls, profile):
        return [e.organisation for e
                in LiaisonsContributeurs.objects.filter(
                    profile=profile, validated_on=None)]


class LiaisonsResources(models.Model):

    profile = models.ForeignKey(to='Profile', on_delete=models.CASCADE)

    resource = models.ForeignKey(to='Resource', on_delete=models.CASCADE)

    created_on = models.DateField(auto_now_add=True)

    validated_on = models.DateField(
        verbose_name="Date de validation de l'action", blank=True, null=True)


class AccountActions(models.Model):

    ACTION_CHOICES = (
        ('confirm_mail', "Confirmation de l'email par l'utilisateur"),
        ('confirm_new_organisation', "Confirmation par un administrateur de la création d'une organisation par l'utilisateur"),
        ('confirm_rattachement', "Rattachement d'un utilisateur à une organsiation par un administrateur"),
        ('confirm_referent', "Confirmation du rôle de réferent d'une organisation pour un utilisatur par un administrateur"),
        ('confirm_contribution', "Confirmation du rôle de contributeur d'une organisation pour un utilisatur par un administrateur"),
        ('reset_password', "Réinitialisation du mot de passe"),
        ('set_password_admin', "Initialisation du mot de passe suite à une inscription par un administrateur"))

    profile = models.ForeignKey(
        to='Profile', on_delete=models.CASCADE, blank=True, null=True)

    # Pour pouvoir reutiliser AccountActions pour demandes post-inscription
    org_extras = models.ForeignKey(
        to='Organisation', on_delete=models.CASCADE, blank=True, null=True)

    key = models.UUIDField(default=uuid.uuid4, editable=False)

    action = models.CharField(
        verbose_name='Action de gestion de profile', blank=True, null=True,
        default='confirm_mail', max_length=250, choices=ACTION_CHOICES)

    created_on = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    closed = models.DateTimeField(
        verbose_name="Date de validation de l'action",
        blank=True, null=True)


class Mail(models.Model):

    template_name = models.CharField(
        verbose_name='Nom du model du message',
        primary_key=True, max_length=255)

    subject = models.CharField(
        verbose_name='Objet', max_length=255, blank=True, null=True)

    message = models.TextField(
        verbose_name='Corps du message', blank=True, null=True)

    from_email = models.EmailField(
        verbose_name='Adresse expediteur',
        default=settings.DEFAULT_FROM_EMAIL)

    class Meta(object):
        verbose_name = 'e-mail'
        verbose_name_plural = 'e-mails'

    def __str__(self):
        return self.template_name

    @classmethod
    def superuser_mails(cls, receip_list):
        receip_list = receip_list + [
            usr.email for usr in User.objects.filter(
                is_superuser=True, is_active=True)]
        return receip_list

    @classmethod
    def admin_mails(cls, receip_list):
        receip_list = receip_list + [
            p.user.email for p in Profile.objects.filter(
                is_active=True, is_admin=True)]
        return receip_list

    @classmethod
    def referents_mails(cls, receip_list, organisation):
        receip_list = receip_list + [
            lr.profile.user.email for lr in LiaisonsReferents.objects.filter(
                organisation=organisation, validated_on__isnull=False)]
        return receip_list

    @classmethod
    def receivers_list(cls, organisation=None):
        receip_list = []
        receip_list = cls.superuser_mails(receip_list)
        receip_list = cls.admin_mails(receip_list)
        if organisation:
            receip_list = cls.referents_mails(receip_list, organisation)

        # Pour retourner une liste de valeurs uniques
        return list(set(receip_list))

    @classmethod
    def send_credentials_user_creation_admin(cls, cleaned_data):
        msg_on_create = """Bonjour, {last_name}, {first_name},
Un compte vous a été créé par les services d'administarion sur la plateforme IDGO .
+ Identifiant de connexion: {username}

Veuillez initializer votre mot de passe en suivant le lien suivant.
+ Url de connexion: {url}

Ce message est envoyé automatiquement. Veuillez ne pas répondre. """
        sub_on_create = "Un nouveau compte vous a été crée sur la plateforme IDGO"

        mail_template, created = cls.objects.get_or_create(
            template_name='credentials_user_creation_admin',
            defaults={
                'message': msg_on_create,
                'subject': sub_on_create})

        fmt = PartialFormatter()
        data = {'first_name': cleaned_data.get('first_name'),
                'last_name': cleaned_data.get('last_name').upper(),
                'username': cleaned_data.get('username'),
                'url': cleaned_data.get('url')}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject, message=message,
                  from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[cleaned_data.get('email')])

    @classmethod
    def validation_user_mail(cls, request, action):

        user = action.profile.user
        mail_template = Mail.objects.get(template_name='validation_user_mail')
        from_email = mail_template.from_email
        subject = mail_template.subject

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirmation_mail',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=subject, message=message,
                  from_email=from_email, recipient_list=[user.email])

    @classmethod
    def confirmation_user_mail(cls, user):
        """E-mail de confirmation.

        E-mail confirmant la creation d'une nouvelle organisation
        suite à une inscription.
        """
        mail_template = \
            Mail.objects.get(template_name='confirmation_user_mail')

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])

    @classmethod
    def confirm_new_organisation(cls, request, action):
        """E-mail de validation.

        E-mail permettant de valider la création d'une nouvelle organisation
        suite à une inscription.
        """
        user = action.profile.user
        organisation = action.profile.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name='confirm_new_organisation')

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_new_orga',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def confirm_rattachement(cls, request, action):

        user = action.profile.user
        organisation = action.profile.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = Mail.objects.get(template_name='confirm_rattachement')

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_rattachement',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def confirm_updating_rattachement(cls, request, action):

        user = action.profile.user
        organisation = action.org_extras
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name="confirm_updating_rattachement")

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_rattachement',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def confirm_referent(cls, request, action):
        user = action.profile.user
        organisation = action.org_extras
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name="confirm_referent")

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_referent',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list())

    @classmethod
    def confirm_contribution(cls, request, action):

        user = action.profile.user
        organisation = action.org_extras
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name="confirm_contribution")

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_contribution',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def affiliate_confirmation_to_user(cls, profile):

        mail_template = \
            Mail.objects.get(template_name="affiliate_confirmation_to_user")

        fmt = PartialFormatter()
        data = {'organisation_name': profile.organisation.name}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[profile.user.email])

    @classmethod
    def confirm_contrib_to_user(cls, action):

        organisation = action.org_extras
        user = action.profile.user

        mail_template = \
            Mail.objects.get(template_name="confirm_contrib_to_user")

        fmt = PartialFormatter()
        data = {'organisation_name': organisation.name}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])

    @classmethod
    def conf_deleting_dataset_res_by_user(cls, user, dataset=None, resource=None):

        fmt = PartialFormatter()
        if dataset:
            mail_template = \
                Mail.objects.get(template_name="conf_deleting_dataset_by_user")

            data = {'dataset_name': dataset.name}

        elif resource:
            mail_template = \
                Mail.objects.get(template_name="conf_deleting_res_by_user")

            data = {'dataset_name': dataset.name,
                    'resource_name': resource.name}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])

    @classmethod
    def conf_deleting_profile_to_user(cls, user_copy):

        mail_template = \
            Mail.objects.get(template_name="conf_deleting_profile_to_user")

        fmt = PartialFormatter()
        data = {'first_name': user_copy["first_name"],
                'last_name': user_copy["last_name"],
                'username': user_copy["username"]}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user_copy["email"]])

    @classmethod
    def send_reset_password_link_to_user(cls, request, action):

        mail_template = \
            Mail.objects.get(template_name="send_reset_password_link_to_user")
        user = action.profile.user

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:password_manager',
                            kwargs={'process': 'reset', 'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])


class Category(models.Model):

    ISO_TOPIC_CHOICES = AUTHORIZED_ISO_TOPIC

    # A chaque déploiement
    # python manage.py sync_ckan_categories

    name = models.CharField(
        verbose_name='Nom', max_length=100)

    description = models.CharField(
        verbose_name='Description', max_length=1024)

    ckan_slug = models.SlugField(
        verbose_name='Ckan slug', max_length=100,
        unique=True, db_index=True, blank=True)

    ckan_id = models.UUIDField(
        verbose_name='Ckan UUID', default=uuid.uuid4, editable=False)

    iso_topic = models.CharField(
        verbose_name='Thème ISO', max_length=100,
        choices=ISO_TOPIC_CHOICES, blank=True, null=True)

    picto = models.ImageField(
        verbose_name='Pictogramme', upload_to='logos/',
        blank=True, null=True)

    class Meta(object):
        verbose_name = 'Catégorie'

    def __str__(self):
        return self.name

    def sync_ckan(self):
        if self.pk:
            ckan.update_group(self)
        else:
            ckan.add_group(self)

    def clean(self):
        self.ckan_slug = slugify(self.name)
        try:
            self.sync_ckan()
        except Exception as e:
            raise ValidationError(e.__str__())


class License(models.Model):

    # MODELE LIE AUX LICENCES CKAN. MODIFIER EGALEMENT DANS LA CONF CKAN
    # QUAND DES ELEMENTS SONT AJOUTES, il faut mettre à jour
    # le fichier /etc/ckan/default/licenses.json

    domain_content = models.BooleanField(default=False)

    domain_data = models.BooleanField(default=False)

    domain_software = models.BooleanField(default=False)

    status = models.CharField(
        verbose_name='Statut', max_length=30, default='active')

    maintainer = models.CharField(
        verbose_name='Maintainer', max_length=50, blank=True)

    od_conformance = models.CharField(
        verbose_name='od_conformance', max_length=30,
        blank=True, default='approved')

    osd_conformance = models.CharField(
        verbose_name='osd_conformance', max_length=30,
        blank=True, default='not reviewed')

    title = models.CharField(verbose_name='Nom', max_length=100)

    url = models.URLField(verbose_name='url', blank=True)

    class Meta(object):
        verbose_name = 'Licence'

    def __str__(self):
        return self.title

    @property
    def ckan_id(self):
        return 'license-{0}'.format(self.pk)


class Support(models.Model):

    name = models.CharField(
        verbose_name='Nom', max_length=100)

    description = models.CharField(
        verbose_name='Description', max_length=1024)

    ckan_slug = models.SlugField(
        verbose_name='Label court', max_length=100,
        unique=True, db_index=True, blank=True)

    email = models.EmailField(
        verbose_name='E-mail', blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = 'Support technique'
        verbose_name_plural = 'Supports techniques'


class DataType(models.Model):

    name = models.CharField(verbose_name='Nom', max_length=100)

    description = models.CharField(verbose_name='Description', max_length=1024)

    ckan_slug = models.SlugField(
        verbose_name='Ckan_ID', max_length=100,
        unique=True, db_index=True, blank=True)

    class Meta(object):
        verbose_name = 'Type de donnée'
        verbose_name_plural = 'Types de données'

    def __str__(self):
        return self.name


class Dataset(models.Model):

    GEOCOVER_CHOICES = (
        ('regionale', 'Régionale'),
        ('international', 'Internationale'),
        ('european', 'Européenne'),
        ('national', 'Nationale'),
        ('departementale', 'Départementale'),
        ('intercommunal', 'Inter-Communale'),
        ('communal', 'Communale'))

    FREQUENCY_CHOICES = (
        ('never', 'Jamais'),
        ('annualy', 'Annuelle'),
        ('monthly', 'Mensuelle'),
        ('weekly', 'Hebdomadaire'),
        ('daily', 'Quotidienne'),
        ('continue', 'Continue'),
        ('realtime', 'Temps réel'))

    # Mandatory
    name = models.TextField(verbose_name='Titre', unique=True)  # unique=False est préférable...

    ckan_slug = models.SlugField(
        error_messages={
            'invalid': "Le label court ne peut contenir ni majuscule, ni caractères spéciaux à l'exception le tiret."},
        verbose_name='Label court', max_length=100,
        unique=True, db_index=True, blank=True, null=True)

    ckan_id = models.UUIDField(
        verbose_name='Identifiant CKAN', unique=True,
        db_index=True, blank=True, null=True)

    description = models.TextField(
        verbose_name='Description', blank=True, null=True)

    thumbnail = models.ImageField(
        verbose_name='Illustration',
        upload_to='thumbnails/', blank=True, null=True)

    keywords = TaggableManager('Liste de mots-clés', blank=True)

    categories = models.ManyToManyField(
        to='Category', verbose_name="Catégories d'appartenance", blank=True)

    date_creation = models.DateField(
        verbose_name='Date de création', blank=True, null=True)

    date_modification = models.DateField(
        verbose_name='Date de dernière modification', blank=True, null=True)

    date_publication = models.DateField(
        verbose_name='Date de publication', blank=True, null=True)

    update_freq = models.CharField(
        verbose_name='Fréquence de mise à jour', default='never',
        max_length=30, choices=FREQUENCY_CHOICES)

    geocover = models.CharField(
        verbose_name='Couverture géographique', blank=True, null=True,
        default='regionale', max_length=30, choices=GEOCOVER_CHOICES)

    # Mandatory
    organisation = models.ForeignKey(
        to='Organisation',
        verbose_name="Organisation à laquelle est rattaché ce jeu de données",
        blank=True, null=True, on_delete=models.CASCADE)

    # Mandatory
    license = models.ForeignKey(License, verbose_name='Licence')

    support = models.ForeignKey(
        to='Support', verbose_name='Support technique', null=True, blank=True)

    data_type = models.ManyToManyField(
        to='DataType', verbose_name='Type de données', blank=True)

    published = models.BooleanField(
        verbose_name='Publier le jeu de données', default=False)

    is_inspire = models.BooleanField(
        verbose_name='Le jeu de données est soumis à la règlementation INSPIRE',
        default=False)

    geonet_id = models.UUIDField(
        verbose_name='UUID de la métadonnées', unique=True,
        db_index=True, blank=True, null=True)

    editor = models.ForeignKey(
        User, verbose_name='Producteur (propriétaire)')

    owner_name = models.CharField(
        verbose_name='Nom du producteur',
        max_length=100, blank=True, null=True)

    owner_email = models.EmailField(
        verbose_name='E-mail du producteur', blank=True, null=True)

    class Meta(object):
        verbose_name = 'Jeu de données'
        verbose_name_plural = 'Jeux de données'

    def __str__(self):
        return self.name

    def is_contributor(self, profile):
        return LiaisonsContributeurs.objects.filter(
            profile=profile, organisation=self.organisation,
            validated_on__isnull=False).exists()

    def is_referent(self, profile):
        return LiaisonsReferents.objects.filter(
            profile=profile, organisation=self.organisation,
            validated_on__isnull=False).exists()

    def clean(self):
        if not self.is_contributor(self.editor.profile):
            raise ValidationError((
                "L'utilisateur « {0} » n'est pas contributeur "
                "de l'organisation « {1} »").format(
                    self.editor.username, self.organisation.name))

    def save(self, *args, **kwargs):

        if not self.owner_name:
            self.owner_name = self.editor.get_full_name()
        if not self.owner_email:
            self.owner_email = self.editor.email

        # Cache avant sauvegarde
        previous = self.pk and Dataset.objects.get(pk=self.pk)

        # Le producteur/propriétaire doit toujours rester le créateur du jeu de données
        # self.editor = previous and previous.editor

        # Synchronisation CKAN
        self.publish_dataset_to_ckan(
            editor='editor' in kwargs and kwargs.pop('editor') or None)

        super().save(*args, **kwargs)

        if previous and previous.organisation:
            ckan.deactivate_ckan_organization_if_empty(
                str(previous.organisation.ckan_id))

    def publish_dataset_to_ckan(self, editor=None):

        ckan_params = {
            'author': self.owner_name,
            'author_email': self.owner_email,
            'datatype': [obj.ckan_slug for obj in self.data_type.all()],
            'dataset_creation_date':
                str(self.date_creation) if self.date_creation else '',
            'dataset_modification_date':
                str(self.date_modification) if self.date_modification else '',
            'dataset_publication_date':
                str(self.date_publication) if self.date_publication else '',
            'groups': [],
            'geocover': self.geocover,
            'last_modified':
                str(self.date_modification) if self.date_modification else '',
            'license_id': (
                self.license.ckan_id
                in [license['id'] for license in ckan.get_licenses()]
                ) and self.license.ckan_id or '',
            'maintainer':
                self.support and self.support.name or 'Plateforme DataSud',
            'maintainer_email':
                self.support and self.support.email or 'contact@datasud.fr',
            'notes': self.description,
            'owner_org': self.organisation.ckan_slug,
            'private': not self.published,
            'state': 'active',
            'support': self.support and self.support.ckan_slug,
            'tags':
                [{'name': keyword.name} for keyword in self.keywords.all()],
            'title': self.name,
            'update_frequency': self.update_freq,
            'url': ''}  # Laissez vide

        if self.geonet_id:
            ckan_params['inspire_url'] = \
                '{0}srv/fre/catalog.search#/metadata/{1}'.format(
                    GEONETWORK_URL, self.geonet_id or '')

        user = editor or self.editor

        for category in self.categories.all():
            ckan.add_user_to_group(user.username, str(category.ckan_id))
            ckan_params['groups'].append({'name': category.ckan_slug})

        # Si l'utilisateur courant n'est pas l'éditeur d'un jeu
        # de données existant mais administrateur de données,
        # alors l'admin Ckan édite le jeu de données..
        is_admin = user.profile.is_admin
        is_referent = LiaisonsReferents.objects.filter(
            profile=user.profile, organisation=self.organisation).exists()
        is_editor = (user == self.editor)
        if is_admin and not is_referent and not is_editor:
            ckan_user = ckan_me(ckan.apikey)
        else:
            ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])

        # Synchronisation de l'organisation
        organisation_ckan_id = str(self.organisation.ckan_id)
        ckan_orga = ckan.get_organization(organisation_ckan_id)
        if not ckan_orga:
            ckan.add_organization(self.organisation)
        elif ckan_orga.get('state') == 'deleted':
            ckan.activate_organization(organisation_ckan_id)
        for profile in LiaisonsContributeurs.get_contributors(self.organisation):
            ckan.add_user_to_organization(profile.user.username, organisation_ckan_id)

        ckan_dataset = ckan_user.publish_dataset(
            self.ckan_slug, id=str(self.ckan_id), **ckan_params)

        self.ckan_id = uuid.UUID(ckan_dataset['id'])
        ckan_user.close()

    @classmethod
    def get_subordinated_datasets(cls, profile):
        return cls.objects.filter(
            organisation__in=LiaisonsReferents.get_subordinated_organizations(
                profile=profile))


# Triggers


@receiver(pre_save, sender=Dataset)
def pre_save_dataset(sender, instance, **kwargs):
    if not instance.ckan_slug:
        instance.ckan_slug = slugify(instance.name)


@receiver(pre_delete, sender=Dataset)
def pre_delete_dataset(sender, instance, **kwargs):
    ckan.purge_dataset(str(instance.ckan_id))


@receiver(pre_delete, sender=Dataset)
def post_delete_dataset(sender, instance, **kwargs):
    ckan.deactivate_ckan_organization_if_empty(str(instance.organisation.ckan_id))


@receiver(post_save, sender=Resource)
def post_save_resource(sender, instance, **kwargs):
    instance.dataset.date_modification = timezone.now().date()
    instance.dataset.save()


@receiver(pre_delete, sender=User)
def pre_delete_user(sender, instance, **kwargs):
    ckan.del_user(instance.username)


@receiver(pre_save, sender=LiaisonsContributeurs)
def pre_save_contribution(sender, instance, **kwargs):
    if not instance.validated_on:
        return
    user = instance.profile.user
    organisation = instance.organisation
    if ckan.get_organization(str(organisation.ckan_id)):
        ckan.add_user_to_organization(user.username, str(organisation.ckan_id))


@receiver(pre_delete, sender=LiaisonsContributeurs)
def pre_delete_contribution(sender, instance, **kwargs):
    user = instance.profile.user
    organisation = instance.organisation
    if ckan.get_organization(str(organisation.ckan_id)):
        ckan.del_user_from_organization(user.username, str(organisation.ckan_id))


@receiver(pre_save, sender=Organisation)
def pre_save_organisation(sender, instance, **kwargs):
    instance.ckan_slug = slugify(instance.name)
    if instance.pk and ckan.is_organization_exists(instance.ckan_id):
        ckan.update_organization(instance)


@receiver(post_delete, sender=Organisation)
def post_delete_organisation(sender, instance, **kwargs):
    if ckan.is_organization_exists(str(instance.ckan_id)):
        ckan.purge_organization(str(instance.ckan_id))


@receiver(pre_delete, sender=Category)
def pre_delete_category(sender, instance, **kwargs):
    if ckan.is_group_exists(str(instance.ckan_id)):
        ckan.del_group(str(instance.ckan_id))
