from django import forms
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core import validators
from django.core.exceptions import ValidationError
from django.forms import CheckboxSelectMultiple, inlineformset_factory


from profiles.models import Profile, Organisation, PublishRequest
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


class UserUpdateForm(forms.ModelForm):
    first_name = fields.FIRST_NAME
    last_name = fields.LAST_NAME

    password1 = forms.CharField(required=False,label='Mot de passe',
                                max_length=150, min_length=6,
                                widget=forms.PasswordInput(attrs={'placeholder': 'Mot de passe'}))

    password2 = forms.CharField(label="Password confirmation", required=False,
                                max_length=150, min_length=6,
                                widget=forms.PasswordInput(attrs={'placeholder': 'Mot de passe'}))
    username = forms.CharField(widget=forms.HiddenInput(), required=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'username')

    def save_f(self, request):

        if self.cleaned_data['password1'] != self.cleaned_data['password2']:
            self.add_error('password1', 'Vérifiez les champs mot de passe')
            self.add_error('password2', '')
            raise ValidationError('password error')

        user = User.objects.get(username=self.cleaned_data["username"])
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.username = self.cleaned_data["username"]

        password = self.cleaned_data["password1"]
        if password:
            user.set_password(password)
            user.save()
            logout(request)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        user.save()
        return user


class UserProfileForm(forms.Form):


    def clean(self):

        organisation = self.cleaned_data.get('organisation')

        if organisation is None:
            # Retourne le nom d'une nouvelle organisation si demande de creation
            self.cleaned_data['organisation'] = self.cleaned_data.get('new_orga')
            self.cleaned_data['website'] = self.cleaned_data.get('website')
            self.cleaned_data['is_new_orga'] = True

        else:
            # Mettre les valeurs de new_orga et website lorsque l'user a deja choisi parmi la liste déroulante
            self.cleaned_data['new_orga'] = ''
            self.cleaned_data['website'] = ''
            self.cleaned_data['is_new_orga'] = False

            # Pour ne manipuler que le nom de l'organisation meme si existante
            self.cleaned_data['organisation'] = self.cleaned_data['organisation'].name

        return self.cleaned_data


    organisation = forms.ModelChoiceField(required=False,
                                          label='Organisme',
                                          queryset=Organisation.objects.all())

    new_orga = forms.CharField(
        error_messages={'invalid': 'invalid'},
        label="Nom de l'organisme",
        max_length=255,
        min_length=3,
        required=False,
        validators=[validators.validate_slug],
        widget=forms.TextInput(attrs={'placeholder': "Nom de l'organisme"}))

    new_website = forms.URLField(
        error_messages={
            'invalid': "L'adresse URL est éronée. "},
        label="URL du site internet de l'organisme",
        required = False)

    is_new_orga = forms.BooleanField(widget=forms.HiddenInput(),
                                     required=False, initial=False)

    phone = fields.PHONE

    role = fields.ROLE

    class Meta:
        model = Profile
        fields = ('organisation', 'role', 'phone',
                  'new_orga', 'new_website', 'is_new_orga')


class ProfileUpdateForm(forms.ModelForm):

    organisation = forms.ModelChoiceField(required=False,
                                          label='Organisme',
                                          queryset=Organisation.objects.all())

    publish_for = forms.ModelChoiceField(required=False,
                                         label='Organismes associés',
                                         widget=forms.RadioSelect,
                                         queryset=Organisation.objects.all())

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
        fields = ('organisation', 'phone', 'role', 'publish_for')


    def save_f(self, commit=True):
        profile = super(ProfileUpdateForm, self).save(commit=False)


        org = self.cleaned_data['organisation']

        if org:
            profile.organisation = org

        if commit:
            profile.save()
        return profile


class UserLoginForm(AuthenticationForm):

    username = fields.USERNAME
    password = fields.PASSWORD1

    class Meta:
        model = User
        fields = ('username', 'password')

class UserDeleteForm(AuthenticationForm):

    username = fields.USERNAME
    password = fields.PASSWORD1

    class Meta:
        model = User
        fields = ('username', 'password')


# class PublishRequestForm(forms.ModelForm):
#
#     publish_for = forms.ModelMultipleChoiceField(required=False,
#                                                  label='Organismes publication',
#                                                  widget=CheckboxSelectMultiple(),
#                                                  queryset=Organisation.objects.all())
#     class Meta:
#         model = PublishRequest
#         fields = ('organisation', 'date_demande', 'date_acceptation')
#
#     def save_f(self, commit=True):
#         publish_request = super(PublishRequestForm, self).save(commit=False)
#
#         publish_for = self.cleaned_data["publish_for"]
