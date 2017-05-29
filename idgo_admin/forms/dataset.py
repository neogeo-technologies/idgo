from django import forms
from django.core import validators
from django.db import IntegrityError
from django.forms import CheckboxSelectMultiple
from idgo_admin.models import *
from profiles.ckan_module import CkanHandler as ckan, \
                                 CkanUserHandler as my_ckan
from taggit.forms import *


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
                            widget=CheckboxSelectMultiple())

    organisation = forms.ModelChoiceField(
                            label="Organisme d'appartenance",
                            queryset=Organisation.objects.all(),
                            required=False)

    licences = forms.ModelChoiceField(
                            label='Licences',
                            queryset=License.objects.all(),
                            required=False)

    keywords = TagField(required=False)

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
                  'url_inspire')

    def handle_dataset(self, request, publish=False):

        user = request.user

        params = {"description": self.cleaned_data['description'],
                  "editor": user,
                  "geocover": self.cleaned_data['geocover'],
                  "keywords": self.cleaned_data['keywords'],
                  "licences": self.cleaned_data['licences'],
                  "organisation": self.cleaned_data['organisation'],
                  "owner_email": self.cleaned_data['owner_email'],
                  "update_freq": self.cleaned_data['update_freq'],
                  "url_inspire": self.cleaned_data['url_inspire'],
                  "sync_in_ckan": publish}

        dataset, created = Dataset.objects.get_or_create(name=self.cleaned_data['name'],
                                                         defaults=params)

        if self.cleaned_data['categories']:
            dataset.categories = self.cleaned_data['categories']

        ckan_user = my_ckan(ckan.get_user(user.username)['apikey'])
        params = {'author': user.username,
                  'author_email': user.email,
                  'geocover': dataset.geocover,
                  # 'groups': [{'name': ... }]  # TODO
                  'license_id': dataset.licences_id,
                  'maintainer': user.username,
                  'maintainer_email': user.email,
                  'notes': dataset.description,
                  'owner_org': dataset.organisation.ckan_slug,
                  'private': publish,
                  'state': 'active',
                  'title': dataset.name,
                  'update_frequency': dataset.update_freq,
                  'url': None}

        try:
            ckan_user.publish_dataset(dataset.ckan_slug, **params)
        except:
            dataset.sync_in_ckan = False
        dataset.save()
        ckan_user.close()
