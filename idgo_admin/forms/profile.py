from . import common_fields
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core import validators
from django import forms

from idgo_admin.models import Organisation
from idgo_admin.models import Profile


class UserForm(forms.Form):

    username = common_fields.USERNAME
    email = common_fields.E_MAIL
    first_name = common_fields.FIRST_NAME
    last_name = common_fields.LAST_NAME
    password1 = common_fields.PASSWORD1
    password2 = common_fields.PASSWORD2

    class Meta(object):
        model = User
        fields = ('first_name', 'last_name', 'email', 'username', 'password')


class UserUpdateForm(forms.ModelForm):

    username = forms.CharField(widget=forms.HiddenInput(), required=True)
    first_name = common_fields.FIRST_NAME
    last_name = common_fields.LAST_NAME
    password1 = forms.CharField(
        label='Nouveau mot de passe',
        min_length=6, max_length=150, required=False,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Nouveau mot de passe'}))
    password2 = forms.CharField(
        label='Confirmer le nouveau mot de passe',
        min_length=6, max_length=150, required=False,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Confirmer le nouveau mot de passe'}))

    class Meta(object):
        model = User
        fields = ('first_name', 'last_name', 'email', 'username')

    def save_f(self, request):
        user = User.objects.get(username=self.cleaned_data['username'])

        if self.cleaned_data['password1'] != self.cleaned_data['password2']:
            self.add_error('password1', 'Vérifiez les champs mot de passe')
            self.add_error('password2', '')
            raise ValidationError('Les mots de passe ne sont pas identiques.')

        if "email" in self.cleaned_data and self.cleaned_data['email']:
            email = self.cleaned_data['email']
            if email != user.email and User.objects.filter(
                    email=email).count() > 0:
                raise forms.ValidationError('Cette adresse e-mail \
                                             est réservée.')

        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.username = self.cleaned_data['username']

        password = self.cleaned_data['password1']
        if password:
            user.set_password(password)
            user.save()
            logout(request)
            login(request, user,
                  backend='django.contrib.auth.backends.ModelBackend')

        user.save()
        return user


class UserProfileForm(forms.Form):

    organisation = forms.ModelChoiceField(required=False,
                                          label='Organisme',
                                          queryset=Organisation.objects.all())

    # parent = forms.ModelChoiceField(required=False,
    #                                 label='Organisme',
    #                                 queryset=Organisation.objects.all())

    new_orga = forms.CharField(
        error_messages={"Nom de l'organisme invalide": 'invalid'},
        label="Nom de l'organisme",
        max_length=255,
        min_length=3,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': "Nom de l'organisme"}))
    new_website = forms.URLField(
        error_messages={'invalid': "L'adresse URL est éronée. "},
        label="URL du site internet de l'organisme", required=False)
    is_new_orga = forms.BooleanField(widget=forms.HiddenInput(),
                                     required=False, initial=False)

    phone = common_fields.PHONE
    role = common_fields.ROLE

    class Meta(object):
        model = Profile
        fields = ('organisation', 'role', 'phone',
                  'new_orga', 'new_website', 'is_new_orga',)

    def clean(self):

        organisation = self.cleaned_data.get('organisation')
        if organisation is None:
            # Retourne le nom d'une nouvelle organisation lors d'une
            # nouvelle demande de création
            self.cleaned_data['organisation'] = \
                self.cleaned_data.get('new_orga')
            self.cleaned_data['website'] = self.cleaned_data.get('website')
            # self.cleaned_data['parent'] = self.cleaned_data.get('parent')
            # self.cleaned_data['code_insee'] = \
            #     self.cleaned_data.get('code_insee')
            # self.cleaned_data['organisation_type'] = \
            #     self.cleaned_data.get('organisation_type')
            self.cleaned_data['is_new_orga'] = True
        else:
            # Mettre les valeurs de `new_orga` et `website` lorsque
            # l'utilisateur a déjà choisi parmi la liste déroulante
            self.cleaned_data['new_orga'] = ''
            self.cleaned_data['website'] = ''
            # self.cleaned_data['parent'] = ''
            # self.cleaned_data['code_insee'] = ''
            # self.cleaned_data['organisation_type'] = ''
            self.cleaned_data['is_new_orga'] = False

            # Pour ne manipuler que le nom de l'organisation meme si existante
            self.cleaned_data['organisation'] = \
                self.cleaned_data['organisation'].name

        return self.cleaned_data


class ProfileUpdateForm(forms.ModelForm):

    organisation = forms.ModelChoiceField(required=False,
                                          label='Organisme',
                                          queryset=Organisation.objects.all())
    publish_for = forms.ModelChoiceField(required=False,
                                         label='Organismes associés',
                                         widget=forms.RadioSelect(),
                                         queryset=Organisation.objects.all())
    phone = forms.CharField(
        error_messages={'invalid': 'Le numéro est invalide.'},
        required=False, label='Téléphone',
        min_length=3, max_length=150,
        validators=[validators.RegexValidator(regex='^0\d{9}$')],
        widget=forms.TextInput(attrs={'placeholder': 'Téléphone'}))

    role = forms.CharField(
        required=False, label='Rôle',
        min_length=3, max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Rôle'}))

    class Meta(object):
        model = Profile
        fields = ('organisation', 'phone', 'role', 'publish_for')

    def __init__(self, *args, **kwargs):
        exclude_args = kwargs.pop('exclude', {})
        super(ProfileUpdateForm, self).__init__(*args, **kwargs)
        ppf = Profile.publish_for.through
        set = ppf.objects.filter(profile__user=exclude_args['user'])
        black_l = [e.organisation_id for e in set]
        self.fields['publish_for'].queryset = \
            Organisation.objects.exclude(pk__in=black_l)

    def save_f(self, commit=True):
        profile = super(ProfileUpdateForm, self).save(commit=False)
        org = self.cleaned_data['organisation']
        if org:
            profile.organisation = org

        if commit:
            profile.save()

        return profile


class UserLoginForm(AuthenticationForm):

    username = common_fields.USERNAME
    password = common_fields.PASSWORD1

    class Meta(object):
        model = User
        fields = ('username', 'password')


class UserDeleteForm(AuthenticationForm):

    username = common_fields.USERNAME
    password = common_fields.PASSWORD1

    class Meta(object):
        model = User
        fields = ('username', 'password')


class PublishDeleteForm(forms.ModelForm):
    publish_for = forms.ModelChoiceField(required=False,
                                         label='Organismes associés',
                                         widget=forms.RadioSelect(),
                                         queryset=Organisation.objects.all())

    def __init__(self, *args, **kwargs):
        include_args = kwargs.pop('include', {})
        super(PublishDeleteForm, self).__init__(*args, **kwargs)
        ppf = Profile.publish_for.through
        set = ppf.objects.filter(profile__user=include_args['user'])
        org_contrib = [e.organisation_id for e in set]
        self.fields['publish_for'].queryset = \
            Organisation.objects.filter(pk__in=org_contrib)

    class Meta(object):
        model = Profile
        fields = ('publish_for', )
