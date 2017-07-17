from django import forms
from idgo_admin.models import Resource
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me


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

    def handle_me(self, request, dataset, id=None):
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

        print(data)

        params = {
            # 'url'
            # 'revision_id'
            'name': resource.name,
            'description': resource.description,
            'format': resource.data_format,
            'resource_type': '',
            'created': str(resource.created_on.date()) if resource.created_on else '',
            'last_modified': str(resource.last_update.date()) if resource.last_update else ''}

        if resource.referenced_url:
            return
        if resource.dl_url:
            return
        if resource.up_file:
            print(resource.up_file)

        # try:
        #     ckan_resource = ckan_user.publish_resource(dataset.ckan_id, **params)
        # except Exception as err:
        #     dataset.sync_in_ckan = False
        #     dataset.delete()
        #     raise err
        # else:
        #     dataset.ckan_id = ckan_dataset['id']
        #     dataset.sync_in_ckan = True

        ckan_user.close()
        # dataset.save()
