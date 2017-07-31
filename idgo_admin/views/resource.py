from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.forms.resource import ResourceForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models import Mail
from idgo_admin.models import Resource
import json


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


def render_on_error(request):  # TODO(cbenhabib)
    # dform = DatasetForm(include={'user': request.user})
    # return render(request, 'idgo_admin/dataset.html', {'dform': dform})
    pass


def render_an_critical_error(request):
    message = ("Une erreur critique s'est produite "
               'lors de la suppression de la ressource.')

    return JsonResponse(data={'message': message}, status=400)


@method_decorator(decorators, name='dispatch')
class ResourceManager(View):

    all_users = [m[1] for m in ckan.get_all_users()]
    all_organizations = ckan.get_all_organizations()

    def mode(self, instance):
        if instance.up_file:
            return 'up_file'
        if instance.dl_url:
            return 'dl_url'
        if instance.referenced_url:
            return 'referenced_url'

    def get(self, request, dataset_id):
        user = request.user
        id = request.GET.get('id') or None
        dataset = get_object_or_404(Dataset, id=dataset_id)

        if id:
            instance = get_object_or_404(Resource, id=id, dataset_id=dataset_id)
            return render(request, 'idgo_admin/resource.html', context={
                'users': json.dumps(self.all_users),
                'organizations': json.dumps(self.all_organizations),
                'first_name': user.first_name,
                'last_name': user.last_name,
                'dataset_name': dataset.name,
                'dataset_id': dataset.id,
                'resource_name': instance.name,
                'mode': self.mode(instance),
                'form': Form(instance=instance, include={'user': user})})

        return render(request, 'idgo_admin/resource.html', context={
            'users': json.dumps(self.all_users),
            'organizations': json.dumps(self.all_organizations),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'dataset_name': dataset.name,  # TODO
            'dataset_id': dataset.id,  # TODO
            'resource_name': 'Nouveau',
            'form': Form(include={'user': user})})

    def post(self, request, dataset_id):

        def get_uploaded_file(form):
            return (form.is_multipart() and 'up_file' in request.FILES
                    ) and request.FILES['up_file'] or None

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id)
        success = False
        text = "Erreur lors de l'opération de modification de la base Resource"
        id = request.POST.get('id', request.GET.get('id')) or None
        if id:
            instance = get_object_or_404(Resource, id=id, dataset_id=dataset_id)
            resource_name = instance.name
            mode = self.mode(instance)

            form = Form(request.POST, request.FILES,
                        instance=instance, include={'user': user})
            if form.is_valid() and user.is_authenticated:
                try:
                    form.handle_me(request, dataset, id=id,
                                   uploaded_file=get_uploaded_file(form))
                except Exception as e:
                    success = False
                    text = ("L'erreur suivante est survenue : "
                            '<strong>{0}</strong>.').format(str(e))
                else:
                    success = True
                    text = 'La ressource a été mise à jour avec succès.'

        else:
            resource_name = 'Nouveau'
            mode = None
            form = Form(request.POST, request.FILES, include={'user': user})
            
            if form.is_valid() and user.is_authenticated:
                try:
                    instance = form.handle_me(
                        request, dataset, uploaded_file=get_uploaded_file(form))
                except Exception as e:
                    print('Exception:', e)
                    success = False
                    text = ("L'erreur suivante est survenue : "
                            '<strong>{0}</strong>.').format(str(e))
                else:
                    success = True
                    text = 'La ressource a été créée avec succès.'

                    form = Form(instance=instance, include={'user': user})
                    resource_name = instance.name

        return render(request, 'idgo_admin/resource.html', context={
            'users': json.dumps(self.all_users),
            'organizations': json.dumps(self.all_organizations),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'dataset_name': dataset.name,  # TODO
            'dataset_id': dataset.id,  # TODO
            'resource_name': resource_name,
            'form': form,
            'mode': mode,
            'message': {
                'status': success and 'success' or 'failure',
                'text': text}})

    def delete(self, request, dataset_id):

        id = request.POST.get('id', request.GET.get('id')) or None
        if not id:
            return render_an_critical_error(request)

        resource = get_object_or_404(Resource, id=id, dataset_id=dataset_id)

        ckan_user = ckan_me(ckan.get_user(request.user.username)['apikey'])
        try:
            ckan_user.delete_resource(str(resource.ckan_id))
        except Exception:
            message = ('La ressource <strong>{0}</strong> '
                       'ne peut pas être supprimé.').format(resource.name)
            status = 400
        else:
            resource.delete()
            message = ('Le jeu de données <strong>{0}</strong> '
                       'a été supprimé avec succès.').format(resource.name)
            status = 200
        finally:
            ckan_user.close()

        try:
            Mail.conf_deleting_dataset_res_by_user(request.user,
                                                   resource=resource)
        except Exception as e:
            print('Error', e)
            pass

        context = {
            'message': message,
            'action': '{0}{1}'.format(reverse('idgo_admin:dataset'),
                                      '?id={0}#resources'.format(dataset_id))}
        return render(
            request, 'idgo_admin/response.htm', context=context, status=status)
