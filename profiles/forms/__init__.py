from django import forms
from django.core import validators
from profiles.models import Organisation

from ..utils import StaticClass


__all__ = ['fields']


class CommonFields(metaclass=StaticClass):

    USERNAME = forms.CharField(
        error_messages={'invalid': "Seuls les caractères alpha-numériques et le caractère « _ » sont autorisés. "},
        label="Nom d'utilisateur",
        max_length=255,
        min_length=3,
        validators=[validators.validate_slug],
        widget=forms.TextInput(attrs={'placeholder': "Nom d'utilisateur"}))

    FIRST_NAME = forms.CharField(
        error_messages={'invalid': 'invalid'},
        label='Prénom',
        max_length=30,
        min_length=1,
        widget=forms.TextInput(attrs={'placeholder': 'Prénom'}))

    LAST_NAME = forms.CharField(
        label='Nom',
        max_length=30,
        min_length=1,
        widget=forms.TextInput(attrs={'placeholder': 'Nom'}))

    E_MAIL = forms.EmailField(
        error_messages={'invalid': "L'adresse e-mail est invalide."},
        label='Adresse e-mail',
        validators=[validators.validate_email],
        widget=forms.EmailInput(attrs={'placeholder': 'Adresse e-mail'}))

    PASSWORD1 = forms.CharField(
        label='Mot de passe',
        max_length=150,
        min_length=6,
        widget=forms.PasswordInput(attrs={'placeholder': 'Mot de passe'}))

    PASSWORD2 = forms.CharField(
        label='Confirmer le mot de passe',
        max_length=150,
        min_length=6,
        widget=forms.PasswordInput(
                attrs={'placeholder': 'Confirmer le mot de passe'}))

    ORGANISATION = forms.IntegerField(
        label='Organisme',
        widget=forms.Select(
                attrs={'placeholder': 'Organisme'},
                choices=Organisation.objects.all().values_list('id', 'name')))

    ROLE = forms.CharField(
        required=False,
        label='Rôle',
        max_length=150,
        min_length=3,
        widget=forms.TextInput(attrs={'placeholder': 'Rôle'}))

    PHONE = forms.CharField(
        required=False,
        label='Téléphone',
        max_length=150,
        min_length=3,
        validators=[],  # TODO validator regex
        widget=forms.TextInput(attrs={'placeholder': 'Téléphone'}))


common_fields = CommonFields
