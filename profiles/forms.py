from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core import validators
from django.core.mail import send_mail
from django.forms.utils import ErrorList
from django.template import Context, Template

from profiles.models import Profile, Organisation

import datetime


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'password', 'email', 'first_name', 'last_name']


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['orga', 'address', 'zipcode',
                  'city', 'country', 'key_expires']


class UserDeleteForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']


class RegistrationForm(forms.Form):

    username = forms.CharField(
        label='',
        widget=forms.TextInput(
            attrs={'placeholder': "Nom d\'utilisateur",
                   'class': 'form-control input-perso'}),
        max_length=30,
        min_length=3,
        validators=[validators.validate_slug])

    email = forms.EmailField(
        label='',
        widget=forms.EmailInput(
            attrs={'placeholder': 'Email',
                   'class': 'form-control input-perso'}),
        max_length=100,
        error_messages={'invalid': ('Email invalide.')},
        validators=[validators.validate_email])

    password1 = forms.CharField(
        label='',
        max_length=50,
        min_length=6,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Mot de passe',
                   'class': 'form-control input-perso'}))

    password2 = forms.CharField(
        label='',
        max_length=50,
        min_length=6,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Confirmer le mot de passe',
                   'class': 'form-control input-perso'}))

    site = forms.IntegerField(
        widget=forms.Select(
            choices=Organisation.objects.all().values_list('id', 'name')))

    #recaptcha = ReCaptchaField()

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

    def sendEmail(self, data):

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
