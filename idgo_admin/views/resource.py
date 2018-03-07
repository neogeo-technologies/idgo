# Copyright (c) 2017-2018 Datasud.
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
from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanNotFoundError
from idgo_admin.ckan_module import CkanSyncingError
from idgo_admin.ckan_module import CkanTimeoutError
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
import json


CKAN_URL = settings.CKAN_URL

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class ResourceManager(View):

    template = 'idgo_admin/resource.html'
    namespace = 'idgo_admin:resource'

    @ExceptionsHandler(actions={ProfileHttp404: on_profile_http404})
    def get(self, request, dataset_id=None, *args, **kwargs):

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

            mode = instance.up_file and 'up_file' \
                or instance.dl_url and 'dl_url' \
                or instance.referenced_url and 'referenced_url' \
                or None

            context.update({
                'resource_name': three_suspension_points(instance.name),
                'resource_id': instance.id,
                'resource_ckan_id': instance.ckan_id,
                'mode': mode,
                'form': Form(instance=instance)})

        return render_with_info_profile(request, self.template, context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    @transaction.atomic
    def post(self, request, dataset_id=None, *args, **kwargs):

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        id = request.POST.get('id', request.GET.get('id'))
        instance = id and get_object_or_404_extended(
            Resource, user, include={'id': id, 'dataset': dataset}) or None

        form = Form(
            request.POST, request.FILES, instance=instance, dataset=dataset)

        if not form.is_valid():
            error = dict(
                [(k, [str(m) for m in v]) for k, v in form.errors.items()])
            return JsonResponse(json.dumps({'error': error}), safe=False)

        try:
            with transaction.atomic():
                instance = form.handle_me(request, dataset, id=id)

        except CkanSyncingError as e:
            error = {'__all__': [e.__str__()]}

        except CkanTimeoutError:
            error = {'__all__': [e.__str__()]}

        except ValidationError as e:
            form.add_error(e.code, e.message)
            error = dict(
                [(k, [str(m) for m in v]) for k, v in form.errors.items()])

        else:
            dataset_href = reverse(
                self.namespace, kwargs={'dataset_id': dataset_id})

            messages.success(request, (
                'La ressource a été {0} avec succès. Souhaitez-vous '
                '<a href="{1}">ajouter une nouvelle ressource</a> ? ou bien '
                '<a href="{2}/dataset/{3}/resource/{4}" target="_blank">'
                'voir la ressource dans CKAN</a> ?').format(
                id and 'mise à jour' or 'créée', dataset_href,
                CKAN_URL, dataset.ckan_slug, instance.ckan_id))

            response = HttpResponse(status=201)  # Ugly hack

            if 'continue' in request.POST:
                href = '{0}?id={1}'.format(dataset_href, instance.id)
            else:
                href = '{0}?id={1}#resources/{2}'.format(
                    reverse('idgo_admin:dataset'), dataset_id, instance.id)

            response['Content-Location'] = href
            return response

        return JsonResponse(json.dumps({'error': error}), safe=False)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def delete(self, request, dataset_id=None, *args, **kwargs):

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
        except CkanNotFoundError as e:
            status = 500
            messages.error(request, e.__str__())
        except CkanSyncingError as e:
            status = 500
            messages.error(request, e.__str__())
        else:
            instance.delete()
            status = 200
            message = 'La ressource a été supprimée avec succès.'
            messages.success(request, message)
        finally:
            ckan_user.close()

        return HttpResponse(status=status)
