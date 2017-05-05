from django import forms
from django.core import validators
from profiles.models import Organisation


__all__ = ['fields']


class FIELDS:

    FIRST_NAME = forms.CharField(
        label='Prénom',
        max_length=150,
        min_length=1,
        validators=[validators.validate_slug],
        widget=forms.TextInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Prénom'}))

    LAST_NAME = forms.CharField(
        label='Nom',
        max_length=150,
        min_length=1,
        validators=[validators.validate_slug],
        widget=forms.TextInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Nom'}))

    E_MAIL = forms.EmailField(
        error_messages={'invalid': ("L'adresse e-mail est invalide.")},
        label='Adresse e-mail',
        max_length=150,
        validators=[validators.validate_email],
        widget=forms.EmailInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Adresse e-mail'}))

    PASSWORD1 = forms.CharField(
        label='Mot de passe',
        max_length=150,
        min_length=6,
        widget=forms.PasswordInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Mot de passe'}))

    PASSWORD2 = forms.CharField(
        label='Confirmer le mot de passe',
        max_length=150,
        min_length=6,
        widget=forms.PasswordInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Confirmer le mot de passe'}))

    ORGANISATION = forms.CharField(
        label='Organisme',
        widget=forms.Select(
            attrs={'class': 'form-control',
                   'placeholder': 'Organisme'},
            choices=Organisation.objects.all().values_list('id', 'name')))

    ROLE = forms.CharField(
        label='Rôle',
        max_length=150,
        min_length=3,
        widget=forms.TextInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Rôle'}))

    PHONE = forms.CharField(
        label='Téléphone',
        max_length=150,
        min_length=3,
        widget=forms.TextInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Téléphone'}))

    SITE = forms.IntegerField(
        label='',
        widget=forms.Select(
            choices=Organisation.objects.all().values_list('id', 'name')))


fields = FIELDS
