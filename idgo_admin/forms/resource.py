from django.conf import settings
from django.core.files import File
from django import forms
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.models import Resource
from idgo_admin.utils import download
from uuid import uuid4


class CustomClearableFileInput(forms.ClearableFileInput):
    template_name = 'idgo_admin/clearable_file_input.html'


class ResourceForm(forms.ModelForm):

    name = forms.CharField(
        label='Titre',
        widget=forms.TextInput(
            attrs={'placeholder': 'Titre'}))

    description = forms.CharField(
        label='Description',
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

    class Meta(object):
        model = Resource
        fields = ('name',
                  'description',
                  'lang',
                  'data_format',
                  'restricted_level',
                  'dl_url',
                  'referenced_url',
                  'up_file')

    def handle_me(self, request, dataset, id=None, uploaded_file=None):
        user = request.user
        data = self.cleaned_data

        params = {'name': data['name'],
                  'description': data['description'],
                  'dl_url': data['dl_url'],
                  'referenced_url': data['referenced_url'],
                  'lang': data['lang'],
                  'data_format': data['data_format'],
                  'restricted_level': data['restricted_level'],
                  'up_file': data['up_file'],
                  'dataset': dataset}

        restricted_level = data['access']

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
            params['restricted'] = {
                'allowed_users': '',  # TODO(@m431m)
                'level': 'registered'}

        if restricted_level == '4':  # Any organization
            params['restricted'] = {
                'allowed_users': '',  # TODO(@m431m)
                'level': 'any_organization'}

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
            params['resource_type'] = filename

        if uploaded_file:
            params['upload'] = uploaded_file
            params['size'] = uploaded_file.size
            params['mimetype'] = uploaded_file.content_type
            params['resource_type'] = uploaded_file.name

        try:
            ckan_user.publish_resource(str(dataset.ckan_id), **params)
        except Exception as e:
            # resource.delete()  # TODO(@m431m)
            raise Exception(e)
        else:
            resource.last_update = timezone.now()
            resource.save()
        finally:
            ckan_user.close()

        return resource
