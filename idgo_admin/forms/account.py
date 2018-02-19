from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django import forms
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.forms import common_fields
from idgo_admin.models import Dataset
from mama_cas.forms import LoginForm as MamaLoginForm


class UserForgetPassword(forms.Form):

    class Meta(object):
        model = User
        fields = (
            'email',)

    email = common_fields.EMAIL


class UserResetPassword(forms.Form):

    class Meta(object):
        model = User
        fields = (
            'username',
            'password')

    username = common_fields.USERNAME
    password1 = common_fields.PASSWORD
    password2 = common_fields.PASSWORD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['password1'].widget = forms.PasswordInput(
            attrs={'placeholder': 'Nouveau mot de passe'})
        self.fields['password2'].widget = forms.PasswordInput(
            attrs={'placeholder': 'Confirmez le nouveau mot de passe'})

    def clean(self):
        if self.cleaned_data['password1'] != self.cleaned_data['password2']:
            self.add_error('password1', 'Vérifiez les mots de passe')
            self.add_error('password2', '')
            raise ValidationError('Les mots de passe ne sont pas identiques.')
        return self.cleaned_data

    def save(self, request, user):
        password = self.cleaned_data['password1']
        if password:
            user.set_password(password)
            user.save()
            logout(request)
            login(request, user,
                  backend='django.contrib.auth.backends.ModelBackend')

        user.save()
        return user


class SignInForm(MamaLoginForm):

    username = common_fields.USERNAME
    password = common_fields.PASSWORD

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            try:
                self.user = authenticate(
                    request=self.request, username=username, password=password)
            except Exception:
                raise ValidationError("Erreur interne d'authentification")

            if self.user is None:
                self.add_error('username', "Vérifiez votre nom d'utilisateur")
                self.add_error('password', 'Vérifiez votre mot de passe')
                raise ValidationError('error')
            else:
                if not self.user.is_active:
                    self.add_error('username', "Ce compte n'est pas activé")
                    raise ValidationError('error')

        return self.cleaned_data


class UserDeleteForm(AuthenticationForm):

    class Meta(object):
        model = User
        fields = (
            'username',
            'password')

    username = common_fields.USERNAME
    password = common_fields.PASSWORD


class DeleteAdminForm(forms.Form):

    new_user = forms.ModelChoiceField(
        User.objects.all(),
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
            self.fields['new_user'].queryset = User.objects.exclude(id=self.included['user_id']).exclude(is_active=False)
        else:
            self.fields['new_user'].queryset = User.objects.filter(is_active=True)

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
            'email',
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
    username = common_fields.USERNAME
    first_name = common_fields.FIRST_NAME
    last_name = common_fields.LAST_NAME
    email = common_fields.EMAIL
    password1 = common_fields.PASSWORD
    password2 = common_fields.PASSWORD

    # Profile fields
    phone = common_fields.PHONE
    organisation = common_fields.ORGANISATION

    # Organisation fields
    new_orga = common_fields.ORGANISATION_NAME
    logo = common_fields.ORGANISATION_LOGO
    address = common_fields.ADDRESS
    city = common_fields.CITY
    postcode = common_fields.POSTCODE
    org_phone = common_fields.PHONE
    email = common_fields.EMAIL
    website = common_fields.WEBSITE
    description = common_fields.DESCRIPTION
    jurisdiction = common_fields.JURISDICTION
    organisation_type = common_fields.ORGANISATION_TYPE
    license = common_fields.LICENSE

    # Extended fields
    contributor = common_fields.CONTRIBUTOR
    referent = common_fields.REFERENT

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['password1'].widget = forms.PasswordInput(
            attrs={'placeholder': 'Nouveau mot de passe'})
        self.fields['password2'].widget = forms.PasswordInput(
            attrs={'placeholder': 'Confirmez le nouveau mot de passe'})

    def clean(self):

        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists() or ckan.is_user_exists(username):
            self.add_error('username', "Ce nom d'utilisateur est reservé.")

        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            self.add_error('email', "Ce courriel est reservé.")

        password1 = self.cleaned_data.get("password1", None)
        password2 = self.cleaned_data.get("password2", None)
        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Vérifiez les mots de passes.")
        self.cleaned_data['password'] = self.cleaned_data.pop('password1')

        return self.cleaned_data

    @property
    def is_member(self):
        return self.cleaned_data.get('organisation', False)

    @property
    def is_contributor(self):
        return self.cleaned_data.get('contributor', False)

    @property
    def is_referent(self):
        return self.cleaned_data.get('referent', False)

    @property
    def create_organisation(self):
        return self.cleaned_data.get('new_orga', None)

    @property
    def cleaned_organisation_data(self):
        data = dict((item, self.cleaned_data[item])
                    for item in self.Meta.organisation_fields)
        data['name'] = data.pop('new_orga')
        return data

    @property
    def cleaned_user_data(self):
        return dict((item, self.cleaned_data[item])
                    for item in self.Meta.user_fields)

    @property
    def cleaned_profile_data(self):
        return dict((item, self.cleaned_data[item])
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
    first_name = common_fields.FIRST_NAME
    last_name = common_fields.LAST_NAME
    email = common_fields.EMAIL
    password1 = common_fields.PASSWORD
    password2 = common_fields.PASSWORD

    # Profile fields
    phone = common_fields.PHONE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['password1'].widget = forms.PasswordInput(
            attrs={'placeholder': 'Nouveau mot de passe'})
        self.fields['password2'].widget = forms.PasswordInput(
            attrs={'placeholder': 'Confirmez le nouveau mot de passe'})

        if 'instance' in kwargs:
            self._instance = kwargs['instance']
            self.fields['phone'].initial = self._instance.profile.phone

    def clean(self):
        email = self.cleaned_data['email']
        if email != self._instance.email and User.objects.filter(email=email).exists():
            self.add_error('email', "Ce courriel est reservé.")

        password = self.cleaned_data.pop('password1')
        if password != self.cleaned_data.pop('password2'):
            self.add_error('password1', '')
            self.add_error('password2', 'Vérifiez les mots de passe')
        else:
            self.cleaned_data['password'] = password

        return self.cleaned_data

    @property
    def new_password(self):
        return self.cleaned_data.get('password', None)
