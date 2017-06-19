from django import forms
from idgo_admin.models import *
from profiles.ckan_module import CkanHandler as ckan, \
                                 CkanUserHandler as ckan_me
from taggit.forms import TagField


class DatasetForm(forms.ModelForm):

    # Champs modifiables :

    geocover = forms.ChoiceField(
                            choices=Dataset.GEOCOVER_CHOICES,
                            label='Couverture géographique',
                            required = False)

    update_freq = forms.ChoiceField(
                            choices=Dataset.FREQUENCY_CHOICES,
                            label='Fréquence de mise à jour',
                            required=False)

    categories = forms.ModelMultipleChoiceField(
                            label='categories associés',
                            queryset=Category.objects.all(),
                            required=False,
                            widget=forms.CheckboxSelectMultiple())

    organisation = forms.ModelChoiceField(
                            label="Organisme d'appartenance",
                            queryset=Organisation.objects.all(),
                            required=True)

    licences = forms.ModelChoiceField(
                            label='Licences',
                            queryset=License.objects.all(),
                            required=True)

    keywords = TagField(required=False)

    published = forms.BooleanField(initial=True,
                                   label="Publier ce jeu de donnée ",
                                   required=False)

    is_inspire = forms.BooleanField(initial=False,
                                    label="Cette ressource nécessite une URL au format INSPIRE",
                                    required=False,)


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

    class Meta:
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
                  'is_inspire')

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
                  'url_inspire': data['url_inspire'],
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

        params = {'author': user.username,
                  'author_email': user.email,
                  'geocover': dataset.geocover,
                  # 'groups': [{'name': ... }]  # TODO
                  'license_id': dataset.licences_id,
                  'maintainer': user.username,
                  'maintainer_email': user.email,
                  'notes': dataset.description,
                  'owner_org': dataset.organisation.ckan_slug,
                  'private': False,
                  'state': 'active',
                  'title': dataset.name,
                  'update_frequency': dataset.update_freq,
                  'url': None, 'published':True}

        try:
            ckan_dataset = ckan_user.publish_dataset(
                dataset.ckan_slug, id=str(dataset.ckan_id), **params)
        except:
            dataset.sync_in_ckan = False
        else:
            dataset.ckan_id = ckan_dataset['id']
            dataset.sync_in_ckan = True

        ckan_user.close()
        dataset.save()
