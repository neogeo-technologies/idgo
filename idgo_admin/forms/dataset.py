from django import forms
from idgo_admin.models import Category
from idgo_admin.models import Dataset
from idgo_admin.models import License
from idgo_admin.models import Organisation
from idgo_admin.models import Resource
from profiles.ckan_module import CkanHandler as ckan
from profiles.ckan_module import CkanUserHandler as ckan_me
from profiles.models import Profile
from taggit.forms import TagField


class DatasetForm(forms.ModelForm):

    # Champs modifiables :

    geocover = forms.ChoiceField(
        choices=Dataset.GEOCOVER_CHOICES,
        label='Couverture géographique',
        required=False)

    update_freq = forms.ChoiceField(
        choices=Dataset.FREQUENCY_CHOICES,
        label='Fréquence de mise à jour',
        required=False)

    categories = forms.ModelMultipleChoiceField(
        label='Catégories associées',
        queryset=Category.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple())

    organisation = forms.ModelChoiceField(
        label='Organisme de publication',
        queryset=Organisation.objects.all(),
        required=True)

    licences = forms.ModelChoiceField(
        label='Licence',
        queryset=License.objects.all(),
        required=True)

    keywords = TagField(required=False)

    published = forms.BooleanField(
        initial=True,
        label='Publier le jeu de donnée',
        required=False)

    is_inspire = forms.BooleanField(
        initial=False,
        label='Le jeu de données est soumis à la règlementation INSPIRE',
        required=False)

    # Champs cachés :

    owner_email = forms.EmailField(required=False, widget=forms.HiddenInput())

    sync_in_ckan = forms.BooleanField(
        initial=False, required=False, widget=forms.HiddenInput())

    ckan_slug = forms.SlugField(required=False, widget=forms.HiddenInput())

    class Meta(object):
        model = Dataset
        fields = ('ckan_slug',
                  'description',
                  'geocover',
                  'keywords',
                  'licences',
                  'name',
                  'organisation',
                  'owner_email',
                  'update_freq',
                  'published',
                  'is_inspire',
                  'categories')

    def __init__(self, *args, **kwargs):
        include_args = kwargs.pop('include', {})

        super(DatasetForm, self).__init__(*args, **kwargs)

        ppf = Profile.publish_for.through
        set = ppf.objects.filter(profile__user=include_args['user'])
        my_pub_l = [e.organisation_id for e in set]

        self.fields['organisation'].queryset = \
            Organisation.objects.filter(pk__in=my_pub_l)

    def handle_me(self, request, id=None):
        user = request.user
        data = self.cleaned_data

        params = {'description': data['description'],
                  'editor': user,
                  'geocover': data['geocover'],
                  'licences': data['licences'],
                  'name': data['name'],
                  'organisation': data['organisation'],
                  'owner_email': data['owner_email'],
                  'update_freq': data['update_freq'],
                  'published': data['published']}

        if id:  # Mise à jour du dataset
            params.pop('editor', None)
            dataset = Dataset.objects.get(pk=id)
            for key, value in params.items():
                setattr(dataset, key, value)
        else:  # Création d'un nouveau dataset
            dataset = Dataset.objects.create(**params)

        if data['categories']:
            dataset.categories = data['categories']

        if data['keywords']:
            dataset.keywords.clear()
            for tag in data['keywords']:
                dataset.keywords.add(tag)

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])

        params = {
            'author': user.username,
            'author_email': user.email,
            'dataset_creation_date': str(dataset.date_creation.date()),
            'dataset_publication_date': str(dataset.date_publication.date()),
            'groups': [],  # Cf. plus bas..
            'geocover': dataset.geocover,
            'license_id': dataset.licences.title,
            'maintainer': user.username,
            'maintainer_email': user.email,
            'notes': dataset.description,
            'owner_org': dataset.organisation.ckan_slug,
            'private': dataset.published and False or True,
            'state': 'active',
            'tags': [{'name': name} for name in data['keywords']],
            'title': dataset.name,
            'update_frequency': dataset.update_freq,
            # TODO(@m431m): Générer l'URL INSPIRE.
            'url': ''}

        for category in Category.objects.filter(pk__in=data['categories']):
            ckan.add_user_to_group(user.username, category.ckan_slug)
            params['groups'].append({'name': category.ckan_slug})

        try:
            ckan_dataset = ckan_user.publish_dataset(
                dataset.ckan_slug, id=str(dataset.ckan_id), **params)
        except Exception as err:
            dataset.sync_in_ckan = False
            dataset.delete()
            raise err
        else:
            dataset.ckan_id = ckan_dataset['id']
            dataset.sync_in_ckan = True

        ckan_user.close()
        dataset.save()


class ResourceForm(forms.ModelForm):
    # Dans le formulaire de saisie, ne montrer que si AccessLevel = 2
    # geo_restriction, created_on, last_update dataset, type, fichier

    fichier = forms.FileField()

    class Meta(object):
        model = Resource
        fields = ('name',
                  'description',
                  'lang',
                  'data_format',
                  'projection',
                  'resolution',
                  'access',
                  'bbox',
                  'geo_restriction',
                  'dataset',
                  'data_type',
                  'url',
                  'up_file')

    def handle_me(self, request, dataset, id=None):

        data = self.cleaned_data

        params = {'name': data['name'],
                  'description': data['description'],
                  'url': data['url'],
                  'lang': data['licences'],
                  'data_format': data['data_format'],
                  'projection': data['projection'],
                  'resolution': data['resolution'],
                  'access': data['access'],
                  'bbox': data['bbox'],
                  'geo_restriction': data['geo_restriction'],
                  'data_type': data['data_type'],
                  'up_file': data['up_file'],
                  'dataset': dataset
                  }

        if id:  # Mise à jour d'un ressource
            resource = Resource.objects.get(pk=id)
            for key, value in params.items():
                setattr(resource, key, value)

        else:  # Création d'une nouvelle ressource
            resource = Resource.objects.create(**params)
