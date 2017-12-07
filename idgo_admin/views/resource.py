from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
# from django.http import HttpResponseForbidden
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanSyncingError
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.resource import ResourceForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models import Resource
from idgo_admin.shortcuts import get_object_or_404_extended
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
from idgo_admin.utils import three_suspension_points


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class ResourceManager(View):

    template = 'idgo_admin/resource.html'
    namespace = 'idgo_admin:resource'

    @ExceptionsHandler(actions={ProfileHttp404: on_profile_http404})
    def get(self, request, dataset_id, *args, **kwargs):

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        context = {'dataset_name': three_suspension_points(dataset.name),
                   'dataset_id': dataset.id,
                   'dataset_ckan_slug': dataset.ckan_slug,
                   'resource_name': 'Nouvelle ressource',
                   'resource_ckan_id': None,
                   'form': Form()}

        id = request.GET.get('id')
        if id:
            instance = get_object_or_404_extended(
                Resource, user, include={'id': id, 'dataset_id': dataset_id})

            mode = None
            if instance.up_file:
                mode = 'up_file'
            if instance.dl_url:
                mode = 'dl_url'
            if instance.referenced_url:
                mode = 'referenced_url'

            context.update({
                'resource_name': three_suspension_points(instance.name),
                'resource_ckan_id': instance.ckan_id,
                'mode': mode,
                'form': Form(instance=instance)})

        return render_with_info_profile(request, self.template, context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    @transaction.atomic
    def post(self, request, dataset_id, *args, **kwargs):

        def get_uploaded_file(form):
            return form.is_multipart() and request.FILES.get('up_file')

        def http_redirect(dataset_id, resource_id):
            return HttpResponseRedirect(
                reverse(self.namespace, kwargs={'dataset_id': dataset_id}
                        ) + '?id={0}'.format(resource_id))

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        context = {'dataset_name': three_suspension_points(dataset.name),
                   'dataset_id': dataset.id,
                   'dataset_ckan_slug': dataset.ckan_slug,
                   'mode': None,
                   'resource_name': 'Nouvelle ressource',
                   'resource_ckan_id': None}

        id = request.POST.get('id', request.GET.get('id'))
        if id:
            instance = get_object_or_404_extended(
                Resource, user, include={'id': id, 'dataset': dataset})

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
                return render_with_info_profile(request, self.template, context)

            try:
                with transaction.atomic():
                    form.handle_me(
                        request, dataset, id=id, uploaded_file=get_uploaded_file(form))
            except ValidationError as e:
                form.add_error(e.code, e.message)
                context.update({'form': form})
                return render_with_info_profile(request, self.template, context)

            messages.success(
                request, 'La ressource a été mise à jour avec succès.')

            return http_redirect(dataset_id, instance.id)

        form = Form(request.POST, request.FILES)
        if not form.is_valid():
            context.update({'form': form})
            return render_with_info_profile(request, self.template, context)

        try:
            with transaction.atomic():
                instance = form.handle_me(
                    request, dataset, uploaded_file=get_uploaded_file(form))
        except ValidationError as e:
            form.add_error(e.code, e.message)
            context.update({'form': form})
            return render_with_info_profile(request, self.template, context)

        messages.success(request, (
            'La ressource a été créée avec succès. Souhaitez-vous '
            '<a href="{0}">ajouter une nouvelle ressource ?</a>').format(
                reverse(self.namespace, kwargs={'dataset_id': dataset_id})))

        return http_redirect(dataset_id, instance.id)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def delete(self, request, dataset_id, *args, **kwargs):

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        id = request.POST.get('id', request.GET.get('id'))
        if not id:
            raise Http404
        instance = get_object_or_404_extended(
            Resource, user, include={'id': id, 'dataset': dataset})

        ckan_id = str(instance.ckan_id)

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        try:
            ckan_user.delete_resource(ckan_id)
        except CkanSyncingError as e:
            if e.name == 'NotFound':
                instance.delete()
            status = 500
            message = 'Impossible de supprimer la ressource Ckan.'
            messages.error(request, message)
        else:
            instance.delete()
            status = 200
            message = 'La ressource a été supprimée avec succès.'
            messages.success(request, message)
        finally:
            ckan_user.close()

        return HttpResponse(status=status)
