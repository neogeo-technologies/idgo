from django.conf import settings
from django.contrib.auth.models import User
# from django.db import models
from django.contrib.gis.db import models  # TODO(@m431m)
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.db.models.signals import pre_delete
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from taggit.managers import TaggableManager
import uuid


def deltatime_2_days():
    return timezone.now() + timezone.timedelta(days=2)


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
        ('O', 'Tous les utilisateurs'),
        ('1', 'Utilisateurs authentifiés'),
        ('2', 'Utilisateurs authentifiés avec droits spécifiques'))

    # Une fiche dataset correspond à n fiches Resource

    name = models.CharField('Nom', max_length=150)

    ckan_id = models.UUIDField(
        'Ckan UUID', unique=True, db_index=True, blank=True, null=True)

    description = models.TextField('Description', blank=True, null=True)

    referenced_url = models.URLField(
        'Référencer une URL', blank=True, null=True)

    dl_url = models.URLField(
        'Télécharger depuis une URL', blank=True, null=True)

    up_file = models.FileField(
        'Téléverser un ou plusieurs fichiers', blank=True, null=True)

    lang = models.CharField(
        'Langue', choices=LANG_CHOICES, default='french', max_length=10)

    data_format = models.CharField(
        'Format', max_length=20, blank=True)

    projection = models.ForeignKey(
        'Projection', blank=True, null=True)

    resolution = models.ForeignKey(
        'Resolution', blank=True, null=True)

    restricted_level = models.CharField(
        "Restriction d'accès", choices=LEVEL_CHOICES,
        default="0", max_length=20, blank=True, null=True)

    allowed_users = models.ManyToManyField(
        'Profile', verbose_name="Utilisateurs autorisés")

    allowed_organisations = models.ManyToManyField(
        'Organisation', verbose_name="Organisations autorisées")

    dataset = models.ForeignKey(
        'Dataset', on_delete=models.CASCADE, blank=True, null=True)

    bbox = models.PolygonField(
        'Rectangle englobant', blank=True, null=True)

    # Dans le formulaire de saisie, ne montrer que si AccessLevel = 2
    geo_restriction = models.BooleanField(
        "Restriction géographique", default=False)

    created_on = models.DateTimeField(
        verbose_name="Date de creation de la resource",
        blank=True, null=True, default=timezone.now)

    last_update = models.DateTimeField(
        verbose_name="Date de dernière modification de la resource",
        blank=True, null=True)

    data_type = models.CharField(verbose_name='type de resources',
                                 choices=TYPE_CHOICES, max_length=10)

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = "Ressource"


class Commune(models.Model):
    code = models.CharField('Code INSEE', max_length=5)
    name = models.CharField('Nom', max_length=100)
    geom = models.MultiPolygonField(
        'Geometrie', srid=2154, blank=True, null=True)
    objects = models.GeoManager()

    def __str__(self):
        return self.name


class Financeur(models.Model):

    name = models.CharField('Nom du financeur', max_length=250)
    code = models.CharField('Code du financeur', max_length=250)

    class Meta(object):
        verbose_name = "Nom du financeur d'une organisation"
        verbose_name_plural = "Noms des financeurs"

    def __str__(self):
        return self.name


class Status(models.Model):

    name = models.CharField("Status d'une organisation", max_length=250)
    code = models.CharField('Code du status', max_length=250)

    class Meta(object):
        verbose_name = "Status d'une organisation"

    def __str__(self):
        return self.name


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
        OrganisationType, verbose_name="Type d'organisme", default='1')
    code_insee = models.CharField(
        'Code INSEE', max_length=20, unique=False, db_index=True)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, blank=True,
        null=True, verbose_name="Organisation parente")

    # Territoire de compétence
    geom = models.MultiPolygonField(
        'Territoire', srid=4171, blank=True, null=True)
    objects = models.GeoManager()

    # Champs à integrer:
    sync_in_ckan = models.BooleanField(
        'Synchronisé dans CKAN', default=False)
    ckan_slug = models.SlugField(
        'CKAN ID', max_length=150, unique=True, db_index=True)
    website = models.URLField('Site web', blank=True)
    email = models.EmailField(verbose_name="Adresse mail de l'organisation")
    id_url_unique = models.URLField('URL unique', blank=True, null=True)
    titre = models.CharField('Titre', max_length=100, blank=True, null=True)  # Todo: unique=True
    description = models.CharField('Description', max_length=1024, blank=True,
                                   null=True)  # Description CKAN
    logo = models.ImageField('Logo', upload_to="logos/", blank=True, null=True)
    adresse = models.CharField('Adresse', max_length=100, blank=True, null=True)
    code_postal = models.CharField('Code postal', max_length=100, blank=True,
                                   null=True)
    ville = models.CharField('Ville', max_length=100, blank=True, null=True)
    org_phone = models.CharField('Téléphone', max_length=10, blank=True, null=True)
    communes = models.ManyToManyField(Commune)  # Territoires de compétence
    license = models.ForeignKey('License', on_delete=models.CASCADE,
                                blank=True, null=True)
    financeur = models.ForeignKey(Financeur,
                                  blank=True, null=True,
                                  on_delete=models.CASCADE)
    status = models.ForeignKey(Status, blank=True, null=True,
                               on_delete=models.CASCADE)
    is_active = models.BooleanField("Création validée par un administrateur",
                                    default=False)

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        ckan.del_organization(self.ckan_slug)
        super().delete()

    # def delete(self, *args, **kwargs):
    #     res = ldap.sync_object(
    #         'organisations', self.name,
    #         self.id + settings.LDAP_ORGANISATION_ID_INCREMENT, 'delete')
    #     res_ckan = ckan.del_organization(self.ckan_slug)
    #     if res and res_ckan:
    #         super().delete()


class Profile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, blank=True, null=True,
                                     verbose_name="Organisme d'appartenance")
    referents = models.ManyToManyField(
        Organisation, through='Liaisons_Referents',
        verbose_name="Organismes dont l'utiliateur est réferent",
        related_name='profile_referents')

    contributions = models.ManyToManyField(
        Organisation, through='Liaisons_Contributeurs',
        verbose_name="Organismes dont l'utiliateur est contributeur",
        related_name='profile_contributions')

    resources = models.ManyToManyField(
        Resource, through='Liaisons_Resources',
        verbose_name="Resources publiées par l'utilisateur",
        related_name='profile_resources')

    phone = models.CharField('Téléphone', max_length=10, blank=True, null=True)
    role = models.CharField('Fonction', max_length=150, blank=True, null=True)
    is_active = models.BooleanField("Validation suite à confirmation mail par utilisateur",
                                    default=False)

    def __str__(self):
        return self.user.username


# TODO(cbenhabib):
# Le rattachement est conservé sur FK: Profile-Organisation
class Liaisons_Referents(models.Model):

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    created_on = models.DateField(auto_now_add=True)
    validated_on = models.DateField(
        verbose_name="Date de validation de l'action",
        blank=True, null=True)

    class Meta:
        unique_together = (('profile', 'organisation'),)

    @classmethod
    def get_subordonates(cls, profile):
        return [e.organisation for e in Liaisons_Contributeurs.objects.filter(
                    profile=profile)]


class Liaisons_Contributeurs(models.Model):

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    created_on = models.DateField(auto_now_add=True)
    validated_on = models.DateField(
        verbose_name="Date de validation de l'action",
        blank=True, null=True)

    class Meta:
        unique_together = (('profile', 'organisation'),)

    @classmethod
    def get_contribs(cls, profile):
        return [e.organisation for e in Liaisons_Contributeurs.objects.filter(
                    profile=profile)]


class Liaisons_Resources(models.Model):

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    created_on = models.DateField(auto_now_add=True)
    validated_on = models.DateField(
        verbose_name="Date de validation de l'action",
        blank=True, null=True)


# TODO: en remplacement de class Registraion
class AccountActions(models.Model):
    ACTION_CHOICES = (
        ("confirm_mail", "Confirmation de l'email par l'utilisateur"),
        ("confirm_new_organisation", ("Confirmation par un administrateur"
                                      "de la création d'une orga par l'utilisateur")),
        ("confirm_rattachement", "Rattachement d'un utilisateur à une organsiation par un administrateur"),
        ("confirm_referent", ("Confirmation du rôle de réferent d'une organisation"
                              "pour un utilisatur par un administrateur")),
        ("confirm_contribution", ("Confirmation du rôle de contributeur d'une organisation"
                                  "pour un utilisatur par un administrateur")),
        ("reset_password", "Réinitialisation du mot de passe")
    )
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE,
                                blank=True, null=True)

    # Pour pouvoir reutiliser AccountActions pour demandes post-inscription
    org_extras = models.ForeignKey(Organisation, on_delete=models.CASCADE,
                                   blank=True, null=True)

    key = models.UUIDField(default=uuid.uuid4, editable=False)
    action = models.CharField(
        'Action de gestion de profile', blank=True, null=True,
        default='confirm_mail', max_length=250, choices=ACTION_CHOICES)
    created = models.DateField(auto_now_add=True)
    closed = models.DateField(
        verbose_name="Date de validation de l'action",
        blank=True, null=True)


class Mail(models.Model):

    template_name = models.CharField("Nom du model du message",
                                     primary_key=True, max_length=255)

    subject = models.CharField("Objet", max_length=255, blank=True, null=True)
    message = models.TextField("Corps du message", blank=True, null=True)
    from_email = models.EmailField("Adresse expediteur",
                                   default=settings.DEFAULT_FROM_EMAIL)

    def __str__(self):
        return self.template_name

    @classmethod
    def validation_user_mail(cls, request, action):
        user = action.profile.user
        try:
            mail_template = Mail.objects.get(template_name="validation_user_mail")
        except Mail.DoesNotExist as e:
            raise e
        from_email = mail_template.from_email
        subject = mail_template.subject

        message = mail_template.message.format(
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            url=request.build_absolute_uri(
                reverse('idgo_admin:confirmation_mail',
                        kwargs={'key': action.key})))
        try:
            send_mail(subject=subject, message=message,
                      from_email=from_email, recipient_list=[user.email])
        except Exception as e:
            raise e

    @classmethod
    def confirmation_user_mail(cls, user):
        """Mail confirmant la creation d'un nouvelle organsation
        suite à une inscription.
        """
        mail_template = Mail.objects.get(template_name="confirmation_user_mail")

        message = mail_template.message.format(
                first_name=user.first_name, last_name=user.last_name,
                username=user.username)

        send_mail(subject=mail_template.subject, message=message,
                  from_email=mail_template.from_email, recipient_list=[user.email])

    @classmethod
    def confirm_new_organisation(cls, request, action):
        """Mail permettant de valider la creation d'un nouvelle organsation
        suite à une inscription.
        """
        user = action.profile.user
        mail_template = Mail.objects.get(template_name="confirm_new_organisation")
        message = mail_template.message.format(
                    username=user.username,
                    user_mail=user.email,
                    organisation_name=action.profile.organisation.name,
                    website=action.profile.organisation.website,
                    url=request.build_absolute_uri(
                        reverse('idgo_admin:confirm_new_orga',
                                kwargs={'key': action.key})))

        send_mail(subject=mail_template.subject, message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[usr.email for usr in User.objects.filter(
                        is_staff=True, is_active=True)])

    @classmethod
    def confirm_rattachement(cls, request, action):
        user = action.profile.user
        mail_template = Mail.objects.get(
                template_name="confirm_rattachement")
        message = mail_template.message.format(
                    username=user.username,
                    user_mail=user.email,
                    organisation_name=action.profile.organisation.name,
                    website=action.profile.organisation.website,
                    url=request.build_absolute_uri(
                        reverse('idgo_admin:confirm_rattachement',
                                kwargs={'key': action.key})))

        send_mail(
            subject=mail_template.subject, message=message,
            from_email=mail_template.from_email,
            recipient_list=[usr.email for usr
                            in User.objects.filter(is_staff=True, is_active=True)])

    @classmethod
    def confirm_referent(cls, request, action):
        user = action.profile.user
        organisation = action.org_extras
        mail_template = Mail.objects.get(
                template_name="confirm_referent")
        message = mail_template.message.format(
                    username=user.username,
                    user_mail=user.email,
                    organisation_name=organisation.name,
                    website=action.profile.organisation.website,
                    url=request.build_absolute_uri(
                        reverse('idgo_admin:confirm_referent',
                                kwargs={'key': action.key})))

        send_mail(
            subject=mail_template.subject, message=message,
            from_email=mail_template.from_email,
            recipient_list=[usr.email for usr
                            in User.objects.filter(is_staff=True, is_active=True)])

    @classmethod
    def confirm_contribution(cls, request, action):
        user = action.profile.user
        organisation = action.org_extras
        mail_template = Mail.objects.get(
                template_name="confirm_referent")
        message = mail_template.message.format(
                    username=user.username,
                    user_mail=user.email,
                    organisation_name=organisation.name,
                    website=organisation.website,
                    url=request.build_absolute_uri(
                        reverse('idgo_admin:confirm_contribution',
                                kwargs={'key': action.key})))

        send_mail(
            subject=mail_template.subject, message=message,
            from_email=mail_template.from_email,
            recipient_list=[usr.email for usr
                            in User.objects.filter(is_staff=True, is_active=True)])

    @classmethod
    def affiliate_confirmation_to_user(cls, profile):

        mail_template = Mail.objects.get(
                template_name="affiliate_confirmation_to_user")

        message = mail_template.message.format(
                organisation_name=profile.organisation.name)

        send_mail(subject=mail_template.subject, message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[profile.user.email])

    @classmethod
    def confirm_contrib_to_user(cls, action):
        """Message confirmant le role de contributeur à un utilisateur"""
        organisation = action.org_extras
        user = action.profile.user

        mail_template = Mail.objects.get(
                template_name="confirm_contrib_to_user")
        message = mail_template.message.format(
                organisation=organisation.name)
        send_mail(subject=mail_template.subject, message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])

    @classmethod
    def conf_deleting_dataset_res_by_user(cls, user, dataset=None, resource=None):

        if dataset:
            mail_template = Mail.objects.get(template_name="conf_deleting_dataset_by_user")
            message = mail_template.message.format(dataset_name=dataset.name)
        elif resource:
            mail_template = Mail.objects.get(template_name="conf_deleting_res_by_user")
            message = mail_template.message.format(
                    dataset_name=resource.dataset.name,
                    resource_name=resource.name)

        send_mail(subject=mail_template.subject, message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])

    @classmethod
    def conf_deleting_profile_to_user(cls, user_copy):
        mail_template = Mail.objects.get(template_name="conf_deleting_profile_to_user")

        message = mail_template.message.format(
                first_name=user_copy["first_name"],
                last_name=user_copy["last_name"],
                username=user_copy["username"])
        try:
            send_mail(subject=mail_template.subject, message=message,
                      from_email=mail_template.from_email,
                      recipient_list=[user_copy["email"]])
        except Exception as e:
            raise e

    @classmethod
    def send_reset_password_link_to_user(cls, request, reg):
        mail_template = Mail.objects.get(template_name="send_reset_password_link_to_user")
        user = reg.user

        message = mail_template.message.format(
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            url=request.build_absolute_uri(
                reverse('idgo_admin:resetPassword',
                        kwargs={'key': reg.reset_password_key})))

        send_mail(subject=mail_template.subject, message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])


class Category(models.Model):

    name = models.CharField('Nom', max_length=100)
    description = models.CharField('Description', max_length=1024)
    ckan_slug = models.SlugField('Ckan_ID', max_length=100, unique=True,
                                 db_index=True, blank=True)
    sync_in_ckan = models.BooleanField('Synchro CKAN', default=False)

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = "Catégorie"

    def save(self, *args, **kwargs):
        if self.id:
            self.sync_in_ckan = ckan.sync_group(self)
        else:
            self.ckan_slug = slugify(self.name)
            self.sync_in_ckan = ckan.add_group(self)
        super(Category, self).save(*args, **kwargs)

    def delete(self):
        if ckan.del_group(self.ckan_slug):
            super(Category, self).delete()


class License(models.Model):

    # MODELE LIE AUX LICENCES CKAN. MODIFIER EGALEMENT DANS LA CONF CKAN
    # QUAND DES ELEMENTS SONT AJOUTES, il faut mettre à jour
    # le fichier /etc/ckan/default/licenses.json

    license_id = models.CharField('id', max_length=30)
    domain_content = models.BooleanField(default=False)
    domain_data = models.BooleanField(default=False)
    domain_software = models.BooleanField(default=False)
    status = models.CharField('Statut', max_length=30, default="active")
    maintainer = models.CharField('Maintainer', max_length=50, blank=True)
    od_conformance = models.CharField('od_conformance', max_length=30,
                                      blank=True, default="approved")
    osd_conformance = models.CharField('osd_conformance', max_length=30,
                                       blank=True, default="not reviewed")
    title = models.CharField('Nom', max_length=100)
    url = models.URLField('url', blank=True)

    def __str__(self):
        return self.title

    class Meta(object):
        verbose_name = 'Licence'


class Projection(models.Model):
    name = models.CharField('Nom', max_length=50)
    code = models.IntegerField('Code EPSG', primary_key=True)

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = 'Projection'


class Resolution(models.Model):
    value = models.CharField('Valeur', max_length=50)

    def __str__(self):
        return self.value

    class Meta(object):
        verbose_name = 'Resolution'


class Territory(models.Model):

    code = models.CharField('Code INSEE', max_length=10)
    name = models.CharField('Nom', max_length=100)
    communes = models.ManyToManyField(Commune)
    geom = models.MultiPolygonField(
        'Geometrie', srid=2154, blank=True, null=True)
    objects = models.GeoManager()

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = 'Territoire'


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

    name = models.CharField('Nom', max_length=100, unique=True)  # Titre CKAN

    description = models.TextField(
        'Description', max_length=1024, blank=True, null=True)

    ckan_slug = models.SlugField(
        'Ckan_ID', max_length=100, unique=True,
        db_index=True, blank=True, null=True)

    ckan_id = models.UUIDField(
        'Ckan UUID', unique=True, db_index=True, blank=True, null=True)

    sync_in_ckan = models.BooleanField('Synchro CKAN', default=False)

    url_inspire = models.URLField('URL Inspire', blank=True, null=True)

    is_inspire = models.BooleanField("L'URL Inspire est valide", default=False)

    geocover = models.CharField(
        'Couverture géographique', blank=True, null=True,
        default='regionale', max_length=30, choices=GEOCOVER_CHOICES)

    keywords = TaggableManager(blank=True)

    date_creation = models.DateField(
        verbose_name="Date de création du jeu de donnée",
        # auto_now_add=timezone.now()
        )

    date_publication = models.DateField(
        verbose_name="Date de publication du jeu de donnée",
        # default=timezone.now
        )

    date_modification = models.DateField(
        verbose_name="Date de dernière modification du jeu de donnée",
        # default=timezone.now
        )

    editor = models.ForeignKey(User)

    organisation = models.ForeignKey(
        Organisation, blank=True, null=True,
        verbose_name="Organisme d'appartenance")

    licences = models.ForeignKey(License, verbose_name="Licence d'utilisation")

    categories = models.ManyToManyField(
        Category, verbose_name="Catégories d'appartenance")

    update_freq = models.CharField(
        'Fréquence de mise à jour', default='never',
        max_length=30, choices=FREQUENCY_CHOICES)

    owner_email = models.EmailField(
        'Email du producteur de la donnée', blank=True, null=True)

    published = models.BooleanField(
        'Etat du jeu de donnée', default=False)

    def __str__(self):
        return self.name

    class Meta(object):
        verbose_name = "Jeu de données"
        verbose_name_plural = "Jeux de données"


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


@receiver(pre_save, sender=Profile)
def update_externals(sender, instance, **kwargs):

    user = instance.user
    # through = Profile.publish_for.through
    contributions = Liaisons_Contributeurs.objects.filter(
                    profile=instance, validated_on__isnull=False)

    def remove(name):
        if name in ckan.get_organizations_which_user_belongs(user.username):
            ckan.del_user_from_organization(user.username, name)

    def add(name):
        ckan.add_user_to_organization(user.username, name)

    def iter_organization(profile, callback):
        # for e in through.objects.filter(profile=profile):
        #     callback(Organisation.objects.get(id=e.organisation_id).ckan_slug)
        for e in contributions:
            callback(e.organisation.ckan_slug)
    try:
        old = Profile.objects.get(pk=instance.id)
    except Profile.DoesNotExist:
        pass
    except Exception as e:
        print('Error:', e)
        pass
    else:
        iter_organization(old, remove)
        iter_organization(instance, add)


# TODO(cbenhabib): Orga inactive a la creation!
# Sync uniquement lors de l'activation
@receiver(pre_save, sender=Organisation)
def orga_ckan_presave(sender, instance, **kwargs):

    if instance.is_active:
        instance.sync_in_ckan = ckan.is_organization_exists(instance.ckan_slug)
        instance.ckan_slug = slugify(instance.name)
        try:
            ckan.add_organization(instance)
        except Exception:
            instance.sync_in_ckan = False
        else:
            instance.sync_in_ckan = True
    else:
        instance.sync_in_ckan = False
