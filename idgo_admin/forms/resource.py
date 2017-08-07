from django.conf import settings
from django.core.files import File
from django.db import IntegrityError
from django import forms
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.utils import download
import json
from pathlib import Path


_today = timezone.now().date()


def get_all_users_for_organizations(list_id):
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


class ResourceForm(forms.ModelForm):

    class CustomClearableFileInput(forms.ClearableFileInput):
        template_name = 'idgo_admin/clearable_file_input.html'

    up_file = forms.FileField(
        label='Téléversement',
        required=False,
        widget=CustomClearableFileInput())

    # dl_url

    # referenced_url

    name = forms.CharField(
        label='Titre',
        widget=forms.TextInput(
            attrs={'placeholder': 'Titre'}))

    description = forms.CharField(
        label='Description',
        required=False,
        widget=forms.Textarea(
            attrs={'placeholder': 'Vous pouvez utiliser le langage Markdown ici'}))

    # lang

    data_format = forms.CharField(
        label='Format',
        widget=forms.TextInput(
            attrs={'placeholder': 'CSV, XML, JSON, XLS... '}))

    # restricted_level

    # users_allowed

    # organisations_allowed

    class Meta(object):
        model = Resource
        fields = ('up_file',
                  'dl_url',
                  'referenced_url',
                  'name',
                  'description',
                  'lang',
                  'data_format',
                  'restricted_level',
                  'users_allowed',
                  'organisations_allowed')

    def handle_me(self, request, dataset, id=None, uploaded_file=None):

        user = request.user
        data = self.cleaned_data
        restricted_level = data['restricted_level']
        users_allowed = data['users_allowed']
        organizations_allowed = data['organisations_allowed']

        params = {'name': data['name'],
                  'description': data['description'],
                  'dl_url': data['dl_url'],
                  'referenced_url': data['referenced_url'],
                  'lang': data['lang'],
                  'data_format': data['data_format'],
                  'restricted_level': restricted_level,
                  'up_file': data['up_file'],
                  'dataset': dataset}

        if id:  # Mise à jour de la ressource
            resource = Resource.objects.get(pk=id)
            for key, value in params.items():
                setattr(resource, key, value)
        else:  # Création d'une nouvelle ressource
            resource = Resource.objects.create(**params)

        # TODO(cbenhabib) Lien ressource / user
        # profile = Profile.objects.get(user=user)
        # bonding = Liaisons_Resources.objects.create(
        #     profile=profile, resource=resource)
        # bonding.validated_on = timezone.now()
        # bonding.save()

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])

        ckan_params = {
            'name': resource.name,
            'description': resource.description,
            'format': resource.data_format,
            'id': str(resource.ckan_id),
            'lang': resource.lang,
            'url': ''}

        if restricted_level == '2':  # Registered users
            resource.users_allowed = users_allowed
            ckan_params['restricted'] = json.dumps({
                'allowed_users': ','.join([u.username for u in users_allowed]),
                'level': 'registered'})

        if restricted_level == '4':  # Any organization
            resource.organisations_allowed = organizations_allowed
            ckan_params['restricted'] = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organizations(data['organisations_allowed'])),
                'level': 'registered'})

        if resource.referenced_url:
            ckan_params['url'] = resource.referenced_url
            ckan_params['resource_type'] = \
                '{0}.{1}'.format(resource.name, resource.data_format)

        if resource.dl_url:
            filename, content_type = \
                download(resource.dl_url, settings.MEDIA_ROOT)
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

        try:
            ckan_user.publish_resource(str(dataset.ckan_id), **ckan_params)
        except Exception as e:
            # resource.sync_in_ckan = False
            # TODO Gérer correctement les erreurs
            raise IntegrityError('Une erreur est survenue lors de la création '
                                 'de la ressource dans CKAN : {0}'.format(e))
        else:
            # resource.sync_in_ckan = True
            resource.last_update = _today
        ckan_user.close()

        resource.save()
        return resource
