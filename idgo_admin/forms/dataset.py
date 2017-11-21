from django.conf import settings
from django.core.exceptions import ValidationError
from django import forms
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.models import Category
from idgo_admin.models import create_organization_in_ckan
from idgo_admin.models import Dataset
from idgo_admin.models import DataType
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import License
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.models import Support
from idgo_admin.shortcuts import user_and_profile
import re
from taggit.forms import TagField
from taggit.forms import TagWidget
from uuid import UUID


GEONETWORK_URL = settings.GEONETWORK_URL


_today = timezone.now().date()
_today_str = _today.strftime('%d/%m/%Y')


class DatasetForm(forms.ModelForm):

    name = forms.CharField(
        label='Titre*',
        required=True)

    description = forms.CharField(
        label='Description',
        required=False,
        widget=forms.Textarea(
            attrs={'placeholder': 'Vous pouvez utiliser le langage Markdown ici'}))

    keywords = TagField(
        label='Liste de mots-clés',
        required=False,
        widget=TagWidget(
            attrs={'autocomplete': 'off',
                   'class': 'typeahead',
                   'placeholder': 'Utilisez la virgule comme séparateur'}))

    categories = forms.ModelMultipleChoiceField(
        label='Catégories associées',
        queryset=Category.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple())

    data_type = forms.ModelMultipleChoiceField(
        label='Type de données',
        queryset=DataType.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple())

    date_creation = forms.DateField(
        label='Date de création',
        required=False,
        widget=forms.TextInput(
            attrs={
                'autocomplete': 'off',
                'class': 'datepicker',
                'placeholder': '{0} (valeur par défaut)'.format(_today_str)}))

    date_modification = forms.DateField(
        label='Date de dernière modification',
        required=False,
        widget=forms.TextInput(
            attrs={
                'autocomplete': 'off',
                'class': 'datepicker',
                'placeholder': _today_str}))

    date_publication = forms.DateField(
        label='Date de publication',
        required=False,
        widget=forms.TextInput(
            attrs={
                'autocomplete': 'off',
                'class': 'datepicker',
                'placeholder': _today_str}))

    update_freq = forms.ChoiceField(
        choices=Dataset.FREQUENCY_CHOICES,
        label='Fréquence de mise à jour',
        required=False)

    geocover = forms.ChoiceField(
        choices=Dataset.GEOCOVER_CHOICES,
        label='Couverture géographique',
        required=False)

    organisation = forms.ModelChoiceField(
        label='Organisation à laquelle est rattaché ce jeu de données*',
        queryset=Organisation.objects.all(),
        required=True,
        empty_label="Sélectionnez une organisation")

    license = forms.ModelChoiceField(
        label='Licence*',
        queryset=License.objects.all(),
        required=True,
        empty_label="Sélectionnez une licence")

    # owner_email = forms.EmailField(
    #     label='Adresse e-mail du producteur',
    #     error_messages={'invalid': "L'adresse e-mail est invalide."},
    #     required=False,
    #     validators=[validators.validate_email],
    #     widget=forms.EmailInput(
    #         attrs={'placeholder': 'Adresse e-mail'}))

    published = forms.BooleanField(
        initial=True,
        label='Publier le jeu de données',
        required=False)

    support = forms.ModelChoiceField(
        label='Support technique',
        queryset=Support.objects.all(),
        required=False,
        empty_label="Aucun")

    thumbnail = forms.ImageField(label="Vignette", required=False)

    is_inspire = forms.BooleanField(
        initial=False,
        label='Le jeu de données est soumis à la règlementation INSPIRE',
        required=False)

    class Meta(object):
        model = Dataset
        fields = ('categories',
                  'data_type',
                  'date_creation',
                  'date_modification',
                  'date_publication',
                  'description',
                  'geocover',
                  'is_inspire',
                  'keywords',
                  'license',
                  'organisation',
                  'published',
                  'support',
                  'thumbnail',
                  'update_freq',
                  'name',)

    def __init__(self, *args, **kwargs):

        self.include_args = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)

        self.fields['organisation'].queryset = \
            Organisation.objects.filter(
                pk__in=[o.pk for o in LiaisonsContributeurs.get_contribs(
                        profile=Profile.objects.get(user=self.include_args['user']))])

    def clean(self):

        name = self.cleaned_data.get('name')
        # organisation = self.cleand_data.get('organisation', None)
        # if organisation:
        #     self.fields['license'].initial = organisation.license
        #     self.fields['license'].queryset = License.objects.all()

        if self.include_args['identification']:
            dataset = Dataset.objects.get(id=self.include_args['id'])
            if name != dataset.name and Dataset.objects.filter(name=name).exists():
                self.add_error('name', 'Ce nom est réservé.')
                raise ValidationError('NameError')

        if not self.include_args['identification'] \
                and Dataset.objects.filter(name=name).exists():
            self.add_error('name', 'Le jeu de données "{0}" existe déjà'.format(name))
            raise ValidationError("Dataset '{0}' already exists".format(name))

        if not self.cleaned_data.get('date_creation'):
            self.cleaned_data['date_creation'] = _today
        kwords = self.cleaned_data.get('keywords')

        if kwords:
            for w in kwords:
                if len(w) < 2:
                    self.add_error('keywords', "La taille minimum pour un mot clé est de 2 caractères. ")
                    raise ValidationError("KeywordsError")
                regex = '^[a-zA-Z0-9áàâäãåçéèêëíìîïñóòôöõúùûüýÿæœÁÀÂÄÃÅÇÉÈÊËÍÌÎÏÑÓÒÔÖÕÚÙÛÜÝŸÆŒ\._\-\s]*$'
                if not re.match(regex, w):
                    self.add_error('keywords', "Les mots-clés ne peuvent pas contenir de caractères spéciaux. ")
                    raise ValidationError("KeywordsError")
        return self.cleaned_data

    def handle_me(self, request, id=None):
        user, profile = user_and_profile(request)

        data = self.cleaned_data
        params = {
            'date_creation': data['date_creation'],
            'date_modification': data['date_modification'],
            'date_publication': data['date_publication'],
            'description': data['description'],
            'editor': user,
            'geocover': data['geocover'],
            'license': data['license'],
            'name': data['name'],
            'organisation': data['organisation'],
            # 'owner_email': data['owner_email'],
            'update_freq': data['update_freq'],
            'published': data['published'],
            'support': data['support'],
            'thumbnail': data['thumbnail'],
            'is_inspire': data['is_inspire']}

        if id:  # Mise à jour du jeu de données
            created = False
            params.pop('editor', None)
            dataset = Dataset.objects.get(pk=id)
            for key, value in params.items():
                setattr(dataset, key, value)
            dataset.save()
        else:  # Création d'un nouveau jeu de données
            created = True
            dataset = Dataset.objects.create(**params)

        if not ckan.get_organization(dataset.organisation.ckan_slug):
            create_organization_in_ckan(dataset.organisation)

        dataset.categories.set(data.get('categories', []), clear=True)

        if data.get('keywords'):
            dataset.keywords.clear()
            for tag in data['keywords']:
                dataset.keywords.add(tag)

        tags = [{'name': name} for name in data['keywords']]

        dataset.data_type.set(data.get('data_type', []), clear=True)

        ckan_params = {
            'author': user.username,
            'author_email': user.email,
            'datatype': [obj.ckan_slug for obj in data.get('data_type', [])],
            'dataset_creation_date':
                str(dataset.date_creation) if dataset.date_creation else '',
            'dataset_modification_date':
                str(dataset.date_modification) if dataset.date_modification else '',
            'dataset_publication_date':
                str(dataset.date_publication) if dataset.date_publication else '',
            'groups': [],
            'geocover': dataset.geocover,
            'last_modified':
                str(dataset.date_modification) if dataset.date_modification else '',
            'license_id': dataset.license.title,
            'maintainer': user.username,
            'maintainer_email': user.email,
            'notes': dataset.description,
            'owner_org': dataset.organisation.ckan_slug,
            'private': not dataset.published,
            'state': 'active',
            'support': params.get('support') and params.get('support').ckan_slug or '',
            'tags': tags,
            'title': dataset.name,
            'update_frequency': dataset.update_freq,
            'url': ''}

        if dataset.geonet_id:
            ckan_params['inspire_url'] = \
                '{0}srv/fre/catalog.search#/metadata/{1}'.format(
                    GEONETWORK_URL, dataset.geonet_id or '')

        for category in Category.objects.filter(pk__in=data['categories']):
            ckan.add_user_to_group(user.username, category.ckan_slug)
            ckan_params['groups'].append({'name': category.ckan_slug})

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        try:
            ckan_dataset = ckan_user.publish_dataset(
                dataset.ckan_slug, id=str(dataset.ckan_id), **ckan_params)
        except Exception as e:
            if created:
                dataset.delete()
            raise e
        else:
            dataset.ckan_id = UUID(ckan_dataset['id'])
            dataset.save()
        finally:
            ckan_user.close()

        return dataset
