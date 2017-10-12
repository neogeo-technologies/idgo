from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import Http404
# from django.http import HttpResponseForbidden
from django.http import HttpResponse
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
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.utils import three_suspension_points
import json


def get_all_users():
    # TODO Récupérer depuis Django et non CKAN (ou bien comparer)
    # return [m[1] for m in ckan.get_all_users()]

    return [p.user.username for p in Profile.objects.filter(is_active=True)]


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

        if not dataset.is_profile_allowed(get_object_or_404(Profile, user=user)):
            # return HttpResponseForbidden("L'accès à ce jeu de données est réservé")
            raise Http404

        all_users = get_all_users()
        all_organizations = get_all_organizations()

        context = {'users': json.dumps(all_users),
                   'organizations': json.dumps(all_organizations),
                   'first_name': user.first_name,
                   'last_name': user.last_name,
                   'dataset_name': three_suspension_points(dataset.name),
                   'dataset_id': dataset.id,
                   'resource_name': 'Nouveau',
                   'form': Form()}

        id = request.GET.get('id')
        if id:
            instance = \
                get_object_or_404(Resource, id=id, dataset_id=dataset_id)

            mode = None
            if instance.up_file:
                mode = 'up_file'
            if instance.dl_url:
                mode = 'dl_url'
            if instance.referenced_url:
                mode = 'referenced_url'

            context.update({
                'resource_name': three_suspension_points(instance.name),
                'mode': mode,
                'form': Form(instance=instance)})

        return render(request, self.template, context)

    @ExceptionsHandler(ignore=[Http404])
    @transaction.atomic
    def post(self, request, dataset_id):

        def get_uploaded_file(form):
            return form.is_multipart() and request.FILES.get('up_file')

        def http_redirect(dataset_id, resource_id):
            return HttpResponseRedirect(
                reverse(self.namespace, kwargs={'dataset_id': dataset_id}
                        ) + '?id={0}'.format(resource_id))

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id, editor=user)

        if not dataset.is_profile_allowed(get_object_or_404(Profile, user=user)):
            # return HttpResponseForbidden("L'accès à cette ressource est réservé")
            raise Http404

        all_users = get_all_users()
        all_organizations = get_all_organizations()

        context = {'users': json.dumps(all_users),
                   'organizations': json.dumps(all_organizations),
                   'first_name': user.first_name,
                   'last_name': user.last_name,
                   'dataset_name': three_suspension_points(dataset.name),
                   'dataset_id': dataset.id,
                   'mode': None,
                   'resource_name': 'Nouveau'}

        id = request.POST.get('id', request.GET.get('id'))
        if id:
            instance = \
                get_object_or_404(Resource, id=id, dataset_id=dataset_id)

            mode = None
            if instance.up_file:
                mode = 'up_file'
            if instance.dl_url:
                mode = 'dl_url'
            if instance.referenced_url:
                mode = 'referenced_url'

            context.update({'mode': mode})

            form = Form(request.POST, request.FILES, instance=instance)
            if not form.is_valid():
                context.update({
                    'resource_name': three_suspension_points(instance.name),
                    'form': form})
                return render(request, self.template, context)

            try:
                with transaction.atomic():
                    form.handle_me(
                        request, dataset, id=id, uploaded_file=get_uploaded_file(form))
            except ValidationError as e:
                form.add_error(e.code, e.message)
                context.update({'form': form})
                return render(request, self.template, context)

            messages.success(
                request, 'La ressource a été mise à jour avec succès.')

            return http_redirect(dataset_id, instance.id)

        form = Form(request.POST, request.FILES)
        if not form.is_valid():
            context.update({'form': form})
            return render(request, self.template, context)

        try:
            with transaction.atomic():
                instance = form.handle_me(
                    request, dataset, uploaded_file=get_uploaded_file(form))
        except ValidationError as e:
            form.add_error(e.code, e.message)
            context.update({'form': form})
            return render(request, self.template, context)

        messages.success(request, (
            'La ressource a été créée avec succès. Souhaitez-vous '
            '<a href="{0}">ajouter une nouvelle ressource ?</a>').format(
                reverse(self.namespace, kwargs={'dataset_id': dataset_id})))

        return http_redirect(dataset_id, instance.id)

    @ExceptionsHandler(ignore=[Http404])
    def delete(self, request, dataset_id):

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id)
        if not dataset.is_profile_allowed(get_object_or_404(Profile, user=user)):
            # return HttpResponseForbidden("L'accès à cette ressource est réservé")
            raise Http404

        id = request.POST.get('id', request.GET.get('id'))
        if not id:
            raise Http404
        instance = get_object_or_404(Resource, id=id, dataset=dataset)
        ckan_id = str(instance.ckan_id)

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        try:
            ckan_user.delete_resource(ckan_id)
        except CkanSyncingError as e:
            if e.name == 'NotFound':
                instance.delete()
            status = 500
            message = 'Impossible de supprimer la ressource Ckan.'
            message.error(request, message)
        else:
            instance.delete()
            status = 200
            message = 'La ressource a été supprimée avec succès.'
            message.info(request, message)
        finally:
            ckan_user.close()

        # return render(request, 'idgo_admin/response.html',
        #               context={'message': message}, status=status)

        return HttpResponse(status=status)
