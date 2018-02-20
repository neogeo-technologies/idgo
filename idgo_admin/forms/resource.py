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


from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django import forms
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.exceptions import SizeLimitExceededError
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats
from idgo_admin.utils import download
from idgo_admin.utils import readable_file_size
import json
from pathlib import Path


try:
    DOWNLOAD_SIZE_LIMIT = settings.DOWNLOAD_SIZE_LIMIT
except AttributeError:
    DOWNLOAD_SIZE_LIMIT = 104857600  # 100Mio


def get_all_users_for_organizations(list_id):
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


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
                  'sync_frequency')

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

    def __init__(self, *args, **kwargs):
        self.include_args = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)

    def handle_me(self, request, dataset, id=None, uploaded_file=None):

        user = request.user
        data = self.cleaned_data
        restricted_level = data['restricted_level']
        profiles_allowed = data['profiles_allowed']
        organizations_allowed = data['organisations_allowed']

        params = {'name': data['name'],
                  'description': data['description'],
                  'dl_url': data['dl_url'],
                  'referenced_url': data['referenced_url'],
                  'lang': data['lang'],
                  'format_type': data['format_type'],
                  'restricted_level': restricted_level,
                  'up_file': data['up_file'],
                  'dataset': dataset}

        if id:  # Mise à jour de la ressource
            created = False
            resource = Resource.objects.get(pk=id)
            for key, value in params.items():
                setattr(resource, key, value)
        else:  # Création d'une nouvelle ressource
            created = True
            resource = Resource.objects.create(**params)

        ckan_params = {
            'name': resource.name,
            'description': resource.description,
            'format': resource.format_type.extension,
            'view_type': resource.format_type.ckan_view,
            'id': str(resource.ckan_id),
            'lang': resource.lang,
            'url': ''}

        if restricted_level == '0':  # Public
            resource.profiles_allowed = profiles_allowed
            ckan_params['restricted'] = json.dumps({'level': 'public'})

        if restricted_level == '1':  # Registered users
            resource.profiles_allowed = profiles_allowed
            ckan_params['restricted'] = json.dumps({'level': 'registered'})

        if restricted_level == '2':  # Only allowed users
            resource.profiles_allowed = profiles_allowed
            ckan_params['restricted'] = json.dumps({
                'allowed_users': ','.join([p.user.username for p in profiles_allowed]),
                'level': 'only_allowed_users'})

        if restricted_level == '3':  # This organization
            resource.organisations_allowed = [dataset.organisation]
            ckan_params['restricted'] = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organizations([dataset.organisation])),
                'level': 'only_allowed_users'})

        if restricted_level == '4':  # Any organization
            resource.organisations_allowed = organizations_allowed
            ckan_params['restricted'] = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organizations(organizations_allowed)),
                'level': 'only_allowed_users'})

        if resource.referenced_url:
            ckan_params['url'] = resource.referenced_url
            ckan_params['resource_type'] = \
                '{0}.{1}'.format(resource.name, resource.format_type.ckan_view)

        if resource.dl_url:
            try:
                filename, content_type = download(
                    resource.dl_url, settings.MEDIA_ROOT,
                    max_size=DOWNLOAD_SIZE_LIMIT)
            except SizeLimitExceededError as e:
                l = len(str(e.max_size))
                if l > 6:
                    m = '{0} mo'.format(Decimal(int(e.max_size) / 1024 / 1024))
                elif l > 3:
                    m = '{0} ko'.format(Decimal(int(e.max_size) / 1024))
                else:
                    m = '{0} octets'.format(int(e.max_size))
                raise ValidationError(
                    "La taille du fichier dépasse la limite autorisée : {0}.".format(m), code='dl_url')

            downloaded_file = File(open(filename, 'rb'))
            ckan_params['upload'] = downloaded_file
            ckan_params['size'] = downloaded_file.size
            ckan_params['mimetype'] = content_type
            ckan_params['resource_type'] = Path(filename).name

        if uploaded_file:
            ckan_params['upload'] = resource.up_file.file
            ckan_params['size'] = uploaded_file.size
            ckan_params['mimetype'] = uploaded_file.content_type
            ckan_params['resource_type'] = uploaded_file.name

        # Si l'utilisateur courant n'est pas l'éditeur d'un jeu
        # de données existant mais administrateur de données,
        # alors l'admin Ckan édite le jeu de données..
        # TODO: Factoriser avec form/dataset.py
        profile = Profile.objects.get(user=user)
        is_admin = profile.is_admin
        is_referent = LiaisonsReferents.objects.filter(
            profile=profile, organisation=dataset.organisation).exists()
        is_editor = (user == dataset.editor)
        if is_admin and not is_referent and not is_editor:
            ckan_user = ckan_me(ckan.apikey)
        else:
            ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        try:
            ckan_user.publish_resource(str(dataset.ckan_id), **ckan_params)
        except Exception as e:
            if created:
                resource.delete()
            raise e
        else:
            resource.last_update = timezone.now().date()
            resource.save()
        finally:
            ckan_user.close()

        return resource

    def clean(self):

        up_file = self.cleaned_data.get('up_file', None)
        dl_url = self.cleaned_data.get('dl_url', None)
        referenced_url = self.cleaned_data.get('referenced_url', None)
        res_l = [up_file, dl_url, referenced_url]
        if all(v is None for v in res_l):
            self.add_error('up_file', "Veuillez indiquer un type de ressource.")
            self.add_error('dl_url', "Veuillez indiquer un type de ressource.")
            self.add_error('referenced_url', "Veuillez indiquer un type de ressource.")
            raise ValidationError('ResourceType')
        if sum(v is not None for v in res_l) > 1:
            self.add_error('up_file', "Un seul type de ressource n'est autorisé.")
            self.add_error('dl_url', "Un seul type de ressource n'est autorisé.")
            self.add_error('referenced_url', "Un seul type de ressource n'est autorisé.")
            raise ValidationError('ResourceType')
