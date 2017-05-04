from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core import validators
from django.core.mail import send_mail
from django.forms.utils import ErrorList
from django.template import Context, Template

from profiles.models import Profile, Organisation

import datetime


USERNAME = forms.CharField(
    label="Nom d'utilisateur",
    widget=forms.TextInput(
        attrs={'placeholder': "Nom d'utilisateur", 'class': 'form-control'}),
    max_length=30,
    min_length=3,
    validators=[validators.validate_slug])


PASSWORD1 = forms.CharField(
    label='Mot de passe',
    max_length=50,
    min_length=6,
    widget=forms.PasswordInput(
        attrs={'placeholder': 'Mot de passe', 'class': 'form-control'}))


PASSWORD2 = forms.CharField(
    label='Confirmer le mot de passe',
    max_length=50,
    min_length=6,
    widget=forms.PasswordInput(
        attrs={'placeholder': 'Confirmer le mot de passe',
               'class': 'form-control'}))


E_MAIL = forms.EmailField(
    label='Adresse e-mail',
    widget=forms.EmailInput(
        attrs={'placeholder': 'Adresse e-mail', 'class': 'form-control'}),
    max_length=100,
    error_messages={'invalid': ("L'adresse e-mail est invalide.")},
    validators=[validators.validate_email])


FIRST_NAME = forms.CharField(
    label='Prénom',
    widget=forms.TextInput(
        attrs={'placeholder': 'Prénom', 'class': 'form-control'}),
    max_length=30,
    min_length=3,
    validators=[validators.validate_slug])


LAST_NAME = forms.CharField(
    label='Nom',
    widget=forms.TextInput(
        attrs={'placeholder': 'Nom', 'class': 'form-control'}),
    max_length=30,
    min_length=3,
    validators=[validators.validate_slug])


SITE = forms.IntegerField(
    label='',
    widget=forms.Select(
        choices=Organisation.objects.all().values_list('id', 'name')))


class UserForm(forms.ModelForm):

    username = USERNAME
    password1 = PASSWORD1
    password2 = PASSWORD2
    email = E_MAIL
    first_name = FIRST_NAME
    last_name = LAST_NAME

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2',
                  'first_name', 'last_name', 'email']


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['orga', 'role', 'phone']


class UserDeleteForm(forms.ModelForm):

    username = USERNAME

    first_name = FIRST_NAME
    last_name = LAST_NAME

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']


class RegistrationForm(forms.Form):

    username = USERNAME
    password1 = PASSWORD1
    password2 = PASSWORD2
    email = E_MAIL
    site = SITE

    def clean(self):
        # Override clean method to check password match
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password1 != password2:
            self._errors['password2'] = ErrorList(['Le mot de passe '
                                                   'ne correspond pas.'])
        return self.cleaned_data

    def save(self, data):

        # Override of save method for saving both User and Profile objects

        u = User.objects.create_user(data['username'],
                                     data['email'],
                                     data['password1'])
        u.is_active = False
        u.save()
        profile = Profile()
        profile.user = u
        profile.activation_key = data['activation_key']
        profile.key_expires = datetime.datetime.strftime(datetime.datetime.now() + datetime.timedelta(days=2), "%Y-%m-%d %H:%M:%S")
        profile.save()

        return u

    def send_email(self, data):

        # Sending activation email
        # ------>>>!! Warning : Domain name is hardcoded below !!<<<------
        # The email is written in a text file (it contains templatetags
        # which are populated by the method below)

        link = 'http://%s/profiles/activate/' % settings.DOMAIN_NAME + data['activation_key']
        # c = Context({'activation_link': link,'username': datas['username']})
        # f = open(MEDIA_ROOT+datas['email_path'], 'r')
        # t = Template(f.read())
        # f.close()
        message = 'Bonjour %s, merci pour votre inscription. ' \
                  'Merci de la valider en cliquant sur le lien ' \
                  'suivant : %s' % (data['username'], link)

        print(message.encode('utf8'))

        send_mail(
            data['email_subject'], message,
            'yourdomain <no-reply@yourdomain.com>',
            [data['email']], fail_silently=False)
