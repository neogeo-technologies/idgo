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
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats
from idgo_admin.utils import readable_file_size


try:
    DOWNLOAD_SIZE_LIMIT = settings.DOWNLOAD_SIZE_LIMIT
except AttributeError:
    DOWNLOAD_SIZE_LIMIT = 104857600  # 100Mio


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
        fields = ('up_file',
                  'dl_url',
                  'referenced_url',
                  'name',
                  'description',
                  'lang',
                  'format_type',
                  'restricted_level',
                  'profiles_allowed',
                  'organisations_allowed',
                  'synchronisation',
                  'sync_frequency')

    # _instance = None
    _dataset = None

    class CustomClearableFileInput(forms.ClearableFileInput):
        template_name = 'idgo_admin/widgets/file_drop_zone.html'

    up_file = forms.FileField(
        label='Téléversement',
        required=False,
        validators=[file_size],
        widget=CustomClearableFileInput(
            attrs={'max_size_info': DOWNLOAD_SIZE_LIMIT}))

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

    profiles_allowed = forms.ModelMultipleChoiceField(
        label='Utilisateurs autorisés',
        queryset=Profile.objects.filter(is_active=True),
        required=False,
        to_field_name='pk')

    organisations_allowed = forms.ModelMultipleChoiceField(
        label='Organisations autorisées',
        queryset=Organisation.objects.filter(is_active=True),
        required=False,
        to_field_name='pk')

    synchronisation = forms.BooleanField(
        initial=False,
        label='Synchroniser les données',
        required=False)

    sync_frequency = forms.ChoiceField(
        label='Fréquence de synchronisation',
        choices=Meta.model.FREQUENCY_CHOICES,
        required=False)

    def __init__(self, *args, **kwargs):
        self.include_args = kwargs.pop('include', {})
        self._dataset = kwargs.pop('dataset', None)

        super().__init__(*args, **kwargs)

    def clean(self):

        up_file = self.cleaned_data.get('up_file', None)
        dl_url = self.cleaned_data.get('dl_url', None)
        referenced_url = self.cleaned_data.get('referenced_url', None)

        res_l = [up_file, dl_url, referenced_url]
        if all(v is None for v in res_l):
            for field in ('up_file', 'dl_url', 'referenced_url'):
                self.add_error(field, 'Ce champ est obligatoire.')

        if sum(v is not None for v in res_l) > 1:
            error_msg = "Un seul type de ressource n'est autorisé."
            up_file and self.add_error('up_file', error_msg)
            dl_url and self.add_error('dl_url', error_msg)
            referenced_url and self.add_error('referenced_url', error_msg)

        self.cleaned_data['organisations_allowed'] = [self._dataset.organisation]
        self.cleaned_data['last_update'] = timezone.now().date()

    def handle_me(self, request, dataset, id=None):

        user = request.user

        memory_up_file = request.FILES.get('up_file')
        file_extras = memory_up_file and {
            'mimetype': memory_up_file.content_type,
            'resource_type': memory_up_file.name,
            'size': memory_up_file.size} or None

        data = self.cleaned_data
        params = {'dataset': dataset,
                  'description': data['description'],
                  'dl_url': data['dl_url'],
                  'format_type': data['format_type'],
                  'lang': data['lang'],
                  'last_update': data['last_update'],
                  'name': data['name'],
                  # 'organizations_allowed': None,
                  # 'profiles_allowed': None,
                  'referenced_url': data['referenced_url'],
                  'restricted_level': data['restricted_level'],
                  'sync_frequency': data['sync_frequency'],
                  'synchronisation': data['synchronisation'],
                  'up_file': data['up_file']}

        if id:  # Mise à jour de la ressource
            resource = Resource.objects.get(pk=id)
            for key, value in params.items():
                setattr(resource, key, value)
            resource.save(editor=user, file_extras=file_extras)
        else:  # Création d'une nouvelle ressource
            resource = Resource.objects.create(**params)

        resource.organizations_allowed = data['organisations_allowed']
        resource.profiles_allowed = data['profiles_allowed']
        resource.save(editor=user, file_extras=file_extras, sync_ckan=True)

        return resource
