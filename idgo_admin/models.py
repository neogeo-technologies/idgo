from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.db.models.signals import pre_delete
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.utils import PartialFormatter
from taggit.managers import TaggableManager
import uuid


class ResourceFormats(models.Model):

    CKAN_CHOICES = (
        (None, 'N/A'),
        ('text_view', 'text_view'),
        ('geo_view', 'geo_view'),
        ('recline_view', 'recline_view'),
        ('pdf_view', 'pdf_view'))

    extension = models.CharField('Format', max_length=30, unique=True)
    ckan_view = models.CharField('Vue', max_length=100,
                                 choices=CKAN_CHOICES, blank=True, null=True)

    class Meta(object):
        verbose_name = 'Format de ressource'
        verbose_name_plural = 'Formats de ressource'

    def __str__(self):
        return self.extension


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

    name = models.CharField('Nom', max_length=150)

    ckan_id = models.UUIDField(
        'Ckan UUID', default=uuid.uuid4, editable=False)

    description = models.TextField('Description', blank=True, null=True)

    referenced_url = models.URLField(
        'Référencer une URL', blank=True, null=True)

    dl_url = models.URLField(
        'Télécharger depuis une URL', blank=True, null=True)

    up_file = models.FileField(
        'Téléverser un ou plusieurs fichiers', blank=True, null=True)

    lang = models.CharField(
        'Langue', choices=LANG_CHOICES, default='french', max_length=10)

    format_type = models.ForeignKey(ResourceFormats, default=0)

    # projection = models.ForeignKey(
    #     'Projection', blank=True, null=True)

    # resolution = models.ForeignKey(
    #     'Resolution', blank=True, null=True)

    restricted_level = models.CharField(
        "Restriction d'accès", choices=LEVEL_CHOICES,
        default='0', max_length=20, blank=True, null=True)

    profiles_allowed = models.ManyToManyField(
        'Profile', verbose_name='Utilisateurs autorisés', blank=True)

    organisations_allowed = models.ManyToManyField(
        'Organisation', verbose_name='Organisations autorisées', blank=True)

    dataset = models.ForeignKey(
        'Dataset', on_delete=models.CASCADE, blank=True, null=True)

    bbox = models.PolygonField(
        'Rectangle englobant', blank=True, null=True)

    # Dans le formulaire de saisie, ne montrer que si AccessLevel = 2
    geo_restriction = models.BooleanField(
        'Restriction géographique', default=False)

    created_on = models.DateTimeField(
        verbose_name='Date de création de la resource',
        blank=True, null=True, default=timezone.now)

    last_update = models.DateTimeField(
        verbose_name='Date de dernière modification de la resource',
        blank=True, null=True)

    data_type = models.CharField(verbose_name='type de resources',
                                 choices=TYPE_CHOICES, max_length=10)

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = 'Ressource'


class Commune(models.Model):
    code = models.CharField('Code INSEE', max_length=5)
    name = models.CharField('Nom', max_length=100)
    geom = models.MultiPolygonField(
        'Geometrie', srid=2154, blank=True, null=True)
    objects = models.GeoManager()

    def __str__(self):
        return self.name

    class Meta(object):
        ordering = ['name']


class Jurisdiction(models.Model):  # Territory

    code = models.CharField('Code INSEE', max_length=10)
    name = models.CharField('Nom', max_length=100)
    communes = models.ManyToManyField(Commune)
    # geom = \
    #     models.MultiPolygonField('Geometrie', srid=2154, blank=True, null=True)
    objects = models.GeoManager()

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = 'Territoire de compétence'


class Financier(models.Model):  # Financeur

    name = models.CharField('Nom du financeur', max_length=250)
    code = models.CharField('Code du financeur', max_length=250)

    class Meta(object):
        verbose_name = "Nom du financeur d'une organisation"
        verbose_name_plural = "Noms des financeurs"

    def __str__(self):
        return self.name


# class Status(models.Model):
#
#     name = models.CharField("Status d'une organisation", max_length=250)
#     code = models.CharField('Code du status', max_length=250)
#
#     class Meta(object):
#         verbose_name = "Status d'une organisation"
#
#     def __str__(self):
#         return self.name


class OrganisationType(models.Model):

    name = models.CharField('Dénomination', max_length=50)
    code = models.CharField('Code', max_length=3)

    class Meta(object):
        verbose_name = "Type d'organisation"
        verbose_name_plural = "Types d'organisations"

    def __str__(self):
        return self.name


class Organisation(models.Model):

    name = models.CharField('Nom', max_length=150, unique=True, db_index=True)

    organisation_type = models.ForeignKey(
        OrganisationType, verbose_name="Type d'organisation",
        default='1', blank=True, null=True)

    # code_insee = models.CharField(
    #     'Code INSEE', max_length=20, unique=False, db_index=True)

    # parent = models.ForeignKey(
    #     'self', on_delete=models.CASCADE, blank=True,
    #     null=True, verbose_name="Organisation parente")

    # Territoire de compétence
    jurisdiction = models.ForeignKey(Jurisdiction, blank=True, null=True,
                                     verbose_name="Territoire de compétence")

    # geom = models.MultiPolygonField(
    #     'Territoire', srid=4171, blank=True, null=True)
    # objects = models.GeoManager()

    # Champs à integrer:
    # sync_in_ckan = models.BooleanField(
    #     'Synchronisé dans CKAN', default=False)

    ckan_slug = models.SlugField(
        'CKAN ID', max_length=150, unique=True, db_index=True)

    ckan_id = models.UUIDField(
        'Ckan UUID', default=uuid.uuid4, editable=False)

    website = models.URLField('Site web', blank=True)

    email = models.EmailField(
        verbose_name="Adresse mail de l'organisation", blank=True, null=True)

    # id_url_unique = models.URLField('URL unique', blank=True, null=True)

    # titre = models.CharField(  # ???
    #     'Titre', max_length=100, blank=True, null=True)

    description = models.TextField(
        'Description', blank=True, null=True)  # Description CKAN

    logo = models.ImageField(
        'Logo', upload_to="logos/", blank=True, null=True)

    address = models.CharField(
        'Adresse', max_length=100, blank=True, null=True)

    postcode = models.CharField(
        'Code postal', max_length=100, blank=True, null=True)

    city = models.CharField('Ville', max_length=100, blank=True, null=True)

    org_phone = models.CharField(
        'Téléphone', max_length=10, blank=True, null=True)

    # communes = models.ManyToManyField(Commune)  # Territoires de compétence

    license = models.ForeignKey(
        'License', on_delete=models.CASCADE, blank=True, null=True)

    financier = models.ForeignKey(
        Financier, blank=True, null=True, on_delete=models.CASCADE)

    # status = models.ForeignKey(
    #     Status, blank=True, null=True, on_delete=models.CASCADE)

    is_active = models.BooleanField(
        "Création validée par un administrateur", default=False)

    def __str__(self):
        return self.name

    # def delete(self, *args, **kwargs):
    #     ckan.del_organization(self.ckan_id)
    #     super().delete()


class Profile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    organisation = models.ForeignKey(
        Organisation, blank=True, null=True,
        verbose_name="Organisation d'appartenance")

    referents = models.ManyToManyField(
        Organisation, through='LiaisonsReferents',
        verbose_name="Organisations dont l'utiliateur est réferent",
        related_name='profile_referents')

    contributions = models.ManyToManyField(
        Organisation, through='LiaisonsContributeurs',
        verbose_name="Organisations dont l'utiliateur est contributeur",
        related_name='profile_contributions')

    resources = models.ManyToManyField(
        Resource, through='LiaisonsResources',
        verbose_name="Resources publiées par l'utilisateur",
        related_name='profile_resources')

    phone = models.CharField('Téléphone', max_length=10, blank=True, null=True)

    is_active = models.BooleanField(
        'Validation suite à confirmation mail par utilisateur', default=False)

    membership = models.BooleanField(
        verbose_name="Etat de rattachement profile-organisation d'appartenance",
        default=False)

    is_admin = models.BooleanField(
        verbose_name="Administrateur IDGO",
        default=False)

    def __str__(self):
        return self.user.username

    class Meta(object):
        verbose_name = 'Profil'
        verbose_name_plural = 'Profils'

    def nb_datasets(self, organisation):
        return Dataset.objects.filter(
            editor=self.user, organisation=organisation).count()

    # def nb_datasets(self, organisation):
    #     return Dataset.objects.filter(
    #         author=self.author, organisation=organisation).count()

    def is_referent(self, organisation=None):
        res = False
        if self.is_admin:
            res = True
        elif organisation:
            res = LiaisonsReferents.objects.filter(profile=self, organisation=organisation).exists()
        else:
            res = LiaisonsReferents.objects.filter(profile=self).exists()
        return res

    # @classmethod
    # def active_users(cls):
    #     active_profiles = Profile.objects.filter(is_active=True)
    #     return User.objects.filter(pk__in=[])


class LiaisonsReferents(models.Model):

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    created_on = models.DateField(auto_now_add=True)
    validated_on = models.DateField(
        verbose_name="Date de validation de l'action", blank=True, null=True)

    class Meta(object):
        unique_together = (('profile', 'organisation'),)

    @classmethod
    def get_subordinates(cls, profile):
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

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    created_on = models.DateField(auto_now_add=True)
    validated_on = models.DateField(
        verbose_name="Date de validation de l'action", blank=True, null=True)

    class Meta(object):
        unique_together = (('profile', 'organisation'),)

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

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
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
        ('reset_password', "Réinitialisation du mot de passe"))

    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, blank=True, null=True)

    # Pour pouvoir reutiliser AccountActions pour demandes post-inscription
    org_extras = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, blank=True, null=True)

    key = models.UUIDField(default=uuid.uuid4, editable=False)

    action = models.CharField(
        'Action de gestion de profile', blank=True, null=True,
        default='confirm_mail', max_length=250, choices=ACTION_CHOICES)

    created_on = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    closed = models.DateTimeField(
        verbose_name="Date de validation de l'action",
        blank=True, null=True)


class Mail(models.Model):

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
            p.user.email for p in Profile.objects.filter(
                referents=organisation)]
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

    template_name = models.CharField(
        'Nom du model du message', primary_key=True, max_length=255)

    subject = models.CharField(
        'Objet', max_length=255, blank=True, null=True)

    message = models.TextField(
        'Corps du message', blank=True, null=True)

    from_email = models.EmailField(
        'Adresse expediteur', default=settings.DEFAULT_FROM_EMAIL)

    def __str__(self):
        return self.template_name

    class Meta(object):
        verbose_name = 'e-mail'
        verbose_name_plural = 'e-mails'

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
        """Mail confirmant la creation d'un nouvelle organisation
        suite à une inscription.
        """

        mail_template = Mail.objects.get(template_name='confirmation_user_mail')

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
        """Mail permettant de valider la creation d'un nouvelle organisation
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
        data = {'username': user.username,
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
        """Message confirmant le role de contributeur à un utilisateur"""

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
                    reverse('idgo_admin:resetPassword',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])


class Category(models.Model):

    # A chaque déploiement
    # python manage.py sync_ckan_categories

    name = models.CharField('Nom', max_length=100)
    description = models.CharField('Description', max_length=1024)
    ckan_slug = models.SlugField(
        'Ckan_ID', max_length=100, unique=True, db_index=True, blank=True)
    # sync_in_ckan = models.BooleanField('Synchro CKAN', default=False)

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = 'Catégorie'

    # def save(self, *args, **kwargs):
    #     if self.id:
    #         self.sync_in_ckan = ckan.sync_group(self)
    #     else:
    #         self.ckan_slug = slugify(self.name)
    #         self.sync_in_ckan = ckan.add_group(self)
    #     super(Category, self).save(*args, **kwargs)

    # def delete(self):
    #     if ckan.del_group(self.ckan_slug):
    #         super(Category, self).delete()


class License(models.Model):

    # MODELE LIE AUX LICENCES CKAN. MODIFIER EGALEMENT DANS LA CONF CKAN
    # QUAND DES ELEMENTS SONT AJOUTES, il faut mettre à jour
    # le fichier /etc/ckan/default/licenses.json

    license_id = models.CharField('id', max_length=30)
    domain_content = models.BooleanField(default=False)
    domain_data = models.BooleanField(default=False)
    domain_software = models.BooleanField(default=False)
    status = models.CharField('Statut', max_length=30, default='active')
    maintainer = models.CharField('Maintainer', max_length=50, blank=True)
    od_conformance = models.CharField(
        'od_conformance', max_length=30, blank=True, default='approved')
    osd_conformance = models.CharField(
        'osd_conformance', max_length=30, blank=True, default='not reviewed')
    title = models.CharField('Nom', max_length=100)
    url = models.URLField('url', blank=True)

    def __str__(self):
        return self.title

    class Meta(object):
        verbose_name = 'Licence'


# class Projection(models.Model):
#
#     name = models.CharField('Nom', max_length=50)
#     code = models.IntegerField('Code EPSG', primary_key=True)
#
#     def __str__(self):
#         return self.name
#
#     class Meta(object):
#         verbose_name = 'Projection'
#
#
# class Resolution(models.Model):
#
#     value = models.CharField('Valeur', max_length=50)
#
#     def __str__(self):
#         return self.value
#
#     class Meta(object):
#         verbose_name = 'Resolution'


class Support(models.Model):

    name = models.CharField('Nom', max_length=100)
    description = models.CharField('Description', max_length=1024)
    ckan_slug = models.SlugField(
        'Ckan_ID', max_length=100, unique=True, db_index=True, blank=True)

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = 'Support technique'
        verbose_name_plural = 'Supports techniques'


class DataType(models.Model):

    name = models.CharField('Nom', max_length=100)
    description = models.CharField('Description', max_length=1024)
    ckan_slug = models.SlugField(
        'Ckan_ID', max_length=100, unique=True, db_index=True, blank=True)

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = 'Type de donnée'
        verbose_name_plural = 'Types de données'


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

    name = models.CharField('Nom', max_length=100, unique=True)

    description = models.TextField('Description', blank=True, null=True)

    ckan_slug = models.SlugField(
        'Ckan_ID', max_length=100, unique=True,
        db_index=True, blank=True, null=True)

    ckan_id = models.UUIDField(
        'Ckan UUID', unique=True, db_index=True, blank=True, null=True)

    # sync_in_ckan = models.BooleanField('Synchro CKAN', default=False)

    # url_inspire = models.URLField('URL Inspire', blank=True, null=True)

    is_inspire = models.BooleanField("L'URL Inspire est valide", default=False)

    geocover = models.CharField(
        'Couverture géographique', blank=True, null=True,
        default='regionale', max_length=30, choices=GEOCOVER_CHOICES)

    keywords = TaggableManager('Mots-clés', blank=True)

    date_creation = models.DateField(
        verbose_name='Date de création du jeu de données',
        blank=True, null=True)

    date_publication = models.DateField(
        verbose_name='Date de publication du jeu de données',
        blank=True, null=True)

    date_modification = models.DateField(
        verbose_name='Date de dernière modification du jeu de données',
        blank=True, null=True)

    editor = models.ForeignKey(User)

    # author = models.ForeignKey(Profile)

    organisation = models.ForeignKey(
        Organisation, blank=True, null=True,
        verbose_name="Organisation d'appartenance")

    license = models.ForeignKey(License, verbose_name="Licence d'utilisation")

    categories = models.ManyToManyField(
        Category, verbose_name="Catégories d'appartenance")

    update_freq = models.CharField(
        'Fréquence de mise à jour', default='never',
        max_length=30, choices=FREQUENCY_CHOICES)

    owner_email = models.EmailField(
        'E-mail du producteur de la donnée', blank=True, null=True)

    published = models.BooleanField(
        'Etat du jeu de donnée', default=False)

    geonet_id = models.UUIDField(
        'Metadonnées UUID', unique=True, db_index=True,
        blank=True, null=True)

    support = models.OneToOneField(Support, verbose_name="Support technique", null=True, blank=True)

    data_type = models.ManyToManyField(DataType, verbose_name="Type de données")

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = "Jeu de données"
        verbose_name_plural = "Jeux de données"

    def is_contributor(self, profile):
        res = LiaisonsContributeurs.objects.filter(
            profile=profile, organisation=self.organisation,
            validated_on__isnull=False).exists()
        return res

    def is_referent(self, profile):

        res = LiaisonsReferents.objects.filter(
            profile=profile, organisation=self.organisation,
            validated_on__isnull=False).exists()
        return res

# Triggers


@receiver(pre_save, sender=Dataset)
def pre_save_dataset(sender, instance, **kwargs):
    instance.ckan_slug = slugify(instance.name)


@receiver(post_save, sender=Resource)
def post_save_resource(sender, instance, **kwargs):
    instance.dataset.date_modification = timezone.now()
    instance.dataset.save()


@receiver(pre_delete, sender=User)
def delete_user_in_externals(sender, instance, **kwargs):
    try:
        # ldap.del_user(instance.username)
        ckan.del_user(instance.username)  # ->state='deleted'
    except Exception:
        pass


@receiver(pre_save, sender=LiaisonsContributeurs)
def pre_save_contribution(sender, instance, **kwargs):
    if not instance.validated_on:
        return
    user = instance.profile.user
    organisation = instance.organisation
    if ckan.get_organization(organisation.ckan_slug):
        ckan.add_user_to_organization(user.username, organisation.ckan_slug)


@receiver(pre_delete, sender=LiaisonsContributeurs)
def pre_delete_contribution(sender, instance, **kwargs):
    user = instance.profile.user
    organisation = instance.organisation
    if ckan.get_organization(organisation.ckan_slug):
        ckan.del_user_from_organization(user.username, organisation.ckan_slug)


@receiver(pre_save, sender=Organisation)
def pre_save_organization(sender, instance, **kwargs):
    instance.ckan_slug = slugify(instance.name)


def create_organization_in_ckan(organization):
    ckan.add_organization(organization)
    for profile in LiaisonsContributeurs.get_contributors(organization):
        user = profile.user
        ckan.add_user_to_organization(user.username, organization.ckan_slug)
