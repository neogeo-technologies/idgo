from django.core import validators
from django.db import IntegrityError
from django.forms import CheckboxSelectMultiple
from django.utils.text import slugify

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

    # formulaire champ pré rempli
    owner_email = forms.EmailField(
        error_messages={'invalid': "L'adresse e-mail est invalide."},
        label='Adresse e-mail',
        validators=[validators.validate_email],
        widget=forms.EmailInput(attrs={'placeholder': 'Adresse e-mail'}))

    # Champs formulaire cachés:
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
            dataset = Dataset.objects.create(ckan_slug=slugify(self.cleaned_data["name"]),
                                             description=self.cleaned_data["description"],
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

class DatasetDisplayForm(forms.ModelForm):

    class Meta:
        model = Dataset
        fields = ('name', 'description', 'url_inspire',
                  'keywords', 'geocover', 'update_freq',
                  'licences', 'organisation', 'licences',
                  'owner_email',
                  'date_publication',)