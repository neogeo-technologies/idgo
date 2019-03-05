# Copyright (c) 2017-2019 Datasud.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.ckan_module import CkanUserHandler
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.resource import ResourceForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models.mail import send_resource_creation_mail
from idgo_admin.models.mail import send_resource_delete_mail
from idgo_admin.models.mail import send_resource_update_mail
from idgo_admin.models import Resource
from idgo_admin.shortcuts import get_object_or_404_extended
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
import json
import os


CKAN_URL = settings.CKAN_URL

FTP_DIR = settings.FTP_DIR
try:
    FTP_UPLOADS_DIR = settings.FTP_UPLOADS_DIR
except AttributeError:
    FTP_UPLOADS_DIR = 'uploads'


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def resource(request, dataset_id=None, *args, **kwargs):
    user, profile = user_and_profile(request)

    id = request.GET.get('id', request.GET.get('ckan_id'))
    if not id:
        raise Http404

    kvp = {}
    try:
        id = int(id)
    except ValueError:
        kvp['ckan_id'] = id
    else:
        kvp['id'] = id
    finally:
        resource = get_object_or_404(Resource, **kvp)

    # TODO:
    # return redirect(reverse('idgo_admin:resource_editor', kwargs={
    #     'dataset_id': resource.dataset.id, 'resource_id': resource.id}))
    return redirect(
        '{}?id={}'.format(
            reverse(
                'idgo_admin:resource', kwargs={'dataset_id': resource.dataset.id}),
            resource.id))


@method_decorator(decorators, name='dispatch')
class ResourceManager(View):

    template = 'idgo_admin/dataset/resource/resource.html'
    namespace = 'idgo_admin:resource'

    def get_context(self, form, profile, dataset, resource):

        if resource:
            mode = (
                resource.up_file and 'up_file' or
                resource.dl_url and 'dl_url' or
                resource.referenced_url and 'referenced_url' or
                resource.ftp_file and 'ftp_file'
                ) or None
        elif form:
            mode = (
                form.files.get('up_file') and 'up_file' or
                form.data.get('dl_url') and 'dl_url' or
                form.data.get('referenced_url') and 'referenced_url' or
                form.data.get('ftp_file') and 'ftp_file'
                ) or None

        return {
            'dataset': dataset,
            'form': form,
            'mode': mode,
            'resource': resource}

    @ExceptionsHandler(actions={ProfileHttp404: on_profile_http404})
    def get(self, request, dataset_id=None, *args, **kwargs):

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        # Redirect to layer
        _resource = request.GET.get('resource')
        _layer = request.GET.get('layer')
        if _resource and _layer:
            return redirect(
                reverse('idgo_admin:layer_editor', kwargs={
                    'dataset_id': dataset.id,
                    'resource_id': _resource,
                    'layer_id': _layer}))

        id = request.GET.get('id')
        resource = id and get_object_or_404_extended(
            Resource, user, include={'id': id, 'dataset_id': dataset.id}) or None

        form = Form(instance=resource, user=user)

        context = self.get_context(form, profile, dataset, resource)

        return render_with_info_profile(request, self.template, context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    @transaction.atomic
    def post(self, request, dataset_id=None, *args, **kwargs):

        # Vider systèmatiquement les messages
        storage = messages.get_messages(request)
        storage.used = True

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        id = request.POST.get('id', request.GET.get('id'))
        resource = id and get_object_or_404_extended(
            Resource, user, include={'id': id, 'dataset': dataset}) or None

        form = Form(
            request.POST, request.FILES,
            instance=resource, dataset=dataset, user=user)

        context = self.get_context(form, profile, dataset, resource)

        ajax = 'ajax' in request.POST
        save_and_continue = 'continue' in request.POST

        if not form.is_valid():
            if ajax:
                error = dict([(k, [str(m) for m in v]) for k, v in form.errors.items()])
                msg = 'Veuillez corriger le formulaire.'
                if '__all__' in error:
                    error['__all__'].prepend(msg)
                else:
                    error['__all__'] = [msg]
                return JsonResponse(json.dumps({'error': error}), safe=False)
            return render_with_info_profile(request, self.template, context)

        data = form.cleaned_data

        kvp = {
            'crs': data['crs'],
            'data_type': data['data_type'],
            'dataset': dataset,
            'description': data['description'],
            'dl_url': data['dl_url'],
            'encoding': data.get('encoding') or None,
            'extractable': data['extractable'],
            'format_type': data['format_type'],
            'ftp_file': data['ftp_file'] and os.path.join(FTP_DIR, user.username, data['ftp_file']) or None,
            'geo_restriction': data['geo_restriction'],
            'lang': data['lang'],
            'last_update': data['last_update'],
            'name': data['name'],
            'ogc_services': data['ogc_services'],
            'referenced_url': data['referenced_url'],
            'restricted_level': data['restricted_level'],
            'sync_frequency': data['sync_frequency'],
            'synchronisation': data['synchronisation'],
            'up_file': data['up_file']}

        if data['restricted_level'] == 'only_allowed_users':
            kvp['profiles_allowed'] = data['profiles_allowed']
        if data['restricted_level'] == 'same_organization':
            kvp['organisations_allowed'] = [form._dataset.organisation]
        if data['restricted_level'] == 'any_organization':
            kvp['organisations_allowed'] = data['organisations_allowed']

        memory_up_file = request.FILES.get('up_file')
        file_extras = memory_up_file and {
            'mimetype': memory_up_file.content_type,
            'resource_type': memory_up_file.name,
            'size': memory_up_file.size} or None

        try:
            with transaction.atomic():
                save_opts = {
                    'current_user': user,
                    'file_extras': file_extras,
                    'synchronize': True}
                if id:
                    resource = Resource.objects.get(pk=id)
                    for k, v in kvp.items():
                        setattr(resource, k, v)
                    resource.save(**save_opts)
                else:
                    save_opts['current_user'] = user
                    resource = Resource.default.create(save_opts=save_opts, **kvp)

        except ValidationError as e:
            if e.code == 'crs':
                form.add_error(e.code, '')
                form.add_error('__all__', e.message)
            elif e.code == 'encoding':
                form.add_error(e.code, '')
                form.add_error('__all__', e.message)
            else:
                form.add_error(e.code, e.message)
            messages.error(request, ' '.join(e))
            error = dict(
                [(k, [str(m) for m in v]) for k, v in form.errors.items()])
        except CkanBaseError as e:
            error = {'__all__': [e.__str__()]}
            form.add_error('__all__', e.__str__())
            messages.error(request, e.__str__())
        else:
            if id:
                send_resource_update_mail(user, resource)
            else:
                send_resource_creation_mail(user, resource)

            dataset_href = reverse(
                self.namespace, kwargs={'dataset_id': dataset_id})
            messages.success(request, (
                'La ressource a été {0} avec succès. Souhaitez-vous '
                '<a href="{1}">ajouter une nouvelle ressource</a> ? ou bien '
                '<a href="{2}/dataset/{3}/resource/{4}" target="_blank">'
                'voir la ressource dans CKAN</a> ?').format(
                id and 'mise à jour' or 'créée', dataset_href,
                CKAN_URL, dataset.ckan_slug, resource.ckan_id))

            if ajax:
                response = HttpResponse(status=201)  # Ugly hack
                if save_and_continue:
                    href = '{0}?id={1}'.format(dataset_href, resource.id)
                else:
                    href = '{0}?id={1}#resources/{2}'.format(
                        reverse('idgo_admin:dataset'), dataset_id, resource.id)
                response['Content-Location'] = href
                return response
            else:
                if save_and_continue:
                    return HttpResponseRedirect(
                        '{0}?id={1}'.format(dataset_href, resource.id))

                return HttpResponseRedirect('{0}?id={1}#resources/{2}'.format(
                    reverse('idgo_admin:dataset'), dataset_id, resource.id))

        if ajax:
            form._errors = None
            return JsonResponse(json.dumps({'error': error}), safe=False)
        return render_with_info_profile(request, self.template, context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def delete(self, request, dataset_id=None, *args, **kwargs):

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        id = request.POST.get('id', request.GET.get('id'))
        if not id:
            raise Http404
        resource = get_object_or_404_extended(
            Resource, user, include={'id': id, 'dataset': dataset})

        try:
            resource.delete(current_user=user)
        except Exception as e:
            status = 500
            message = e.__str__()
            messages.error(request, message)
        else:
            status = 200
            message = 'La ressource a été supprimée avec succès.'
            messages.success(request, message)

            send_resource_delete_mail(user, resource)

        return HttpResponse(status=status)
