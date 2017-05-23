from django import forms
from django.core import validators
from django.db import IntegrityError
from django.forms import CheckboxSelectMultiple

from idgo_admin.models import *

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

    # formulaire champ pré rempli
    owner_email = forms.EmailField(
        error_messages={'invalid': "L'adresse e-mail est invalide."},
        label='Adresse e-mail',
        validators=[validators.validate_email],
        widget=forms.EmailInput(attrs={'placeholder': 'Adresse e-mail'}))

    # Champs formulaire cachés:
    sync_in_ckan = forms.BooleanField(widget=forms.HiddenInput())
    ckan_slug = forms.SlugField(widget=forms.HiddenInput())


    class Meta:
        model = Dataset
        fields = ('name', 'description', 'url_inspire',
                  'keywords', 'geocover','update_freq',
                  'licences','organisation', 'licences',
                  'owner_email',
                  'date_publication',)

    def integrate_in_bo(self, request):
        user = request.user
        try:
            dataset = Dataset.objects.create(name=self.cleaned_data["name"],
                                             editor=user,
                                             geocover=self.cleaned_data["geocover"],
                                             update_freq=self.cleaned_data["update_freq"],
                                             organisation=self.cleaned_data["organisation"],
                                             owner_email=self.cleaned_data["owner_email"],
                                             sync_in_ckan=self.cleaned_data["sync_in_ckan"],
                                             ckan_slug=self.cleaned_data["ckan_slug"],
                                             licences=self.cleaned_data["licences"])

            if self.cleaned_data["categories"]:
                dataset.categories = self.cleaned_data["categories"]

        except:
            raise IntegrityError

        dataset.save()
        return dataset