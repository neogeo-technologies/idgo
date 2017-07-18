from django.conf import settings
from django import forms
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.models import Resource
import os
from urllib.request import urlretrieve


class ResourceForm(forms.ModelForm):
    # Dans le formulaire de saisie, ne montrer que si AccessLevel = 2
    # geo_restriction, created_on, last_update dataset, type, fichier

    class Meta(object):
        model = Resource
        fields = ('name',
                  'description',
                  'lang',
                  'data_format',
                  'access',
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
                  'access': data['access'],
                  'up_file': data['up_file'],
                  'dataset': dataset}

        if id:  # Mise à jour d'un ressource
            resource = Resource.objects.get(pk=id)
            for key, value in params.items():
                setattr(resource, key, value)
        else:  # Création d'une nouvelle ressource
            resource = Resource.objects.create(**params)

        dataset = resource.dataset

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])

        params = {'name': resource.name,
                  'description': resource.description,
                  'format': resource.data_format,
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
            ckan_user.publish_resource(dataset.ckan_id, **params)
        except Exception:
            resource.delete()

        ckan_user.close()
        resource.save()
