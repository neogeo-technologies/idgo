from django import forms
from django.contrib.auth.models import User
from django.shortcuts import redirect, get_object_or_404

from profiles.models import Profile, Organisation

from . import common_fields as fields


class UserForm(forms.Form):

    username = fields.USERNAME
    email = fields.E_MAIL
    first_name = fields.FIRST_NAME
    last_name = fields.LAST_NAME
    password1 = fields.PASSWORD1
    password2 = fields.PASSWORD2

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'username', 'password')


class UserUpdateForm(UserForm):
    password1 = forms.CharField(required=False,label='Mot de passe',
                                max_length=150, min_length=6,
                                widget=forms.PasswordInput(attrs={'placeholder': 'Mot de passe'}))

    password2 = forms.CharField(label="Password confirmation", required=False,
                                max_length=150, min_length=6,
                                widget=forms.PasswordInput(attrs={'placeholder': 'Mot de passe'}))
    username = forms.CharField(widget = forms.HiddenInput(), required = False)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'username')

    def save(self, commit=True):
        user = super(UserUpdateForm, self).save(commit=False)

        # if self.cleaned_data['password1'] != self.cleaned_data['password2']:
        #     self.add_error('password1', 'Vérifiez les champs mot de passe')
        #     return self.add_error('password1', 'Vérifiez les champs mot de passe')

        # user.username = self.cleaned_data["username"]
        password = self.cleaned_data["password1"]
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class UserProfileForm(forms.Form):

    organisation = fields.ORGANISATION
    phone = fields.PHONE
    role = fields.ROLE

    class Meta:
        model = Profile
        fields = ('organisation', 'role', 'phone')


class ProfileUpdateForm(UserProfileForm):

    organisation = forms.CharField(required=False,label='Organisme',
        widget=forms.Select(
            attrs={'placeholder': 'Organisme'},
            choices=Organisation.objects.all().values_list('id', 'name')))

    phone = forms.CharField(required=False,
        label='Téléphone',
        max_length=150,
        min_length=3,
        validators=[],  # TODO validator regex
        widget=forms.TextInput(attrs={'placeholder': 'Téléphone'}))

    role = forms.CharField(required = False,
        label='Rôle',
        max_length=150,
        min_length=3,
        widget=forms.TextInput(attrs={'placeholder': 'Rôle'}))

    class Meta:
        model = Profile
        fields = ('organisation', 'phone','role')

    def save(self, commit=True):
        profile = super(ProfileUpdateForm, self).save(commit=False)

        pk = self.cleaned_data["organisation"]
        if pk:
            profile.organisation = get_object_or_404(Organisation, pk=pk)
        if commit:
            profile.save()
        return profile


class UserDeleteForm(forms.Form):

    username = fields.USERNAME
    password = fields.PASSWORD1

    class Meta:
        model = User
        fields = ('username', 'password')


# class RegistrationForm(forms.Form):

#     from django.core.mail import send_mail
#     from django.forms.utils import ErrorList
#     from django.conf import settings
#
#     email = E_MAIL
#     password1 = PASSWORD1
#     password2 = PASSWORD2
#     site = SITE
#
#     def clean(self):
#         # Override clean method to check password match
#         password1 = self.cleaned_data.get('password1')
#         password2 = self.cleaned_data.get('password2')
#         if password1 and password1 != password2:
#             self._errors['password2'] = ErrorList(['Le mot de passe '
#                                                    'ne correspond pas.'])
#         return self.cleaned_data
#
#     def save(self, data):
#
#         import datetime
#
#         # Override of save method for saving both User and Profile objects
#
#         u = User.objects.create_user(
#                                      data['email'],
#                                      data['password1'])
#         u.is_active = False
#         u.save()
#
#         profile = Profile()
#         profile.user = u
#         profile.activation_key = data['activation_key']
#         profile.key_expires = datetime.datetime.strftime(datetime.datetime.now() + datetime.timedelta(days=2), "%Y-%m-%d %H:%M:%S")
#         profile.save()
#
#         return u
#
#     def send_email(self, data):
#
#         # Sending activation email
#         # ------>>>!! Warning : Domain name is hardcoded below !!<<<------
#         # The email is written in a text file (it contains templatetags
#         # which are populated by the method below)
#
#         link = 'http://%s/profiles/activate/' % settings.DOMAIN_NAME + data['activation_key']
#         # c = Context({'activation_link': link,'username': datas['username']})
#         # f = open(MEDIA_ROOT+datas['email_path'], 'r')
#         # t = Template(f.read())
#         # f.close()
#         message = 'Bonjour %s, merci pour votre inscription. ' \
#                   'Merci de la valider en cliquant sur le lien ' \
#                   'suivant : %s' % (data['username'], link)
#
#         print(message.encode('utf8'))
#
#         send_mail(
#             data['email_subject'], message,
#             'yourdomain <no-reply@yourdomain.com>',
#             [data['email']], fail_silently=False)
