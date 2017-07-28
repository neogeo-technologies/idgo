from django import forms
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.models import Category
from idgo_admin.models import Liaisons_Contributeurs
from idgo_admin.models import Dataset
from idgo_admin.models import License
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from taggit.forms import TagField
from taggit.forms import TagWidget


class DatasetForm(forms.ModelForm):

    # Champs modifiables :

    name = forms.CharField(label='Titre', required=True)

    # description

    keywords = TagField(
        label='Liste de mots-clés',
        required=False,
        widget=TagWidget(
            attrs={'autocomplete': 'off',
                   'class': 'typeahead',
                   'placeholder': 'Utilisez la virgule pour séparer les valeurs.'}))

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

    published = forms.BooleanField(
        initial=True,
        label='Publier le jeu de données',
        required=False)

    is_inspire = forms.BooleanField(
        initial=False,
        label='Le jeu de données est soumis à la règlementation INSPIRE',
        required=False)

    date_creation = forms.DateField(
        label='Date de création',
        required=False,
        widget=forms.TextInput(attrs={'class': 'datepicker'}))

    date_modification = forms.DateField(
        label='Dernière modification',
        required=False,
        widget=forms.TextInput(attrs={'class': 'datepicker'}))

    date_publication = forms.DateField(
        label='Date de publication',
        required=False,
        widget=forms.TextInput(attrs={'class': 'datepicker'}))

    # Champs cachés :

    owner_email = forms.EmailField(
        required=False,
        widget=forms.HiddenInput())

    sync_in_ckan = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.HiddenInput())

    ckan_slug = forms.SlugField(
        required=False,
        widget=forms.HiddenInput())

    class Meta(object):
        model = Dataset
        fields = ('categories',
                  'ckan_slug',
                  'date_creation',
                  'date_modification',
                  'date_publication',
                  'description',
                  'geocover',
                  'is_inspire',
                  'keywords',
                  'licences',
                  'name',
                  'organisation',
                  'owner_email',
                  'published',
                  'update_freq')

    def __init__(self, *args, **kwargs):
        include_args = kwargs.pop('include', {})

        super(DatasetForm, self).__init__(*args, **kwargs)

        profile = Profile.objects.get(user=include_args['user'])
        self.fields['organisation'].queryset = \
            Organisation.objects.filter(
                pk__in=[o.pk for o in Liaisons_Contributeurs.get_contribs(
                    profile=profile)])

    def handle_me(self, request, id=None):
        user = request.user
        data = self.cleaned_data
        params = {'date_creation': data['date_creation'],
                  'date_modification': data['date_modification'],
                  'date_publication': data['date_publication'],
                  'description': data['description'],
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
        if not data['date_creation']:
            dataset.date_creation = timezone.now()
        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])

        params = {
            'author': user.username,
            'author_email': user.email,
            'dataset_creation_date': str(
                dataset.date_creation if dataset.date_creation else ''),
            'dataset_publication_date': str(
                dataset.date_publication if dataset.date_publication else ''),
            # TODO -> Last modification
            'groups': [],  # Cf. plus bas..
            'geocover': dataset.geocover,
            'id': str(dataset.ckan_id),
            'license_id': dataset.licences.title,
            'maintainer': user.username,
            'maintainer_email': user.email,
            'notes': dataset.description,
            'owner_org': dataset.organisation.ckan_slug,
            'private': not dataset.published,  # Reverse boolean
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
            ckan_user.publish_dataset(dataset.ckan_slug, **params)
        except Exception as e:
            dataset.sync_in_ckan = False
            dataset.delete()
            raise e
        else:
            dataset.sync_in_ckan = True

        ckan_user.close()
        dataset.save()
