from django.conf import settings
from django.core.files import File
from django import forms
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.utils import download
import json
from pathlib import Path
# from taggit.forms import TagField
# from taggit.forms import TagWidget
from uuid import uuid4


def get_all_users_for_organizations(list_id):
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


class CustomClearableFileInput(forms.ClearableFileInput):
    template_name = 'idgo_admin/clearable_file_input.html'


class ResourceForm(forms.ModelForm):

    name = forms.CharField(
        label='Titre',
        widget=forms.TextInput(
            attrs={'placeholder': 'Titre'}))

    description = forms.CharField(
        label='Description',
        required=False,
        widget=forms.Textarea(
            attrs={'placeholder': 'Vous pouvez utiliser le langage Markdown ici'}))

    data_format = forms.CharField(
        label='Format',
        widget=forms.TextInput(
            attrs={'placeholder': 'CSV, XML, JSON, XLS... '}))

    up_file = forms.FileField(
        label='Téléversement',
        required=False,
        widget=CustomClearableFileInput())

    # users_allowed = TagField(
    #     label="Liste d'utilisateurs",
    #     required=False,
    #     widget=TagWidget(
    #         attrs={'autocomplete': 'off',
    #                'class': 'typeahead',
    #                'placeholder': ''}))

    # organisations_allowed = TagField(
    #     label="Liste d'organisations",
    #     required=False,
    #     widget=TagWidget(
    #         attrs={'autocomplete': 'off',
    #                'class': 'typeahead',
    #                'placeholder': ''}))

    class Meta(object):
        model = Resource
        fields = ('name',
                  'description',
                  'lang',
                  'data_format',
                  'restricted_level',
                  'dl_url',
                  'referenced_url',
                  'up_file',
                  'users_allowed',
                  'organisations_allowed')

    def __init__(self, *args, **kwargs):
        include_args = kwargs.pop('include', {})
        super(ResourceForm, self).__init__(*args, **kwargs)
        user = include_args['user']

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

        if id:  # Màj
            resource = Resource.objects.get(pk=id)
            for key, value in params.items():
                setattr(resource, key, value)
        else:  # Créer
            resource = Resource.objects.create(**params)
            resource.ckan_id = uuid4()
            resource.save()

        dataset = resource.dataset
        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        params = {'name': resource.name,
                  'description': resource.description,
                  'format': resource.data_format,
                  'id': str(resource.ckan_id),
                  'lang': resource.lang,
                  'url': ''}

        if restricted_level == '2':  # Registered users
            resource.users_allowed = users_allowed
            params['restricted'] = json.dumps({
                'allowed_users': ','.join([
                    u.username for u in users_allowed]),
                'level': 'registered'})

        if restricted_level == '4':  # Any organization
            resource.organisations_allowed = organizations_allowed
            params['restricted'] = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organizations(
                        data['organisations_allowed'])),
                'level': 'registered'})  # any_organization

        if resource.referenced_url:
            params['url'] = resource.referenced_url
            params['resource_type'] = \
                '{0}.{1}'.format(resource.name, resource.data_format)

        if resource.dl_url:
            filename, content_type = \
                download(resource.dl_url, settings.MEDIA_ROOT)
            downloaded_file = File(open(filename, 'rb'))
            params['upload'] = downloaded_file
            params['size'] = downloaded_file.size
            params['mimetype'] = content_type
            params['resource_type'] = Path(filename).name

        if uploaded_file:
            params['upload'] = uploaded_file
            params['size'] = uploaded_file.size
            params['mimetype'] = uploaded_file.content_type
            params['resource_type'] = uploaded_file.name

        try:
            ckan_user.publish_resource(str(dataset.ckan_id), **params)
        except Exception as e:
            print('Error', e)
            # resource.delete()  # TODO(@m431m)
            raise Exception(e)
        else:
            resource.last_update = timezone.now()
            resource.save()
        finally:
            ckan_user.close()

        return resource
