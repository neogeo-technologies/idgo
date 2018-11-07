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
from django.utils import timezone
from idgo_admin.forms import CustomCheckboxSelectMultiple
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats
from idgo_admin.models import SupportedCrs
from idgo_admin.utils import readable_file_size
import os


try:
    DOWNLOAD_SIZE_LIMIT = settings.DOWNLOAD_SIZE_LIMIT
except AttributeError:
    DOWNLOAD_SIZE_LIMIT = 104857600  # 100Mio

FTP_DIR = settings.FTP_DIR


def list_filenames_in_ftp_account(username):
    filenames = []
    for path, subdirs, files in os.walk(os.path.join(FTP_DIR, username)):
        for name in files:
            filenames.append(os.path.join(path, name))
    return filenames


def file_size(value):
    size_limit = DOWNLOAD_SIZE_LIMIT
    if value.size > size_limit:
        message = \
            'Le fichier {0} ({1}) dépasse la limite de taille autorisée {2}.'.format(
                value.name, readable_file_size(value.size), readable_file_size(size_limit))
        raise ValidationError(message)


class ResourceForm(forms.ModelForm):

    class Meta(object):
        model = Resource
        fields = ('crs',
                  'data_type',
                  'description',
                  'dl_url',
                  'extractable',
                  'format_type',
                  'ftp_file',
                  'geo_restriction',
                  'lang',
                  'name',
                  'ogc_services',
                  'organisations_allowed',
                  'profiles_allowed',
                  'referenced_url',
                  'restricted_level',
                  'synchronisation',
                  'sync_frequency',
                  'up_file')

    # _instance = None
    _dataset = None

    class CustomClearableFileInput(forms.ClearableFileInput):
        template_name = 'idgo_admin/widgets/file_drop_zone.html'

    ftp_file = forms.ChoiceField(
        label='Fichier déposé sur FTP',
        choices=[],
        required=False)

    up_file = forms.FileField(
        label='Téléversement',
        required=False,
        validators=[file_size],
        widget=CustomClearableFileInput(
            attrs={
                'value': None,
                'max_size_info': DOWNLOAD_SIZE_LIMIT}))

    name = forms.CharField(
        label='Titre*',
        widget=forms.TextInput(
            attrs={'placeholder': 'Titre'}))

    description = forms.CharField(
        label='Description',
        required=False,
        widget=forms.Textarea(
            attrs={'placeholder': 'Vous pouvez utiliser le langage Markdown ici'}))

    format_type = forms.ModelChoiceField(
        empty_label='Sélectionnez un format',
        label='Format*',
        queryset=ResourceFormats.objects.all(),
        required=True)

    data_type = forms.ChoiceField(
        label='Type',
        choices=Meta.model.TYPE_CHOICES,
        required=False)

    profiles_allowed = forms.ModelMultipleChoiceField(
        label='Utilisateurs autorisés',
        queryset=Profile.objects.filter(is_active=True).order_by('user__last_name'),
        required=False,
        to_field_name='pk',
        widget=CustomCheckboxSelectMultiple(
            attrs={'class': 'list-group-checkbox'}))

    organisations_allowed = forms.ModelMultipleChoiceField(
        label='Organisations autorisées',
        queryset=Organisation.objects.filter(is_active=True).order_by('name'),
        required=False,
        to_field_name='pk',
        widget=CustomCheckboxSelectMultiple(
            attrs={'class': 'list-group-checkbox'}))

    synchronisation = forms.BooleanField(
        initial=False,
        label='Synchroniser les données',
        required=False)

    sync_frequency = forms.ChoiceField(
        label='Fréquence de synchronisation',
        choices=Meta.model.FREQUENCY_CHOICES,
        required=False)

    geo_restriction = forms.BooleanField(
        initial=False,
        label="Restreindre l'accès au territoire de compétence",
        required=False)

    extractable = forms.BooleanField(
        label="Activer le service d'extraction des données géographiques",
        required=False)

    ogc_services = forms.BooleanField(
        label="Activer les services OGC associés",
        required=False)

    crs = forms.ModelChoiceField(
        label='Système de coordonnées du jeu de données géographiques',
        queryset=SupportedCrs.objects.all(),
        required=False,
        to_field_name='auth_code')

    restricted_level = forms.ChoiceField(
        choices=Meta.model.LEVEL_CHOICES,
        label="Restriction d'accès",
        required=True)

    def __init__(self, *args, **kwargs):
        self.include_args = kwargs.pop('include', {})
        self._dataset = kwargs.pop('dataset', None)
        instance = kwargs.get('instance', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['ftp_file'].choices = [
            (f, f) for f in list_filenames_in_ftp_account(user.username)]

        if instance and instance.up_file:
            self.fields['up_file'].widget.attrs['value'] = instance.up_file

    def clean(self):

        up_file = self.cleaned_data.get('up_file', None)
        dl_url = self.cleaned_data.get('dl_url', None)
        referenced_url = self.cleaned_data.get('referenced_url', None)
        ftp_file = self.cleaned_data.get('ftp_file', None)

        res_l = [up_file, dl_url, referenced_url, ftp_file]
        if all(v is None for v in res_l):
            for field in ('up_file', 'dl_url', 'referenced_url', 'ftp_file'):
                self.add_error(field, 'Ce champ est obligatoire.')

        if sum(v is not None for v in res_l) > 1:
            error_msg = "Un seul type de ressource n'est autorisé."
            up_file and self.add_error('up_file', error_msg)
            dl_url and self.add_error('dl_url', error_msg)
            referenced_url and self.add_error('referenced_url', error_msg)
            ftp_file and self.add_error('ftp_file', error_msg)

        self.cleaned_data['last_update'] = timezone.now().date()

    def handle_me(self, request, dataset, id=None):

        user = request.user

        memory_up_file = request.FILES.get('up_file')
        file_extras = memory_up_file and {
            'mimetype': memory_up_file.content_type,
            'resource_type': memory_up_file.name,
            'size': memory_up_file.size} or None

        data = self.cleaned_data
        params = {'crs': data['crs'],
                  'data_type': data['data_type'],
                  'dataset': dataset,
                  'description': data['description'],
                  'dl_url': data['dl_url'],
                  'extractable': data['extractable'],
                  'format_type': data['format_type'],
                  'ftp_file': data['ftp_file'],
                  'geo_restriction': data['geo_restriction'],
                  'lang': data['lang'],
                  'last_update': data['last_update'],
                  'name': data['name'],
                  'ogc_services': data['ogc_services'],
                  # 'organizations_allowed': None,
                  # 'profiles_allowed': None,
                  'referenced_url': data['referenced_url'],
                  'restricted_level': data['restricted_level'],
                  'sync_frequency': data['sync_frequency'],
                  'synchronisation': data['synchronisation'],
                  'up_file': data['up_file']}

        if data['restricted_level'] == '2':
            data['profiles_allowed'] = data['profiles_allowed']
        if data['restricted_level'] == '3':
            data['organisations_allowed'] = [self._dataset.organisation]
        if data['restricted_level'] == '4':
            data['organisations_allowed'] = data['organisations_allowed']

        kwargs = {'editor': user, 'file_extras': file_extras, 'sync_ckan': True}

        if id:
            # Mise à jour de la ressource
            resource = Resource.objects.get(pk=id)
            for key, value in params.items():
                setattr(resource, key, value)
            resource.save(**kwargs)
        else:
            # Création d'une nouvelle ressource
            resource = Resource.objects.create(**params)
            resource.save(**kwargs)

        return resource
