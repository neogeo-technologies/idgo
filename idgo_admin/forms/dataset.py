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
from django.core.exceptions import ValidationError
from django import forms
from django.forms.models import ModelChoiceIterator
from django.utils import timezone
from idgo_admin.models import Category
from idgo_admin.models import Dataset
from idgo_admin.models import DataType
from idgo_admin.models import Granularity
from idgo_admin.models import License
from idgo_admin.models import Organisation
from idgo_admin.models import Support
from idgo_admin.shortcuts import user_and_profile
import re
from taggit.forms import TagField
from taggit.forms import TagWidget


DOMAIN_NAME = settings.DOMAIN_NAME
GEONETWORK_URL = settings.GEONETWORK_URL
CKAN_URL = settings.CKAN_URL
DEFAULT_CONTACT_EMAIL = settings.DEFAULT_CONTACT_EMAIL
DEFAULT_PLATFORM_NAME = settings.DEFAULT_PLATFORM_NAME

TODAY = timezone.now().date()
TODAY_STR = TODAY.strftime('%d/%m/%Y')


class DatatypeModelIterator(ModelChoiceIterator):

    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        queryset = self.queryset
        if not queryset._prefetch_related_lookups:
            queryset = queryset.iterator()
        for obj in queryset:
            if obj.ckan_slug == 'donnees-moissonnees':
                continue
            yield self.choice(obj)


class DatatypeModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    iterator = DatatypeModelIterator


class DatatypeField(DatatypeModelMultipleChoiceField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', 'Type de données')
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.CheckboxSelectMultiple())
        kwargs.setdefault('queryset', DataType.objects.all())

        super().__init__(*args, **kwargs)


class DatasetForm(forms.ModelForm):

    class Meta(object):
        model = Dataset
        fields = (
            'broadcaster_email',
            'broadcaster_name',
            'categories',
            'data_type',
            'date_creation',
            'date_modification',
            'date_publication',
            'description',
            'geocover',
            'granularity',
            'is_inspire',
            'keywords',
            'license',
            'organisation',
            'owner_email',
            'owner_name',
            'published',
            'support',
            'thumbnail',
            'update_freq',
            'name',
            'ckan_slug')

    class CustomClearableFileInput(forms.ClearableFileInput):
        template_name = 'idgo_admin/widgets/file_drop_zone.html'

    name = forms.CharField(
        label='Titre*',
        required=True,
        widget=forms.Textarea(
            attrs={
                'placeholder': 'Titre du jeu de données',
                'rows': 1}))

    ckan_slug = forms.CharField(
        label='URL du jeu de données',
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                'addon_before': '{}/dataset/'.format(CKAN_URL),
                'addon_before_class': 'input-group-addon',
                'addon_after': '<button class="btn btn-default" type="button" />',
                'addon_after_class': 'input-group-btn',
                'autocomplete': 'off',
                'readonly': True,
                # 'pattern': '^[a-z0-9\-]{1,100}$',  # Déplacé dans la function 'clean'
                'placeholder': ''}))

    description = forms.CharField(
        label='Description',
        required=False,
        widget=forms.Textarea(
            attrs={
                'placeholder': 'Vous pouvez utiliser le langage Markdown ici'}))

    keywords = TagField(
        label='Liste de mots-clés',
        required=False,
        widget=TagWidget(
            attrs={
                'autocomplete': 'off',
                'class': 'typeahead',
                'placeholder': 'Utilisez la virgule comme séparateur'}))

    categories = forms.ModelMultipleChoiceField(
        label='Catégories associées',
        queryset=Category.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple())

    data_type = DatatypeField()

    date_creation = forms.DateField(
        label='Date de création',
        required=False,
        widget=forms.DateInput(
            attrs={
                'autocomplete': 'off',
                'class': 'datepicker',
                'placeholder': '{0} (valeur par défaut)'.format(TODAY_STR)}))

    date_modification = forms.DateField(
        label='Date de dernière modification',
        required=False,
        widget=forms.DateInput(
            attrs={
                'autocomplete': 'off',
                'class': 'datepicker',
                'placeholder': '{0} (valeur par défaut)'.format(TODAY_STR)}))

    date_publication = forms.DateField(
        label='Date de publication',
        required=False,
        widget=forms.DateInput(
            attrs={
                'autocomplete': 'off',
                'class': 'datepicker',
                'placeholder': '{0} (valeur par défaut)'.format(TODAY_STR)}))

    update_freq = forms.ChoiceField(
        choices=Dataset.FREQUENCY_CHOICES,
        label='Fréquence de mise à jour',
        required=False)

    geocover = forms.ChoiceField(
        choices=Dataset.GEOCOVER_CHOICES,
        label='Couverture géographique',
        required=False)

    granularity = forms.ModelChoiceField(
        empty_label='Sélectionnez une valeur',
        label='Granularité de la couverture territoriale',
        queryset=Granularity.objects.all(),
        required=False)

    organisation = forms.ModelChoiceField(
        label='Organisation à laquelle est rattaché ce jeu de données*',
        queryset=Organisation.objects.all(),
        required=True,
        empty_label='Sélectionnez une organisation')

    license = forms.ModelChoiceField(
        label='Licence*',
        queryset=License.objects.all(),
        required=True,
        empty_label='Sélectionnez une licence')

    owner_name = forms.CharField(
        label='Nom du producteur', required=False)

    owner_email = forms.EmailField(
        error_messages={
            'invalid': "L'adresse e-mail est invalide."},
        label='Adresse e-mail du producteur', required=False)

    broadcaster_name = forms.CharField(
        label='Nom du diffuseur', required=False)

    broadcaster_email = forms.EmailField(
        error_messages={
            'invalid': "L'adresse e-mail est invalide."},
        label='Adresse e-mail du diffuseur', required=False)

    published = forms.BooleanField(
        initial=True,
        label='Publier le jeu de données',
        required=False)

    support = forms.ModelChoiceField(
        label='Support technique',
        queryset=Support.objects.all(),
        required=False,
        empty_label='Aucun')

    is_inspire = forms.BooleanField(
        initial=False,
        label='Le jeu de données est soumis à la règlementation INSPIRE',
        required=False)

    thumbnail = forms.FileField(
        label='Imagette',
        required=False,
        # validators=[],
        widget=CustomClearableFileInput(
            attrs={
                'value': None,
                'max_size_info': 1048576}))

    def __init__(self, *args, **kwargs):
        self.include_args = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)

        instance = kwargs.get('instance', None)
        owner = instance \
            and instance.editor or self.include_args.get('user')

        self.fields['organisation'].queryset = Organisation.objects.filter(
            liaisonscontributeurs__profile=owner.profile,
            liaisonscontributeurs__validated_on__isnull=False)

        self.fields['owner_name'].initial = owner.get_full_name()
        self.fields['owner_name'].widget.attrs['placeholder'] = \
            '{} (valeur par défaut)'.format(owner.get_full_name())

        self.fields['owner_email'].initial = owner.email
        self.fields['owner_email'].widget.attrs['placeholder'] = \
            '{} (valeur par défaut)'.format(owner.email)

        self.fields['broadcaster_name'].widget.attrs['placeholder'] = \
            instance and instance.support and instance.support.name or DEFAULT_PLATFORM_NAME
        self.fields['broadcaster_email'].widget.attrs['placeholder'] = \
            instance and instance.support and instance.support.email or DEFAULT_CONTACT_EMAIL

        if instance and instance.thumbnail:
            self.fields['thumbnail'].widget.attrs['value'] = instance.thumbnail.url

    def clean(self):

        name = self.cleaned_data.get('name')

        if not re.match('^[a-z0-9\-]{1,100}$', self.cleaned_data.get('ckan_slug')):
            self.add_error('ckan_slug', (
                "Seuls les caractères alphanumériques et le tiret sont "
                "autorisés (100 caractères maximum)."))
            raise ValidationError('KeywordsError')

        if self.include_args['identification']:
            dataset = Dataset.objects.get(id=self.include_args['id'])
            if name != dataset.name and Dataset.objects.filter(name=name).exists():
                self.add_error('name', 'Ce nom est réservé.')
                raise ValidationError('NameError')

        if not self.include_args['identification'] \
                and Dataset.objects.filter(name=name).exists():
            self.add_error('name', 'Le jeu de données "{0}" existe déjà'.format(name))
            raise ValidationError("Dataset '{0}' already exists".format(name))

        kwords = self.cleaned_data.get('keywords')
        if kwords:
            for w in kwords:
                if len(w) < 2:
                    self.add_error('keywords', "La taille minimum pour un mot clé est de 2 caractères. ")
                    raise ValidationError("KeywordsError")
                regex = '^[a-zA-Z0-9áàâäãåçéèêëíìîïñóòôöõúùûüýÿæœÁÀÂÄÃÅÇÉÈÊËÍÌÎÏÑÓÒÔÖÕÚÙÛÜÝŸÆŒ\._\-\s]*$'
                if not re.match(regex, w):
                    self.add_error('keywords', "Les mots-clés ne peuvent pas contenir de caractères spéciaux. ")
                    raise ValidationError('KeywordsError')

        return self.cleaned_data

    def handle_me(self, request, id=None):
        user, profile = user_and_profile(request)

        data = self.cleaned_data
        params = {
            'broadcaster_name': data['broadcaster_name'],
            'broadcaster_email': data['broadcaster_email'],
            'ckan_slug': data['ckan_slug'],
            'date_creation': data['date_creation'],
            'date_modification': data['date_modification'],
            'date_publication': data['date_publication'],
            'description': data['description'],
            'editor': user,
            'geocover': data['geocover'],
            'granularity': data['granularity'],
            'license': data['license'],
            'name': data['name'],
            'organisation': data['organisation'],
            'owner_email': data['owner_email'],
            'owner_name': data['owner_name'],
            'update_freq': data['update_freq'],
            'published': data['published'],
            'support': data['support'],
            'thumbnail': data['thumbnail'],
            'is_inspire': data['is_inspire']}

        if id:  # Mise à jour du jeu de données
            params.pop('editor', None)
            dataset = Dataset.objects.get(pk=id)
            for key, value in params.items():
                setattr(dataset, key, value)
        else:  # Création d'un nouveau jeu de données
            dataset = Dataset.objects.create(**params)

        dataset.categories.set(data.get('categories', []), clear=True)

        if data.get('keywords'):
            dataset.keywords.clear()
            for tag in data['keywords']:
                dataset.keywords.add(tag)

        dataset.data_type.set(data.get('data_type', []), clear=True)

        dataset.save(editor=user, sync_ckan=True)
        return dataset
