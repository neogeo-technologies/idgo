from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanSyncingError
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.forms.resource import ResourceForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models import Mail
from idgo_admin.models import Resource
import json


def get_all_users():
    # TODO Récupérer depuis Django et non CKAN (ou bien comparer)
    return [m[1] for m in ckan.get_all_users()]


def get_all_organizations():
    # TODO Récupérer depuis Django et non CKAN (ou bien comparer)
    return ckan.get_all_organizations()


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class ResourceManager(View):

    template = 'idgo_admin/resource.html'
    namespace = 'idgo_admin:resource'

    @ExceptionsHandler(ignore=[Http404])
    def get(self, request, dataset_id):

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id, editor=user)

        all_users = get_all_users()
        all_organizations = get_all_organizations()

        context = {'users': json.dumps(all_users),
                   'organizations': json.dumps(all_organizations),
                   'first_name': user.first_name,
                   'last_name': user.last_name,
                   'dataset_name': dataset.name,
                   'dataset_id': dataset.id,
                   'resource_name': 'Nouveau',
                   'form': Form()}

        id = request.GET.get('id')
        if id:
            instance = \
                get_object_or_404(Resource, id=id, dataset_id=dataset_id)

            # TODO Les trois champs sont exclusifs et il faudrait s'en assurer
            if instance.up_file:
                mode = 'up_file'
            if instance.dl_url:
                mode = 'dl_url'
            if instance.referenced_url:
                mode = 'referenced_url'

            context.update({'resource_name': instance.name,
                            'mode': mode,
                            'form': Form(instance=instance)})

        return render(request, self.template, context)

    @ExceptionsHandler(ignore=[Http404])
    def post(self, request, dataset_id):

        def get_uploaded_file(form):
            return form.is_multipart() and request.FILES.get('up_file')

        def http_redirect(resource_id):
            return HttpResponseRedirect(
                reverse(self.namespace, kwargs={'dataset_id': dataset_id}
                        ) + '?id={0}'.format(resource_id))

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id, editor=user)

        id = request.POST.get('id', request.GET.get('id'))
        if id:
            instance = \
                get_object_or_404(Resource, id=id, dataset_id=dataset_id)

            form = Form(request.POST, request.FILES, instance=instance)
            if not form.is_valid():
                return render(request, self.template, {'form': form})
            # else
            try:
                form.handle_me(
                    request, dataset, id=id,
                    uploaded_file=get_uploaded_file(form))
            except Exception:
                messages.error(request, 'Une erreur est survenue.')
            else:
                messages.success(
                    request, 'La ressource a été mise à jour avec succès.')
            finally:
                return http_redirect(instance.id)

        form = Form(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template, {'form': form})
        # else
        try:
            instance = form.handle_me(
                request, dataset, uploaded_file=get_uploaded_file(form))
        except Exception:
            messages.error(request, 'Une erreur est survenue.')
            return render(request, self.template, {'form': form})
        else:
            messages.success(
                request, 'La ressource a été créée avec succès.')
            return http_redirect(instance.id)

    @ExceptionsHandler(ignore=[Http404])
    def delete(self, request, dataset_id):

        user = request.user
        id = request.POST.get('id', request.GET.get('id'))
        if not id:
            return Http404()
        instance = get_object_or_404(Resource, id=id, dataset_id=dataset_id)
        ckan_id = str(instance.ckan_id)

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        try:
            ckan_user.delete_resource(ckan_id)
        except CkanSyncingError as e:
            if e.name == 'NotFound':
                instance.delete()
            status = 500
            message = 'Impossible de supprimer la ressource Ckan.'
        else:
            instance.delete()
            status = 200
            message = 'La ressource a été supprimée avec succès.'
        finally:
            ckan_user.close()

        return render(
            request, 'idgo_admin/response.html',
            context={'message': message}, status=status)
