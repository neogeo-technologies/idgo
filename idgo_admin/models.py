from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from django.contrib.gis.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.models import User
from profiles.models import Organisation
from profiles.ckan_module import CkanHandler as ckan
from taggit.managers import TaggableManager


class Category(models.Model):
    # MODELE LIE AUX GROUPES CKAN. A SYNCHRONISER DONC.
    name = models.CharField('Nom', max_length=100)
    description = models.CharField('Description', max_length=1024)
    ckan_slug = models.SlugField('Ckan_ID', max_length=100, unique=True, db_index=True, blank=True)
    sync_in_ckan = models.BooleanField('Synchro CKAN', default=False)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        verbose_name = "Catégorie"

    def save(self, *args, **kwargs):
        if self.id:
            self.sync_in_ckan = ckan.sync_group(self)
        else:
            self.ckan_slug = slugify(self.name)
            self.sync_in_ckan = ckan.add_group(self)

        if self.sync_in_ckan:
            super(Category, self).save(*args, **kwargs)

    def delete(self):
        if ckan.del_group(self.ckan_slug):
            super(Category, self).delete()


class License(models.Model):
    # MODELE LIE AUX LICENCES CKAN. MODIFIER EGALEMENT DANS LA CONF CKAN
    # QUAND DES ELEMENTS SONT AJOUTES, il faut mettre à jour le fichier /etc/ckan/default/licenses.json
    license_id = models.CharField('id', max_length=30)
    domain_content = models.BooleanField(default=False)
    domain_data = models.BooleanField(default=False)
    domain_software = models.BooleanField(default=False)
    status = models.CharField('Statut', max_length=30, default="active")
    maintainer = models.CharField('Maintainer', max_length=50, blank=True)
    od_conformance = models.CharField('od_conformance', max_length=30, blank=True, default="approved")
    osd_conformance = models.CharField('osd_conformance', max_length=30, blank=True, default="not reviewed")
    title = models.CharField('Nom', max_length=100)
    url = models.URLField('url', blank=True)

    def __str__(self):
        return self.title

    class Meta:
        managed = False
        verbose_name = "Licence"


class Projection(models.Model):
    name = models.CharField('Nom', max_length=50)
    code = models.IntegerField('Code EPSG', primary_key=True)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        verbose_name = "Projection"


class Resolution(models.Model):
    value = models.CharField('Valeur', max_length=50)

    def __str__(self):
        return self.value

    class Meta:
        managed = False
        verbose_name = "Resolution"


class Commune(models.Model):
    code = models.CharField('Code INSEE', max_length=5)
    name = models.CharField('Nom', max_length=100)
    geom = models.MultiPolygonField('Geometrie', srid=2154, blank=True, null=True)
    objects = models.GeoManager()

    def __str__(self):
        return self.name

    class Meta:
        managed = False


class Territory(models.Model):

    code = models.CharField('Code INSEE', max_length=10)
    name = models.CharField('Nom', max_length=100)
    communes = models.ManyToManyField(Commune)
    geom = models.MultiPolygonField('Geometrie', srid=2154, blank=True, null=True)
    objects = models.GeoManager()

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        verbose_name = "Territoire"


class AccessLevel(models.Model):
    LEVEL_CHOICES = (
        ('O', 'tous les utilisateurs'),
        ('1', 'utilisateurs authentifiés'),
        ('2', 'utilisateurs authentifiés avec droits spécifiques'),
    )
    name = models.CharField('Libellé', max_length=10)
    code = models.IntegerField('Niveau', choices=LEVEL_CHOICES)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        verbose_name = "Condition d'accès"
        verbose_name_plural = "Conditions d'accès"


class Dataset(models.Model):

    GEOCOVER_CHOICES = (
        ('regionale', 'Régionale'),
        ('international', 'Internationale'),
        ('european', 'Européenne'),
        ('national', 'Nationale'),
        ('departementale', 'Départementale'),
        ('intercommunal', 'Inter-Communale'),
        ('communal', 'Communale')
    )

    FREQUENCY_CHOICES = (
        ('never', 'Jamais'),
        ('annualy', 'Annuelle'),
        ('monthly', 'Mensuelle'),
        ('weekly', 'Hebdomadaire'),
        ('daily', 'Quotidienne'),
        ('continue', 'Continue'),
        ('realtime', 'Temps réel')
    )
    name = models.CharField('Nom', max_length=100, unique=True) #Titre CKAN
    description = models.CharField('Description', max_length=1024, blank=True, null=True) #Description CKAN
    ckan_slug = models.SlugField('Ckan_ID', max_length=100, unique=True,
                                 db_index=True, blank=True, null=True)
    sync_in_ckan = models.BooleanField('Synchro CKAN', default=False)
    url_inspire = models.URLField('URL Inspire', blank=True, null=True)
    geocover = models.CharField('Couverture géographique', blank=True, null=True, default='regionale',
                                max_length=30, choices=GEOCOVER_CHOICES)
    keywords = TaggableManager()

    date_creation = models.DateTimeField(verbose_name="Date de création du jeu de donnée",
                                     auto_now_add=timezone.now())
    date_publication = models.DateTimeField(verbose_name="Date de publication du jeu de donnée",
                                        default=timezone.now)
    date_modification = models.DateTimeField(verbose_name="Date de dernière modification du jeu de donnée",
                                         auto_now=timezone.now())
    editor = models.ForeignKey(User)
    organisation = models.ForeignKey(Organisation, verbose_name="Organisme d'appartenance",
                                     blank=True, null=True)
    licences = models.ForeignKey(License, verbose_name="Licence d'utilisation")
    categories = models.ManyToManyField(Category, verbose_name="Catégories d'appartenance")
    update_freq = models.CharField('Fréquence de mise à jour', default='never',
                                max_length=30, choices=FREQUENCY_CHOICES)

    # formulaire champ pré rempli
    owner_email = models.EmailField('Email du producteur de la donnée', blank=True, null=True)


    def __str__(self):
        return self.name

    class Meta:
        managed = False
        verbose_name = "Jeu de données"
        verbose_name_plural = "Jeux de données"



class Resource(models.Model):

    # PENSER A SYNCHRONISER CETTE LISTE DES LANGUES AVEC LE STRUCTURE DECRITE DANS CKAN
    # cf. /usr/lib/ckan/default/lib/python2.7/site-packages/ckanext/scheming/ckan_dataset.json
    LANG_CHOICES = (
    ('french', 'Français'),
    ('english', 'Anglais'),
    ('italian', 'Italien'),
    ('german', 'Allemand'),
    ('other', 'Autre'),
    )
    TYPE_CHOICES = (
        ('data', 'Données'),
        ('resource', 'Resources'),
    )
    # Une fiche dataset correspond à n fiches Resource

    name = models.CharField('Nom', max_length=150)
    description = models.TextField('Description')
    url = models.URLField('URL distante', blank=True)
    rfile = models.FileField('Fichier à télécharger', blank=True)
    lang = models.CharField('Langue', choices=LANG_CHOICES, default='french', max_length=10)
    format = models.CharField('Format', max_length=20, blank=True)
    projection = models.ForeignKey(Projection, blank=True, null=True)
    resolution = models.ForeignKey(Resolution, blank=True, null=True)
    acces = models.ForeignKey(AccessLevel)
    bbox = models.PolygonField('BBOX', blank=True)
    geo_restriction = models.BooleanField("Restriction géographique", default=False) # Dans le formulaire de saisie, ne montrer que si AccessLevel = 2

    created_on = models.DateField(verbose_name="Date de creation de la resource",
                                  auto_now_add=timezone.now())
    last_update = models.DateField(verbose_name="Date de dernière modification de la resource",
                                   auto_now=timezone.now())
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    type = models.CharField(verbose_name='type de resources',
                            choices=TYPE_CHOICES, max_length=10)
    fichier = models.FileField(null=True, blank=True, default=None)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        verbose_name = "Ressource"


# Triggers
@receiver(pre_save, sender=Dataset)
def pre_save_dataset(sender, instance, **kwargs):
    instance.ckan_slug = slugify(instance.name)