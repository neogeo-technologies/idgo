# from django.conf import settings
from django import forms
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.models import Resource
# import os
# from urllib.request import urlretrieve
from uuid import uuid4


class ResourceForm(forms.ModelForm):
    # Dans le formulaire de saisie, ne montrer que si AccessLevel = 2
    # geo_restriction, created_on, last_update dataset, type, fichier

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

    class CustomClearableFileInput(forms.ClearableFileInput):
        template_name = 'idgo_admin/clearable_file_input.html'

    up_file = forms.FileField(
        label='Téléversement',
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

        if id:  # Màj
            resource = Resource.objects.get(pk=id)
            for key, value in params.items():
                setattr(resource, key, value)
        else:  # Créer
            resource = Resource.objects.create(**params)
            resource.ckan_id = uuid4()

        dataset = resource.dataset
        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])

        params = {'name': resource.name,
                  'description': resource.description,
                  'format': resource.data_format,
                  'id': str(resource.ckan_id),
                  'lang': resource.lang}

        if resource.referenced_url:
            params['url'] = resource.referenced_url
            params['resource_type'] = '{0}.{1}'.format(resource.name,
                                                       resource.data_format)

        if resource.dl_url:  # TODO(@m431m)
            pass
            # filename = os.path.join(settings.MEDIA_ROOT,
            #                         resource.dl_url.split('/')[-1])
            # retreive_url = urlretrieve(resource.dl_url, filename=filename)
            # headers = retreive_url[1]
            # f = open(filename, 'wb')
            # params['upload'] = f
            # params['size'] = os.stat(f).st_size
            # params['mimetype'] = headers["Content-Type"]
            # params['resource_type'] = filename
            # ckan_user.publish_resource(dataset.ckan_id, **params)
            # f.close()

        if uploaded_file:
            params['url'] = ''  # empty character string
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
