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
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
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

    def get(self, request, dataset_id):

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id)

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
                data_field = instance.up_file
            if instance.dl_url:
                data_field = instance.dl_url
            if instance.referenced_url:
                data_field = instance.referenced_url

            context.update({'resource_name': instance.name,
                            'mode': data_field.__dict__.get('field').name,
                            'form': Form(instance=instance)})

        return render(request, self.template, context)

    def post(self, request, dataset_id):

        def get_uploaded_file(form):
            return form.is_multipart() and request.FILES.get('up_file')

        def http_redirect(resource_id):
            return HttpResponseRedirect(
                reverse(self.namespace, kwargs={'dataset_id': dataset_id}
                        ) + '?id={0}'.format(resource_id))

        dataset = get_object_or_404(Dataset, id=dataset_id)

        id = request.POST.get('id', request.GET.get('id'))
        if id:
            instance = get_object_or_404(Resource, id=id, dataset_id=dataset_id)
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
                messages.success(request, 'La ressource a été mise à jour avec succès.')
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
            messages.success(request, 'La ressource a été créée avec succès.')
            return http_redirect(instance.id)

    def delete(self, request, dataset_id):

        user = request.user
        id = request.POST.get('id', request.GET.get('id'))
        if not id:
            return Http404()
        instance = get_object_or_404(Resource, id=id, dataset_id=dataset_id)

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        try:
            ckan_user.delete_resource(str(instance.ckan_id))
        except Exception:
            # TODO Gérer les erreurs correctement
            message = "La ressource ne peut pas être supprimée. Veuillez contacter l'administrateur du site."
            status = 400
        else:
            instance.delete()
            message = 'La ressource a été supprimée avec succès.'
            status = 200
        ckan_user.close()

        try:
            Mail.conf_deleting_dataset_res_by_user(user, resource=instance)
        except Exception:
            # TODO Que faire en cas d'erreur à ce niveau ?
            pass

        # TODO Revoir le 'render' complètement
        context = {
            'message': message,
            'method': 'get',
            'action': reverse('idgo_admin:dataset') + '?id={0}'.format(dataset_id)}

        return render(
            request, 'idgo_admin/response.html', context=context, status=status)
