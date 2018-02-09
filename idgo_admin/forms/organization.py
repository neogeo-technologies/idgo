from django import forms
from django.core import validators
from idgo_admin.models import Organisation
# from idgo_admin.models import OrganisationType


class OrganizationForm(forms.ModelForm):

    class Meta(object):
        model = Organisation
        fields = ('name',
                  'logo',
                  'address',
                  'city',
                  'postcode',
                  # 'phone',
                  # 'email',
                  'website',
                  'description'
                  )

    name = forms.CharField(
        error_messages={"Nom de l'organisation invalide": 'invalid'},
        label="Nom de l'organisation",
        max_length=255,
        min_length=3,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': "Nom de l'organisation"}))

    logo = forms.ImageField(
        label="Logo de l'organisation",
        required=False)

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

    postcode = forms.CharField(
        required=False,
        label='Code postal',
        max_length=10,
        widget=forms.TextInput(
            attrs={'placeholder': 'Code postal'}))

    phone = forms.CharField(
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
        widget=forms.EmailInput(
            attrs={'placeholder': 'Adresse e-mail'}))

    website = forms.URLField(
        error_messages={'invalid': "L'adresse URL est erronée. "},
        label="URL du site internet de l'organisation", required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Site internet'}))

    description = forms.CharField(
        required=False,
        label='Description',
        widget=forms.Textarea(
            attrs={'placeholder': 'Description'}))

    def __init__(self, *args, **kwargs):
        self.include_args = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)

    def clean(self):
        return self.cleaned_data

    def handle_me(self, request, id=None):

        data = self.cleaned_data

        instance = Organisation.objects.get(pk=id)
        for key, value in data.items():
            setattr(instance, key, value)

        instance.save()

        return instance
