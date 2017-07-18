from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.forms.resource import ResourceForm
from idgo_admin.models import Dataset
from idgo_admin.models import Resource


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

    def get(self, request, dataset_id):
        user = request.user
        id = request.GET.get('id') or None
        dataset = get_object_or_404(Dataset, id=dataset_id)
        if id:
            resource = get_object_or_404(Resource, id=id,
                                         dataset_id=dataset_id)
            return render(request, 'idgo_admin/resource.html',
                          {'first_name': user.first_name,
                           'last_name': user.last_name,
                           'dataset_name': dataset.name,
                           'dataset_id': dataset.id,
                           'resource_name': resource.name,
                           'rform': ResourceForm(instance=resource)})

        return render(request, 'idgo_admin/resource.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'dataset_name': dataset.name,  # TODO
                       'dataset_id': dataset.id,  # TODO
                       'resource_name': 'Nouveau',
                       'rform': ResourceForm()})

    def post(self, request, dataset_id):
        user = request.user
        id = request.POST.get('id', request.GET.get('id')) or None
        dataset = get_object_or_404(Dataset, id=dataset_id)
        if id:
            resource = get_object_or_404(
                Resource, id=id, dataset_id=dataset_id)
            rform = ResourceForm(
                request.POST, request.FILES, instance=resource)

            uploaded_file = None
            if rform.is_multipart():
                uploaded_file = 'up_file' in request.FILES and request.FILES['up_file'] or None

            if not rform.is_valid() or not request.user.is_authenticated:
                return render(request, 'idgo_admin/resource.html',
                              {'first_name': user.first_name,
                               'last_name': user.last_name,
                               'dataset_name': dataset.name,
                               'dataset_id': dataset.id,
                               'resource_name': resource.name,
                               'rform': Resource(instance=resource)})

            try:
                rform.handle_me(
                    request, dataset, id=id, uploaded_file=uploaded_file)
            except Exception as e:
                message = ("L'erreur suivante est survenue : "
                           '<strong>{0}</strong>.').format(str(e))
            else:
                message = 'La ressource a été mise à jour avec succès.'

            return render(request, 'idgo_admin/response.html',
                          {'message': message}, status=200)
        else:
            rform = ResourceForm(data=request.POST)
            if rform.is_valid() and request.user.is_authenticated:
                try:
                    rform.handle_me(request, dataset)
                except Exception as e:
                    message = ("L'erreur suivante est survenue : "
                               '<strong>{0}</strong>.').format(str(e))
                else:
                    message = 'La ressource a été créée avec succès.'

                return render(request, 'idgo_admin/response.html',
                              {'message': message}, status=200)

        return render(request, 'idgo_admin/resource.html', {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'dataset_name': dataset.name,  # TODO
            'dataset_id': dataset.id,  # TODO
            'resource_name': 'Nouveau',
            'rform': rform})

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

        ckan_user.close()

        return render(request, 'idgo_admin/response.htm',
                      {'message': message}, status=status)
