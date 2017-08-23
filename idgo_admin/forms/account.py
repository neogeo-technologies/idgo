from . import common_fields
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django import forms
from django.utils.text import slugify
from idgo_admin.models import Financeur
from idgo_admin.models import Liaisons_Contributeurs
from idgo_admin.models import Liaisons_Referents
from idgo_admin.models import License
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType
from idgo_admin.models import Profile
from idgo_admin.models import Status
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

    def clean(self):

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

    username = forms.CharField(widget=forms.HiddenInput(), required=False)
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

    phone = common_fields.PHONE
    role = common_fields.ROLE

    # Champs Organisation
    organisation = forms.ModelChoiceField(
        required=False,
        label='Organisation',
        queryset=Organisation.objects.all())

    parent = forms.ModelChoiceField(
        required=False,
        label='Organisation parent',
        queryset=Organisation.objects.all())

    new_orga = forms.CharField(
        error_messages={"Nom de l'organisation invalide": 'invalid'},
        label="Nom de l'organisation",
        max_length=255,
        min_length=3,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': "Nom de l'organisation"}))

    website = forms.URLField(
        error_messages={'invalid': "L'adresse URL est erronée. "},
        label="URL du site internet de l'organisation", required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Site internet'}))

    code_insee = forms.CharField(
        required=False,
        label='Territoire de compétence',
        max_length=10,
        widget=forms.TextInput(
            attrs={'placeholder': 'Territoire de compétence'}))

    description = forms.CharField(
        required=False,
        label="Description",
        max_length=1024,
        widget=forms.Textarea(
            attrs={'placeholder': "Description"}))

    adresse = forms.CharField(
        required=False,
        label="Adresse",
        max_length=1024,
        widget=forms.TextInput(
            attrs={'placeholder': "Numéro de voirie et rue"}))

    code_postal = forms.CharField(
        required=False,
        label="Code postal",
        max_length=10,
        widget=forms.TextInput(
            attrs={'placeholder': "Code postal"}))

    ville = forms.CharField(
        required=False,
        label="Ville",
        max_length=150,
        widget=forms.TextInput(
            attrs={'placeholder': "Ville"}))

    org_phone = common_fields.PHONE

    organisation_type = forms.ModelChoiceField(
        required=False,
        label="Type d'organisation",
        queryset=OrganisationType.objects.all())

    financeur = forms.ModelChoiceField(
        required=False,
        label='Financeur',
        queryset=Financeur.objects.all())

    status = forms.ModelChoiceField(
        required=False,
        label='Statut',
        queryset=Status.objects.all())

    license = forms.ModelChoiceField(
        required=False,
        label='Licence par défaut pour tout nouveau jeu de données',
        queryset=License.objects.all())

    referent_requested = forms.BooleanField(
        initial=True,
        label='Je suis référent',
        required=False)

    contribution_requested = forms.BooleanField(
        initial=True,
        label="Je souhaite être contributeur pour l'organisation",
        required=False)

    referents = forms.ModelChoiceField(
        required=False,
        label='Référent pour ces organisations',
        widget=forms.RadioSelect(),
        queryset=Organisation.objects.all())

    contributions = forms.ModelChoiceField(
        required=False,
        label='Organisation de contribution',
        widget=forms.RadioSelect(),
        queryset=Organisation.objects.all())

    logo = forms.ImageField(
        label="Logo de l'organisation",
        required=False)

    class Meta(object):
        model = Profile
        fields = ('phone', 'role', 'organisation')

    def __init__(self, *args, **kwargs):

        self.include_args = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)

        if self.include_args['action'] == 'update':
            self._profile = Profile.objects.get(user=self.include_args['user'])
            # On exclut de la liste de choix toutes les organisations pour
            # lesquelles l'user est contributeur ou en attente de validation
            con_org_bl = [e.organisation.pk for e in Liaisons_Contributeurs.objects.filter(profile=self._profile)]
            self.fields['contributions'].queryset = Organisation.objects.exclude(pk__in=con_org_bl).exclude(is_active=False)

            # Idem "Référent"
            ref_org_bl = [e.organisation.pk for e in Liaisons_Referents.objects.filter(profile=self._profile)]
            self.fields['referents'].queryset = Organisation.objects.exclude(pk__in=ref_org_bl).exclude(is_active=False)

            organisation = self._profile.organisation
            if organisation:
                if not organisation.is_active:  # L'organisation est en attente de validation par l'administrateur
                    self.fields['organisation'].widget = forms.HiddenInput()
                else:
                    if not self._profile.rattachement_active:  # Si l'utilisateur est en attente de rattachement
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
        params = ['adresse', 'code_insee', 'code_postal', 'description',
                  'financeur', 'license', 'organisation_type', 'org_phone'
                  'parent', 'status', 'ville', 'website', 'logo', 'new_orga']

        if self.cleaned_data.get('referent_requested'):
            self.cleaned_data['referent_requested'] = True
        if self.cleaned_data.get('contribution_requested'):
            self.cleaned_data['contribution_requested'] = True
        if self.cleaned_data['new_orga']:
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

        if self.include_args['action'] == 'update':
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
