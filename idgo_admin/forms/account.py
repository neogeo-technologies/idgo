from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core import validators
from django import forms
from django.utils.text import slugify
from idgo_admin.forms import common_fields
from idgo_admin.models import Dataset
from idgo_admin.models import Jurisdiction
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import License
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType
from idgo_admin.models import Profile
from mama_cas.forms import LoginForm as MamaLoginForm


class UserForm(forms.ModelForm):

    first_name = common_fields.FIRST_NAME
    last_name = common_fields.LAST_NAME
    username = common_fields.USERNAME
    email = common_fields.E_MAIL
    password1 = common_fields.PASSWORD1
    password2 = common_fields.PASSWORD2

    class Meta(object):
        model = User
        fields = ('first_name', 'last_name', 'email', 'username')

    def __init__(self, *args, **kwargs):

        self.include_args = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)

        # if self.include_args['action'] == "update_organization":
        #     self._profile = Profile.objects.get(user=self.include_args['user'])

        if self.include_args['action'] == "update":
            self.fields['username'].widget = forms.HiddenInput()
            self.fields['password1'] = forms.CharField(
                label='Nouveau mot de passe',
                min_length=6, max_length=150, required=False,
                widget=forms.PasswordInput(
                    attrs={'placeholder': 'Nouveau mot de passe'}))
            self.fields['password2'] = forms.CharField(
                label='Confirmez le nouveau mot de passe',
                min_length=6, max_length=150, required=False,
                widget=forms.PasswordInput(
                    attrs={'placeholder': 'Confirmez le nouveau mot de passe'}))

        # if self.include_args['action'] == "update_organization":
        #     self.fields['username'].required = False
        #     self.fields['last_name'].required = False
        #     self.fields['first_name'].required = False
        #     self.fields['email'].required = False
        #     self.fields['password1'].required = False
        #     self.fields['password2'].required = False

    def clean(self):

        # if self.include_args['action'] == "update_organization":
        #     self.cleaned_data['username'] = self.instance.username
        #     self.cleaned_data['last_name'] = self.instance.last_name
        #     self.cleaned_data['first_name'] = self.instance.first_name
        #     self.cleaned_data['email'] = self.instance.email
        #     self.cleaned_data['password'] = self.instance.password
        #     return self.cleaned_data

        username = self.cleaned_data.get('username', None)
        if username and username.lower() != username:
            self.add_error('username', "Le nom d'utilisateur doit contenir uniquement des caractères alphanumériques en minuscules (ascii) et ces symboles : -_")
            raise ValidationError('UsernameLower')

        password = self.cleaned_data.get('password1', None)
        if password and (self.cleaned_data['password1'] != self.cleaned_data['password2']):
            self.add_error('password1', 'Vérifiez les mots de passe')
            self.add_error('password2', '')
            raise ValidationError('Les mots de passe ne sont pas identiques.')

        email = self.cleaned_data.get('email', None)
        if email and self.include_args['action'] == 'create':
            if User.objects.filter(email=email).count() > 0:
                self.add_error('email', 'Cette adresse e-mail est réservée.')
                raise ValidationError(
                    'Cette adresse e-mail est réservée.')

        if email and self.include_args['action'] == 'update':
            user = User.objects.get(username=self.cleaned_data['username'])
            if email != user.email and User.objects.filter(
                    email=email).count() > 0:
                self.add_error('email', 'Cette adresse e-mail est réservée.')
                raise ValidationError(
                    'Cette adresse e-mail est réservée.')

        return self.cleaned_data


class UserForgetPassword(forms.Form):
    email = common_fields.E_MAIL

    class Meta(object):
        model = User
        fields = ('email',)


class UserResetPassword(forms.Form):

    username = common_fields.USERNAME
    # username = forms.CharField(widget=forms.HiddenInput(), required=False)
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


class ProfileForm(forms.ModelForm):
    # Champs Profile
    phone = common_fields.PHONE

    # Champs Organisation
    address = forms.CharField(
        required=False,
        label="Adresse",
        max_length=1024,
        widget=forms.TextInput(
            attrs={'placeholder': "Numéro de voirie et rue"}))

    city = forms.CharField(
        required=False,
        label="Ville",
        max_length=150,
        widget=forms.TextInput(
            attrs={'placeholder': "Ville"}))

    contribution_requested = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>contributeur</strong> de l'organisation",
        required=False)

    contributions = forms.ModelChoiceField(
        required=False,
        label='Organisation de contribution',
        widget=forms.RadioSelect(),
        queryset=Organisation.objects.all())

    description = forms.CharField(
        required=False,
        label='Description',
        widget=forms.Textarea(
            attrs={'placeholder': 'Description'}))

    jurisdiction = forms.ModelChoiceField(
        required=False,
        label='Territoire de compétence',
        queryset=Jurisdiction.objects.all(),
        empty_label='Aucun')

    license = forms.ModelChoiceField(
        required=False,
        label='Licence par défaut pour tout nouveau jeu de données',
        queryset=License.objects.all(),
        empty_label="Sélectionnez une licence par défaut")

    logo = forms.ImageField(
        label="Logo de l'organisation",
        required=False)

    new_orga = forms.CharField(
        error_messages={"Nom de l'organisation invalide": 'invalid'},
        label="Nom de l'organisation",
        max_length=100,
        min_length=3,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': "Nom de l'organisation"}))

    org_phone = common_fields.PHONE

    organisation = forms.ModelChoiceField(
        required=False,
        label='Organisation',
        queryset=Organisation.objects.all(),
        empty_label="Je ne suis rattaché à aucune organisation")

    organisation_type = forms.ModelChoiceField(
        required=False,
        label="Type d'organisation",
        queryset=OrganisationType.objects.all(),
        empty_label="Sélectionnez un type d'organisation")

    postcode = forms.CharField(
        required=False,
        label='Code postal',
        max_length=10,
        widget=forms.TextInput(
            attrs={'placeholder': 'Code postal'}))

    referent_requested = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>référent technique</strong> de l'organisation",
        required=False)

    referents = forms.ModelChoiceField(
        required=False,
        label='Référent technique pour ces organisations',
        widget=forms.RadioSelect(),
        queryset=Organisation.objects.all())

    website = forms.URLField(
        error_messages={'invalid': "L'adresse URL est erronée. "},
        label="URL du site internet de l'organisation", required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Site internet'}))

    class Meta(object):
        model = Profile
        fields = ('phone', 'organisation')

    def __init__(self, *args, **kwargs):

        self.include_args = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)

        if self.include_args['action'] in ("update", "update_organization"):
            self._profile = Profile.objects.get(user=self.include_args['user'])
            # On exclut de la liste de choix toutes les organisations pour
            # lesquelles l'user est contributeur ou en attente de validation
            con_org_bl = [e.organisation.pk for e in LiaisonsContributeurs.objects.filter(profile=self._profile)]
            self.fields['contributions'].queryset = Organisation.objects.exclude(pk__in=con_org_bl).exclude(is_active=False)

            # Idem "Référent"
            ref_org_bl = [e.organisation.pk for e in LiaisonsReferents.objects.filter(profile=self._profile)]
            self.fields['referents'].queryset = Organisation.objects.exclude(pk__in=ref_org_bl).exclude(is_active=False)

            organisation = self._profile.organisation
            if organisation:
                if not organisation.is_active:  # L'organisation est en attente de validation par l'administrateur
                    self.fields['organisation'].widget = forms.HiddenInput()

                else:
                    if not self._profile.membership:  # Si l'utilisateur est en attente de rattachement
                        self.fields['organisation'].widget = forms.HiddenInput()
                    else:
                        self.fields['organisation'].initial = organisation.pk
                        self.fields['organisation'].queryset = Organisation.objects.exclude(is_active=False)
            else:
                self.fields['organisation'].queryset = Organisation.objects.exclude(is_active=False)

        if self.include_args['action'] == 'create':
            self.fields['organisation'].queryset = \
                Organisation.objects.exclude(is_active=False)

    def clean(self):

        params = ['address', 'city', 'description',
                  'jurisdiction', 'license', 'logo',
                  'organisation_type', 'org_phone', 'postcode',
                  'new_orga', 'website']

        if self.cleaned_data.get('referent_requested'):
            self.cleaned_data['referent_requested'] = True
        if self.cleaned_data.get('contribution_requested') and not self.cleaned_data.get('referent_requested'):
            self.cleaned_data['contribution_requested'] = True

        if self.cleaned_data.get('new_orga'):
            self.cleaned_data['organisation'] = None

            # On vérifie si l'organisation n'existe pas déjà auquel cas on retourne une erreur.
            if Organisation.objects.filter(
                    ckan_slug=slugify(self.cleaned_data['new_orga'])).exists():
                self.add_error('new_orga', "L'organisation existe déjà.")
                raise ValidationError('OrganisationExist')

            self.cleaned_data['mode'] = 'require_new_organization'

            for p in params:
                self.cleaned_data[p] = self.cleaned_data.get(p)

            return self.cleaned_data

        # On vide les valeurs d'une nouvelle organisation par sécurité
        for p in params:
            self.cleaned_data[p] = ''

        organisation = self.cleaned_data.get('organisation')

        if not organisation:  # TODO
            self.cleaned_data['mode'] = 'no_organization_please'
            return self.cleaned_data

        if self.include_args['action'] in ("update", "update_organization"):

            if organisation != self._profile.organisation:
                self.cleaned_data['mode'] = 'change_organization'
                return self.cleaned_data

        if self.include_args['action'] == 'create':
            self.cleaned_data['mode'] = 'change_organization'
            return self.cleaned_data

        self.cleaned_data['mode'] = 'nothing_to_do'

        return self.cleaned_data


class SignInForm(MamaLoginForm):

    username = common_fields.USERNAME
    password = common_fields.PASSWORD1

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

    username = common_fields.USERNAME
    password = common_fields.PASSWORD1

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
            'password1',
            'password2')

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
            'contributor_process',
            'referent_process')

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

    contributor_process = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>contributeur</strong> de l'organisation",
        required=False)

    referent_process = forms.BooleanField(
        initial=False,
        label="Je souhaite être <strong>référent technique</strong> de l'organisation",
        required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['password'] = cleaned_data.pop('password1')
        self.cleaned_data = cleaned_data
        return self.cleaned_data

    @property
    def rattachement_process(self):
        return self.cleaned_data.get('organisation', False)

    # @property
    # def contributor_process(self):
    #     return self.cleaned_data.get('contributor_process', False)

    # @property
    # def referent_process(self):
    #     return self.cleaned_data.get('referent_process', False)

    @property
    def create_organisation(self):
        return self.cleaned_data.get('new_orga', None)

    @property
    def cleaned_organisation_data(self):
        return dict((item, self.cleaned_data[item])
                    for item in self.Meta.organisation_fields)

    @property
    def cleaned_user_data(self):
        return dict((item, self.cleaned_data[item])
                    for item in self.Meta.user_fields)

    @property
    def cleaned_profile_data(self):
        return dict((item, self.cleaned_data[item])
                    for item in self.Meta.profile_fields)
