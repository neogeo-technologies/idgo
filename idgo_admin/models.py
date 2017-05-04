from django.db import models
from django.contrib.gis.db import models
from django.contrib.auth.models import User
from ckan_module.views import ckan_add_group, ckan_sync_group, ckan_del_group
from django.utils.text import slugify
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
        verbose_name = "Catégorie"

    def save(self, *args, **kwargs):
        if self.id:
            self.sync_in_ckan = ckan_sync_group(self)
        else:
            self.ckan_slug = slugify(self.name)
            self.sync_in_ckan = ckan_add_group(self)

        if self.sync_in_ckan:
            super(Category, self).save(*args, **kwargs)

    def delete(self):
        if ckan_del_group(self):
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
        verbose_name = "Licence"


class Projection(models.Model):
    name = models.CharField('Nom', max_length=50)
    code = models.IntegerField('Code EPSG', primary_key=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Projection"


class Resolution(models.Model):
    value = models.CharField('Valeur', max_length=50)

    def __str__(self):
        return self.value

    class Meta:
        verbose_name = "Resolution"


class Commune(models.Model):
    code = models.CharField('Code INSEE', max_length=5)
    name = models.CharField('Nom', max_length=100)
    geom = models.MultiPolygonField('Geometrie', srid=4171, blank=True, null=True)
    objects = models.GeoManager()

    def __str__(self):
        return self.name


class Territory(models.Model):

    code = models.CharField('Code INSEE', max_length=5)
    name = models.CharField('Nom', max_length=100)
    commmunes = models.ManyToManyField(Commune)
    geom = models.MultiPolygonField('Geometrie', srid=4171, blank=True, null=True)
    objects = models.GeoManager()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Territoire"


class AccessLevel(models.Model):
    name = models.CharField('Libellé', max_length=10)
    code = models.IntegerField('Niveau')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Condition d'accès"
        verbose_name = "Conditions d'accès"


class Dataset(models.Model):

    GEOCOVER_CHOICES = (
        ('international', 'Internationale'),
        ('european', 'Européenne'),
        ('national', 'Nationale'),
        ('regionale', 'Régionale'),
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
    name = models.CharField('Nom', max_length=100)
    description = models.CharField('Description', max_length=1024)
    ckan_slug = models.SlugField('Ckan_ID', max_length=100, unique=True, db_index=True, blank=True)
    sync_in_ckan = models.BooleanField('Synchro CKAN', default=False)
    url_inspire = models.URLField('URL Inspire', blank=True)
    geocover = models.CharField('Couverture géographique', blank=True, max_length=30, choices=GEOCOVER_CHOICES)
    uf = models.CharField('Fréquence de mise à jour', max_length=15, choices=FREQUENCY_CHOICES, default='never')
    keywords = TaggableManager()

    def __str__(self):
        return self.name

    class Meta:
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

    name = models.CharField('Nom', max_length=150)
    description = models.TextField('Description')
    url = models.URLField('URL distante', blank=True)
    rfile = models.FileField('Fichier à télécharger', blank=True)
    lang = models.CharField('Langue', choices=LANG_CHOICES, default='french', max_length=10)
    format = models.CharField('Format', max_length=20, blank=True)
    projection = models.ForeignKey(Projection, blank=True)
    resolution = models.ForeignKey(Resolution, blank=True)
    acces = models.ForeignKey(AccessLevel)
    bbox = models.PolygonField('BBOX', blank=True)
    dataset = models.ForeignKey(Dataset)


    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Ressource"