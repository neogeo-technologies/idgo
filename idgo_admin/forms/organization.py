from django.core import validators
from django import forms
from idgo_admin.models import Jurisdiction
from idgo_admin.models import License
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType


class OrganizationForm(forms.ModelForm):

    class Meta(object):
        model = Organisation
        common_fields = (
            'address',
            'city',
            'description',
            'email',
            'jurisdiction',
            'license',
            'logo',
            'name',
            'organisation_type',
            'org_phone',
            'postcode',
            'website')
        extended_fields = (
            'contributor_process',
            'rattachement_process',
            'referent_process')
        fields = common_fields + extended_fields

    name = forms.CharField(
        error_messages={"Nom de l'organisation invalide": 'invalid'},
        label="Nom de l'organisation",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': "Nom de l'organisation"}))

    logo = forms.ImageField(
        label="Logo de l'organisation",
        required=False)

    address = forms.CharField(
        label='Adresse',
        required=False,
        widget=forms.Textarea(
            attrs={'placeholder': 'Numéro de voirie et rue', 'rows': 2}))

    city = forms.CharField(
        label='Ville',
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={'placeholder': 'Ville'}))

    postcode = forms.CharField(
        label='Code postal',
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={'placeholder': 'Code postal'}))

    org_phone = forms.CharField(
        error_messages={'invalid': 'Le numéro est invalide.'},
        required=False,
        label='Téléphone',
        max_length=30,
        min_length=10,
        widget=forms.TextInput(
            attrs={'placeholder': 'Téléphone', 'class': 'phone'}))

    email = forms.EmailField(
        error_messages={'invalid': "L'adresse e-mail est invalide."},
        label='Adresse e-mail',
        validators=[validators.validate_email],
        required=False,
        widget=forms.EmailInput(
            attrs={'placeholder': 'Adresse e-mail'}))

    website = forms.URLField(
        error_messages={'invalid': "L'adresse URL est erronée. "},
        label="URL du site internet de l'organisation",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Site internet'}))

    description = forms.CharField(
        required=False,
        label='Description',
        widget=forms.Textarea(
            attrs={'placeholder': 'Description'}))

    jurisdiction = forms.ModelChoiceField(
        empty_label='Aucun',
        label='Territoire de compétence',
        queryset=Jurisdiction.objects.all(),
        required=False)

    organisation_type = forms.ModelChoiceField(
        empty_label="Sélectionnez un type d'organisation",
        label="Type d'organisation",
        queryset=OrganisationType.objects.all(),
        required=False)

    license = forms.ModelChoiceField(
        empty_label="Sélectionnez une licence par défaut",
        label='Licence par défaut pour tout nouveau jeu de données',
        queryset=License.objects.all(),
        required=False)

    rattachement_process = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>membre</strong> de l'organisation",
        required=False)

    contributor_process = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>référent technique</strong> de l'organisation",
        required=False)

    referent_process = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>contributeur</strong> de l'organisation",
        required=False)

    def __init__(self, *args, **kwargs):
        self.include_args = kwargs.pop('include', {})
        self.extended = self.include_args.get('extended', False)
        super().__init__(*args, **kwargs)

        if not self.extended:
            for item in self.Meta.extended_fields:
                self.fields[item].widget = forms.HiddenInput()

    def clean(self):
        return self.cleaned_data
