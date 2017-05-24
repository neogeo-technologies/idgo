from django.core import validators
from django.db import IntegrityError
from django.forms import CheckboxSelectMultiple

from idgo_admin.models import *
from taggit.forms import *
from django import forms

class DatasetForm(forms.ModelForm):

    # Champs modifiables:
    geocover = forms.ChoiceField(required=False,
                                label='Couverture géographique',
                                choices=Dataset.GEOCOVER_CHOICES)

    update_freq = forms.ChoiceField(required=False,
                                 label='Fréquence de mise à jour',
                                 choices=Dataset.FREQUENCY_CHOICES)

    categories = forms.ModelMultipleChoiceField(required=False,
                                                 label='categories associés',
                                                 widget=CheckboxSelectMultiple(),
                                                 queryset=Category.objects.all())


    organisation = forms.ModelChoiceField(required=False,
                                          label="Organisme d'appartenance",
                                          queryset=Organisation.objects.all())

    licences = forms.ModelChoiceField(required=False,
                                          label="Licences",
                                          queryset=License.objects.all())

    keywords = TagField()

    # Champs formulaire cachés:
    owner_email = forms.EmailField(widget=forms.HiddenInput(), required=False) #Importer par defaut l'email d'organisation
    sync_in_ckan = forms.BooleanField(widget=forms.HiddenInput(), required=False, initial=False)
    ckan_slug = forms.SlugField(widget=forms.HiddenInput(), required=False)

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
                  'url_inspire',)

    def handle_dataset(self, request, publish=False):
        user = request.user
        try:
            dataset = Dataset.objects.create(description=self.cleaned_data["description"],
                                             editor=user,
                                             geocover=self.cleaned_data["geocover"],
                                             keywords=self.cleaned_data["keywords"],
                                             licences=self.cleaned_data["licences"],
                                             name=self.cleaned_data["name"],
                                             organisation=self.cleaned_data["organisation"],
                                             owner_email=self.cleaned_data["owner_email"],
                                             update_freq=self.cleaned_data["update_freq"],
                                             url_inspire=self.cleaned_data['url_inspire'],
                                             sync_in_ckan=publish)
            if self.cleaned_data["categories"]:
                dataset.categories = self.cleaned_data["categories"]

            dataset.save()
        except:
            raise IntegrityError
