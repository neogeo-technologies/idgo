from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core import validators
from django import forms
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.models import Dataset
from idgo_admin.models import Jurisdiction
from idgo_admin.models import License
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType
from mama_cas.forms import LoginForm as MamaLoginForm


class UserForgetPassword(forms.Form):

    email = forms.EmailField(
        error_messages={'invalid': "L'adresse e-mail est invalide."},
        label='Adresse e-mail',
        validators=[validators.validate_email],
        widget=forms.EmailInput(
            attrs={'placeholder': 'Adresse e-mail'}))

    class Meta(object):
        model = User
        fields = ('email',)


class UserResetPassword(forms.Form):

    username = forms.CharField(
        error_messages={
            'invalid': 'Seuls les caractères alpha-numériques et le caractère « _ » sont autorisés.'},
        label="Nom d'utilisateur",
        max_length=255,
        min_length=3,
        validators=[validators.validate_slug],
        widget=forms.TextInput(
            attrs={'placeholder': "Nom d'utilisateur"}))

    password1 = forms.CharField(
        label='Nouveau mot de passe',
        min_length=6, max_length=150, required=False,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Nouveau mot de passe'}))

    password2 = forms.CharField(
        label='Confirmez le nouveau mot de passe',
        min_length=6, max_length=150, required=False,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Confirmez le nouveau mot de passe'}))

    class Meta(object):
        model = User
        fields = ('username', 'password')

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

    username = forms.CharField(
        error_messages={
            'invalid': 'Seuls les caractères alpha-numériques et le caractère « _ » sont autorisés.'},
        label="Nom d'utilisateur",
        max_length=255,
        min_length=3,
        validators=[validators.validate_slug],
        widget=forms.TextInput(
            attrs={'placeholder': "Nom d'utilisateur"}))

    password = forms.CharField(
        label='Nouveau mot de passe',
        min_length=6,
        max_length=150,
        required=False,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Mot de passe'}))

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

    username = forms.CharField(
        error_messages={
            'invalid': 'Seuls les caractères alpha-numériques et le caractère « _ » sont autorisés.'},
        label="Nom d'utilisateur",
        max_length=255,
        min_length=3,
        validators=[validators.validate_slug],
        widget=forms.TextInput(
            attrs={'placeholder': "Nom d'utilisateur"}))

    password = forms.CharField(
        label='Nouveau mot de passe',
        min_length=6,
        max_length=150,
        required=False,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Mot de passe'}))

    class Meta(object):
        model = User
        fields = ('username', 'password')


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

    username = forms.CharField(
        error_messages={'invalid': ('Seuls les caractères alpha-numériques '
                                    'et le caractère « _ » sont autorisés.')},
        label="Nom d'utilisateur",
        max_length=255,
        min_length=3,
        validators=[validators.validate_slug],
        widget=forms.TextInput(
            attrs={'placeholder': "Nom d'utilisateur"}))

    first_name = forms.CharField(
        error_messages={'invalid': 'invalid'},
        label='Prénom',
        max_length=30,
        min_length=1,
        widget=forms.TextInput(
            attrs={'placeholder': 'Prénom'}))

    last_name = forms.CharField(
        label='Nom',
        max_length=30,
        min_length=1,
        widget=forms.TextInput(
            attrs={'placeholder': 'Nom'}))

    email = forms.EmailField(
        error_messages={'invalid': "L'adresse e-mail est invalide."},
        label='Adresse e-mail',
        validators=[validators.validate_email],
        widget=forms.EmailInput(
            attrs={'placeholder': 'Adresse e-mail'}))

    password1 = forms.CharField(
        label='Mot de passe',
        max_length=150,
        min_length=6,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Mot de passe'}))

    password2 = forms.CharField(
        label='Confirmer le mot de passe',
        max_length=150,
        min_length=6,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Confirmer le mot de passe'}))

    # Profile fields

    phone = forms.CharField(
        error_messages={'invalid': 'Le numéro est invalide.'},
        required=False,
        label='Téléphone',
        max_length=30,
        min_length=10,
        widget=forms.TextInput(
            attrs={'placeholder': 'Téléphone', 'class': 'phone'}))

    organisation = forms.ModelChoiceField(
        required=False,
        label='Organisation',
        queryset=Organisation.objects.filter(is_active=True),
        empty_label="Je ne suis rattaché à aucune organisation")

    # Organisation fields

    new_orga = forms.CharField(
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

    # Extended fields

    contributor = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>contributeur</strong> de l'organisation",
        required=False)

    referent = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>référent technique</strong> de l'organisation",
        required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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

    first_name = forms.CharField(
        error_messages={'invalid': 'invalid'},
        label='Prénom',
        max_length=30,
        min_length=1,
        widget=forms.TextInput(
            attrs={'placeholder': 'Prénom'}))

    last_name = forms.CharField(
        label='Nom',
        max_length=30,
        min_length=1,
        widget=forms.TextInput(
            attrs={'placeholder': 'Nom'}))

    email = forms.EmailField(
        error_messages={'invalid': "L'adresse e-mail est invalide."},
        label='Adresse e-mail',
        validators=[validators.validate_email],
        widget=forms.EmailInput(
            attrs={'placeholder': 'Adresse e-mail'}))

    password1 = forms.CharField(
        label='Mot de passe',
        max_length=150,
        min_length=6,
        required=False,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Nouveau mot de passe'}))

    password2 = forms.CharField(
        label='Confirmer le mot de passe',
        max_length=150,
        min_length=6,
        required=False,
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Confirmer le nouveau mot de passe'}))

    # Profile fields

    phone = forms.CharField(
        error_messages={'invalid': 'Le numéro est invalide.'},
        required=False,
        label='Téléphone',
        max_length=30,
        min_length=10,
        widget=forms.TextInput(
            attrs={'placeholder': 'Téléphone', 'class': 'phone'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
