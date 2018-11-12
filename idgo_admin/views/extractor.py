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
from django.http import Http404
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.models import AsyncExtractorTask
from idgo_admin.models import BaseMaps
from idgo_admin.models import Commune
from idgo_admin.models import Dataset
from idgo_admin.models import ExtractorSupportedFormat
from idgo_admin.models import Layer
from idgo_admin.models import Organisation
from idgo_admin.models import Resource
from idgo_admin.models import SupportedCrs
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
import itertools
import json
from math import ceil
import re
import requests
from uuid import UUID


EXTRACTOR_URL = settings.EXTRACTOR_URL
try:
    BOUNDS = settings.EXTRACTOR_BOUNDS
except AttributeError:
    BOUNDS = [[40, -14], [55, 28]]

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def extractor_task(request, *args, **kwargs):
    user, profile = user_and_profile(request)
    instance = get_object_or_404(AsyncExtractorTask, uuid=request.GET.get('id'))
    query = instance.details['query']

    extract_params = query['data_extractions'][-1]

    auth_name, auth_code = extract_params.get('dst_srs').split(':')
    crs = SupportedCrs.objects.get(auth_name=auth_name, auth_code=auth_code)
    format = ExtractorSupportedFormat.objects.get(details=extract_params.get('dst_format'))

    if instance.model == 'Dataset':
        layers = list(itertools.chain.from_iterable([layer for layer in [
            resource.get_layers() for resource
            in instance.target_object.get_resources()]]))
    elif instance.model == 'Resource':
        layers = [layer for layer in instance.target_object.get_layers()]
    elif instance.model == 'Layer':
        layers = [instance.target_object]

    data = {
        'crs': crs.description,
        'footprint': extract_params.get('footprint'),
        'format': format.description,
        'layer': [layer.name for layer in layers],
        'start': instance.start_datetime,
        'stop': instance.stop_datetime,
        'target': '{} : {}'.format(
            instance.target_object._meta.verbose_name,
            instance.target_object.__str__()),
        'target_value': instance.foreign_value,
        'target_field': instance.foreign_field,
        'target_model': instance.model.lower(),
        'submission': instance.details.get('submission_datetime'),
        'user': instance.user.get_full_name()}

    return JsonResponse(data=data)


@method_decorator(decorators, name='dispatch')
class ExtractorDashboard(View):

    def get(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404

        order_by = request.GET.get('sortby', '-submission')

        if order_by:
            if order_by.endswith('submission'):
                order_by = '{}submission_datetime'.format(
                    order_by.startswith('-') and '-' or '')
            elif order_by.endswith('status'):
                order_by = '{}success'.format(
                    order_by.startswith('-') and '-' or '')
            else:
                order_by = None

        # Pagination
        page_number = int(request.GET.get('page', 1))
        items_per_page = int(request.GET.get('count', 10))

        x = items_per_page * page_number - items_per_page
        y = x + items_per_page

        if profile.is_admin and profile.crige_membership:
            tasks = AsyncExtractorTask.objects.all()
        else:
            tasks = AsyncExtractorTask.objects.filter(user=user)

        tasks = order_by and tasks.order_by(order_by) or tasks
        number_of_pages = ceil(len(tasks) / items_per_page)

        context = {
            'basemaps': BaseMaps.objects.all(),
            'pagination': {
                'current': page_number,
                'total': number_of_pages},
            'supported_crs': SupportedCrs.objects.all(),
            'supported_format': ExtractorSupportedFormat.objects.all(),
            'tasks': tasks[x:y]}

        print(context)

        return render_with_info_profile(
            request, 'idgo_admin/extractor/dashboard.html', context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404

        if 'revoke' in request.POST:
            task = get_object_or_404(
                AsyncExtractorTask, uuid=UUID(request.POST.get('task')))
            if task.success is True:
                messages.error(request, (
                    'La demande de révocation ne peut aboutir car '
                    "l'extraction a déjà été executée avec succès."))
            else:
                if 'abort' in list(task.details.get('possible_requests').keys()):
                    abort = task.details['possible_requests']['abort']
                    r = requests.request(abort['verb'], abort['url'], json=abort['payload'])

                    if r.status_code in (201, 202):
                        messages.success(
                            request, 'La demande de révocation est envoyée avec succès.')
                    else:
                        messages.error(request, r.json().get('detail'))

        return HttpResponseRedirect(reverse('idgo_admin:extractor_dashboard'))


@method_decorator(decorators, name='dispatch')
class Extractor(View):

    template = 'idgo_admin/extractor/extractor.html'
    namespace = 'idgo_admin:extractor'

    def get_instance(self, ModelObj, value):

        m = re.match('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', value)
        if m:
            key = 'ckan_id'
            value = UUID(m.group(0))
        if isinstance(value, str):
            if ModelObj.__name__ == 'Layer':
                key = 'name'
            else:
                key = 'ckan_slug'
        if isinstance(value, int):
            key = 'id'
        try:
            return ModelObj.objects.get(**{key: value})
        except (ModelObj.DoesNotExist, ValueError):
            raise Http404

    def get_context(self, user, organisation=None, dataset=None,
                    resource=None, layer=None, task=None):

        context = {
            'organisations': None,
            'organisation': None,
            'datasets': None,
            'dataset': None,
            'resources': None,
            'resource': None,
            'layer': None,
            'task': None,
            'communes': Commune.objects.all().transform(srid=4326),
            'supported_crs': SupportedCrs.objects.all(),
            'supported_format': ExtractorSupportedFormat.objects.all()}

        if task:
            try:
                task = AsyncExtractorTask.objects.get(uuid=UUID(task))
            except AsyncExtractorTask.DoesNotExist:
                pass
            else:
                if task.model == 'Layer':
                    context['task'] = task
                    context['layer'] = task.target_object
                    context['resource'] = task.target_object.resource
                    context['dataset'] = task.target_object.resource.dataset
                    context['organisation'] = task.target_object.resource.organisation
                elif task.model == 'Resource':
                    context['task'] = task
                    context['layer'] = task.target_object.get_layers()[-1]  # Dans la version actuelle relation 1-1
                    context['resource'] = task.target_object
                    context['dataset'] = task.target_object.dataset
                    context['organisation'] = task.target_object.organisation
                elif task.model == 'Dataset':
                    context['dataset'] = task.target_object
                    context['organisation'] = task.target_object.organisation

                extract_params = task.details['query']['data_extractions'][-1]
                context['footprint'] = extract_params.get('footprint')
                context['crs'] = extract_params.get('dst_srs')
                context['format'] = extract_params.get('dst_format')

        # Les paramètres Layer Resource Dataset et Organisation écrase Task
        if layer:
            layer = self.get_instance(Layer, layer)
            context['layer'] = layer
            context['resource'] = layer.resource
            context['dataset'] = layer.resource.dataset
            context['organisation'] = layer.resource.dataset.organisation
        elif resource:
            resource = self.get_instance(Resource, resource)
            context['resource'] = resource
            context['dataset'] = resource.dataset
            context['organisation'] = resource.dataset.organisation
        elif dataset:
            dataset = self.get_instance(Dataset, dataset)
            context['dataset'] = dataset
            context['organisation'] = dataset.organisation
        elif organisation:
            organisation = self.get_instance(Organisation, organisation)
            context['organisation'] = organisation

        context['organisations'] = Organisation.objects.filter(
            dataset__resource__in=Resource.objects.filter(extractable=True).exclude(layer=None)
            ).distinct()

        context['datasets'] = Dataset.objects.filter(
            organisation=context['organisation'],
            resource__in=Resource.objects.filter(extractable=True).exclude(layer=None)
            ).distinct()

        context['resources'] = Resource.objects.filter(
            dataset=context['dataset'],
            extractable=True
            ).exclude(layer=None)

        layers = Layer.objects.filter(resource=context['resource'])

        if not context['layer'] and layers:
            context['layer'] = layers[0]

        return context

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404

        context = self.get_context(
            user,
            organisation=request.GET.get('organisation'),
            dataset=request.GET.get('dataset'),
            resource=request.GET.get('resource'),
            layer=request.GET.get('layer'),
            task=request.GET.get('task'))

        context['basemaps'] = BaseMaps.objects.all()

        bbox = request.GET.get('bbox')
        if bbox:
            minx, miny, maxx, maxy = bbox.split(',')
            context['bounds'] = [[miny, minx], [maxy, maxx]]
        else:
            context['bounds'] = BOUNDS

        context['crs'] = request.GET.get('crs', context.get('crs'))
        footprint = request.GET.get('footprint')
        context['footprint'] = footprint and json.loads(footprint) or context.get('footprint')
        context['format'] = request.GET.get('format', context.get('format'))

        return render_with_info_profile(request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404

        try:
            context = self.get_context(
                user,
                organisation=request.GET.get('organisation'),
                dataset=request.GET.get('dataset'),
                resource=request.GET.get('resource'),
                layer=request.GET.get('layer'),
                task=request.GET.get('task'))
        except Exception:
            raise Http404

        footprint = json.loads(request.POST.get('footprint')).get('geometry')

        layer_name = request.POST.get('layer')
        resource_name = request.POST.get('resource')
        dataset_name = request.POST.get('dataset')

        dst_crs = request.POST.get('crs')
        format = request.POST.get('format')
        if format:
            dst_format = ExtractorSupportedFormat.objects.get(name=format).details

        source = 'PG:host=postgis-master user=datagis dbname=datagis'
        footprint_crs = 'EPSG:4326'

        extract_params = {
            'source': source,
            'dst_format': dst_format,
            'dst_srs': dst_crs or 'EPSG:2154',
            'footprint': footprint,
            'footprint_srs': footprint_crs}

        data_extractions = []
        additional_files = []

        if layer_name:
            model = 'Layer'
            foreign_field = 'name'
            foreign_value = layer_name

            layer = get_object_or_404(Layer, **{foreign_field: foreign_value})
            data_extractions.append({**extract_params, **{'layer': layer.name}})

        elif resource_name:
            model = 'Resource'
            foreign_field = 'name'
            foreign_value = resource_name

            for layer in get_object_or_404(
                    Resource, **{foreign_field: foreign_value}).get_layers():
                data_extractions.append(
                    {**extract_params, **{'layer': layer.name}})

        elif dataset_name:
            model = 'Dataset'
            foreign_field = 'ckan_slug'
            foreign_value = dataset_name

            for resource in get_object_or_404(
                    Dataset, **{foreign_field: foreign_value}).get_resources():
                for layer in resource.get_layers():
                    data_extractions.append(
                        {**extract_params, **{'layer': layer.name}})

                if resource.data_type == 'annexe':
                    additional_files.append({
                        'file_name': resource.filename,
                        'dir_name': 'Documentation associée',
                        'file_location': ckan.get_resource(
                            str(resource.ckan_id)).get('url')})

        data = {
            'user_id': user.username,
            'user_email_address': user.email,
            'user_name': user.last_name,
            'user_first_name': user.first_name,
            'user_company': user.profile.organisation.name,
            'user_address': user.profile.organisation.full_address,
            'data_extractions': data_extractions,
            'additional_files': additional_files}

        r = requests.post(EXTRACTOR_URL, json=data)

        if r.status_code == 201:
            details = r.json()

            AsyncExtractorTask.objects.create(
                details=details,
                foreign_field=foreign_field,
                foreign_value=foreign_value,
                model=model,
                submission_datetime=details.get('submission_datetime'),
                uuid=UUID(details.get('task_id')),
                user=user)

            messages.success(request, (
                "L'extraction a été ajoutée à la liste de tâche. "
                "Vous allez recevoir un e-mail une fois l'extraction réalisée."))

            return HttpResponseRedirect(reverse('idgo_admin:extractor_dashboard'))
        else:
            if r.status_code == 400:
                msg = r.json().get('detail')
            else:
                msg = "L'extracteur n'est pas disponible pour le moment."
            messages.error(request, msg)
            return render_with_info_profile(request, self.template, context=context)
