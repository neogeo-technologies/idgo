# Copyright (c) 2017-2018 Datasud.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django import forms
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.forms import AddressField
from idgo_admin.forms import CityField
from idgo_admin.forms import ContributorField
from idgo_admin.forms import DescriptionField
from idgo_admin.forms import EMailField
from idgo_admin.forms import FirstNameField
from idgo_admin.forms import JurisdictionField
from idgo_admin.forms import LastNameField
from idgo_admin.forms import LicenseField
from idgo_admin.forms import OrganisatioNameField
from idgo_admin.forms import OrganisationLogoField
from idgo_admin.forms import OrganisationTypeField
from idgo_admin.forms import PasswordField
from idgo_admin.forms import PhoneField
from idgo_admin.forms import PostcodeField
from idgo_admin.forms import ReferentField
from idgo_admin.forms import UsernameField
from idgo_admin.forms import WebsiteField
from idgo_admin.models import Dataset
from idgo_admin.models import Jurisdiction
from idgo_admin.models import Organisation
from mama_cas.forms import LoginForm as MamaLoginForm


try:
    JURISDICTION_CODE = settings.DEFAULTS_VALUES.get('JURISDICTION')
    JURISDICTION = Jurisdiction.objects.get(code=JURISDICTION_CODE)
except:
    JURISDICTION_CODE = None
    JURISDICTION = None
  


class UserForgetPassword(forms.Form):

    class Meta(object):
        model = User
        fields = (
            'email',)

    email = EMailField()


class UserResetPassword(forms.Form):

    class Meta(object):
        model = User
        fields = (
            'username',
            'password')

    username = UsernameField()
    password1 = PasswordField()
    password2 = PasswordField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['placeholder'] = 'Nouveau mot de passe'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirmez le nouveau mot de passe'

    def clean(self):
        if self.cleaned_data.get('password1') != self.cleaned_data.get('password2'):
            self.add_error('password1', 'Vérifiez les mots de passe')
            self.add_error('password2', '')
            raise ValidationError('Les mots de passe ne sont pas identiques.')
        return self.cleaned_data

    def save(self, request, user):
        password = self.cleaned_data.get('password1')
        if password:
            user.set_password(password)
            user.save()
            logout(request)
            login(request, user,
                  backend='django.contrib.auth.backends.ModelBackend')

        user.save()
        return user


class SignInForm(MamaLoginForm):

    username = UsernameField()
    password = PasswordField()

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username and password:
            try:
                self.user = authenticate(
                    request=self.request, username=username, password=password)
            except Exception as e:
                raise ValidationError(e.__str__())

            if self.user is None:
                self.add_error('username', "Vérifiez votre nom d'utilisateur")
                self.add_error('password', 'Vérifiez votre mot de passe')
                raise ValidationError('User is not found')
            else:
                ckan_user = ckan.get_user(username)
                if ckan_user and ckan_user['state'] == 'deleted':
                    self.add_error('username', "Erreur interne d'authentification")
                    raise ValidationError('CKAN user is deleted')
                if not self.user.is_active:
                    self.add_error('username', "Ce compte n'est pas activé")
                    raise ValidationError('User is not activate')

        return self.cleaned_data


class UserDeleteForm(AuthenticationForm):

    class Meta(object):
        model = User
        fields = (
            'username',
            'password')

    username = UsernameField()
    password = PasswordField()


class DeleteAdminForm(forms.Form):

    new_user = forms.ModelChoiceField(
        User.objects.all().order_by('username'),
        empty_label="Selectionnez un utilisateur",
        label="Compte utilisateur pour réaffecter les jeux de donnés orphelins",
        required=False,
        widget=None,
        initial=None,
        help_text="Choisissez un nouvel utilisateur auquel seront affectés les jeux de données de l'utilisateur supprimé.",
        to_field_name=None,
        limit_choices_to=None)

    confirm = forms.BooleanField(
        label="Cocher pour confirmer la suppression de ce compte. ",
        required=True, initial=False)

    def __init__(self, *args, **kwargs):
        self.included = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)
        if self.included['user_id']:
            self.fields['new_user'].queryset = User.objects.exclude(id=self.included['user_id']).exclude(is_active=False).order_by('username')
        else:
            self.fields['new_user'].queryset = User.objects.filter(is_active=True).order_by('username')

    def delete_controller(self, deleted_user, new_user, related_datasets):
        if related_datasets:
            if not new_user:
                Dataset.objects.filter(editor=deleted_user).delete()
            else:
                Dataset.objects.filter(editor=deleted_user).update(editor=new_user)
        # Profil supprimé en cascade
        deleted_user.delete()


class SignUpForm(forms.Form):

    class Meta(object):

        user_fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'password')

        profile_fields = (
            'phone',
            'organisation')

        organisation_fields = (
            'address',
            'city',
            'description',
            'org_email',
            'jurisdiction',
            'license',
            'logo',
            'new_orga',
            'organisation_type',
            'org_phone',
            'postcode',
            'website')

        extended_fields = (
            'contributor',
            'referent')

        fields = user_fields + profile_fields + organisation_fields + extended_fields

    # User fields
    username = UsernameField()
    first_name = FirstNameField()
    last_name = LastNameField()
    email = EMailField()
    password1 = PasswordField()
    password2 = PasswordField()

    # Profile fields
    phone = PhoneField()
    organisation = forms.ModelChoiceField(
        required=False,
        label='Organisation',
        queryset=Organisation.objects.filter(is_active=True),
        empty_label="Je ne suis rattaché à aucune organisation")

    # Organisation fields
    new_orga = OrganisatioNameField()
    logo = OrganisationLogoField()
    address = AddressField()
    city = CityField()
    postcode = PostcodeField()
    org_phone = PhoneField()
    org_email = EMailField()
    website = WebsiteField()
    description = DescriptionField()
    jurisdiction = JurisdictionField()
    organisation_type = OrganisationTypeField()
    license = LicenseField()

    # Extended fields
    contributor = ContributorField()
    referent = ReferentField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if JURISDICTION:
            self.fields['jurisdiction'].initial = JURISDICTION

        self.fields['password1'].widget.attrs['placeholder'] = 'Mot de passe'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirmez le mot de passe'

    def clean(self):

        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists() or ckan.is_user_exists(username):
            self.add_error('username', "Ce nom d'utilisateur est reservé.")

        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            self.add_error('email', 'Ce courriel est reservé.')

        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Vérifiez les mots de passes.')
        self.cleaned_data['password'] = self.cleaned_data.pop('password1')

        return self.cleaned_data

    @property
    def is_member(self):
        if self.cleaned_data.get('organisation') is not None \
                or self.cleaned_data.get('new_orga') is not None:
            return True
        return False

    @property
    def is_contributor(self):
        return self.cleaned_data.get('contributor', False)

    @property
    def is_referent(self):
        return self.cleaned_data.get('referent', False)

    @property
    def create_organisation(self):
        return self.cleaned_data.get('new_orga')

    @property
    def cleaned_organisation_data(self):
        data = dict((item, self.cleaned_data.get(item))
                    for item in self.Meta.organisation_fields)
        data['name'] = data.pop('new_orga')
        return data

    @property
    def cleaned_user_data(self):
        return dict((item, self.cleaned_data.get(item))
                    for item in self.Meta.user_fields)

    @property
    def cleaned_profile_data(self):
        return dict((item, self.cleaned_data.get(item))
                    for item in self.Meta.profile_fields)


class UpdateAccountForm(forms.ModelForm):

    class Meta(object):
        model = User

        user_fields = (
            'first_name',
            'last_name',
            'email')

        profile_fields = (
            'phone',)

        fields = user_fields + profile_fields

    _instance = None

    # User fields
    first_name = FirstNameField()
    last_name = LastNameField()
    email = EMailField()
    password1 = PasswordField()
    password2 = PasswordField()

    # Profile fields
    phone = PhoneField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['password1'].widget.attrs['placeholder'] = 'Nouveau mot de passe'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirmez le nouveau mot de passe'

        if 'instance' in kwargs:
            self._instance = kwargs['instance']
            self.fields['phone'].initial = self._instance.profile.phone

    def clean(self):
        email = self.cleaned_data.get('email')
        if email != self._instance.email and User.objects.filter(email=email).exists():
            self.add_error('email', 'Ce courriel est reservé.')

        password = self.cleaned_data.pop('password1')
        if password != self.cleaned_data.pop('password2'):
            self.add_error('password1', '')
            self.add_error('password2', 'Vérifiez les mots de passe')
        else:
            self.cleaned_data['password'] = password

        return self.cleaned_data

    @property
    def new_password(self):
        return self.cleaned_data.get('password')
