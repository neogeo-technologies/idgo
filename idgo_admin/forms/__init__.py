from django.core import validators
from django import forms
from idgo_admin.models import Jurisdiction
from idgo_admin.models import License
# from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType
from idgo_admin.utils import StaticClass


class CommonFields(metaclass=StaticClass):

    ADDRESS = forms.CharField(
        label='Adresse',
        required=False,
        widget=forms.Textarea(
            attrs={
                'placeholder': 'Numéro de voirie et rue',
                'rows': 2}))

    CITY = forms.CharField(
        label='Ville',
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Ville'}))

    CONTRIBUTOR = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>contributeur</strong> de l'organisation",
        required=False)

    DESCRIPTION = forms.CharField(
        required=False,
        label='Description',
        widget=forms.Textarea(
            attrs={
                'placeholder': 'Description'}))

    EMAIL = forms.EmailField(
        error_messages={'invalid': "L'adresse e-mail est invalide."},
        label='Adresse e-mail',
        validators=[validators.validate_email],
        widget=forms.EmailInput(
            attrs={
                'placeholder': 'Adresse e-mail'}))

    FIRST_NAME = forms.CharField(
        error_messages={'invalid': 'invalid'},
        label='Prénom',
        max_length=30,
        min_length=1,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Prénom'}))

    JURISDICTION = forms.ModelChoiceField(
        empty_label='Aucun',
        label='Territoire de compétence',
        queryset=Jurisdiction.objects.all(),
        required=False)

    LAST_NAME = forms.CharField(
        label='Nom',
        max_length=30,
        min_length=1,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Nom'}))

    LICENSE = forms.ModelChoiceField(
        empty_label="Sélectionnez une licence par défaut",
        label='Licence par défaut pour tout nouveau jeu de données',
        queryset=License.objects.all(),
        required=False)

    ORGANISATION_LOGO = forms.ImageField(
        label="Logo de l'organisation",
        required=False)

    MEMBER = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>membre</strong> de l'organisation",
        required=False)

    # ORGANISATION = forms.ModelChoiceField(
    #     required=False,
    #     label='Organisation',
    #     queryset=Organisation.objects.filter(is_active=True),
    #     empty_label="Je ne suis rattaché à aucune organisation")

    ORGANISATION_NAME = forms.CharField(
        error_messages={"Nom de l'organisation invalide": 'invalid'},
        label="Nom de l'organisation",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': "Nom de l'organisation"}))

    ORGANISATION_TYPE = forms.ModelChoiceField(
        empty_label="Sélectionnez un type d'organisation",
        label="Type d'organisation",
        queryset=OrganisationType.objects.all(),
        required=False)

    PASSWORD = forms.CharField(
        label='Nouveau mot de passe',
        min_length=6,
        max_length=150,
        required=False,
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Mot de passe'}))

    PHONE = forms.CharField(
        error_messages={'invalid': 'Le numéro est invalide.'},
        required=False,
        label='Téléphone',
        max_length=30,
        min_length=10,
        widget=forms.TextInput(
            attrs={
                'class': 'phone',
                'placeholder': 'Téléphone'}))

    POSTCODE = forms.CharField(
        label='Code postal',
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Code postal'}))

    REFERENT = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>référent technique</strong> de l'organisation",
        required=False)

    USERNAME = forms.CharField(
        error_messages={
            'invalid': 'Seuls les caractères alpha-numériques et le caractère « _ » sont autorisés.'},
        label="Nom d'utilisateur",
        max_length=255,
        min_length=3,
        validators=[validators.validate_slug],
        widget=forms.TextInput(
            attrs={
                'placeholder': "Nom d'utilisateur"}))

    WEBSITE = forms.URLField(
        error_messages={'invalid': "L'adresse URL est erronée. "},
        label="URL du site internet de l'organisation",
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Site internet'}))


common_fields = CommonFields
