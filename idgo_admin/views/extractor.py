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
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.models import AsyncExtractorTask
from idgo_admin.models import BaseMaps
from idgo_admin.models import Dataset
from idgo_admin.models import ExtractorSupportedFormat
from idgo_admin.models import Layer
from idgo_admin.models import Organisation
from idgo_admin.models import Resource
from idgo_admin.models import SupportedCrs
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
import json
from math import ceil
import requests
from uuid import UUID


EXTRACTOR_URL = settings.EXTRACTOR_URL


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def extractor_task(request, *args, **kwargs):
    user, profile = user_and_profile(request)
    instance = get_object_or_404(AsyncExtractorTask, uuid=request.GET.get('id'))
    query = instance.details['query']
    data = {
        'user': instance.user.get_full_name(),
        'dataset': instance.layer.resource.dataset.name,
        'resource': instance.layer.resource.name,
        'layer': instance.layer.name,
        'format': query.get('dst_format'),
        'srs': query.get('dst_srs'),
        'submission': instance.details.get('submission_datetime'),
        'start': instance.start_datetime,
        'stop': instance.stop_datetime,
        'footprint': query.get('footprint_geojson')}

    return JsonResponse(data=data)


@method_decorator([csrf_exempt], name='dispatch')
class ExtractorDashboard(View):

    template = 'idgo_admin/extractor/dashboard.html'
    namespace = 'idgo_admin:extractor_dashboard'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
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
            'tasks': tasks[x:y]}

        return render_with_info_profile(request, self.template, context=context)


@method_decorator([csrf_exempt], name='dispatch')
class Extractor(View):

    template = 'idgo_admin/extractor/extractor.html'
    namespace = 'idgo_admin:extractor'

    def get_context(self, user, organisation=None,
                    dataset=None, resource=None, task=None):

        context = {
            'organisations': None,
            'organisation': None,
            'datasets': None,
            'dataset': None,
            'resources': None,
            'resource': None,
            'layer': None,
            'task': None,
            'supported_crs': SupportedCrs.objects.all(),
            'supported_format': ExtractorSupportedFormat.objects.all()}

        if task:
            try:
                task = AsyncExtractorTask.objects.get(uuid=UUID(task))
            except AsyncExtractorTask.DoesNotExist:
                pass
            else:
                context['task'] = task
                context['layer'] = task.layer
                context['resource'] = task.layer.resource
                context['dataset'] = task.layer.resource.dataset
                context['organisation'] = task.layer.resource.dataset.organisation

        context['organisations'] = \
            Organisation.objects.filter(
                dataset__resource__in=Resource.objects.all().exclude(layer=None)
                ).distinct()

        if not context['organisation'] and organisation:
            try:
                context['organisation'] = Organisation.objects.get(id=organisation)
            except Organisation.DoesNotExist:
                return context

        context['datasets'] = \
            Dataset.objects.filter(
                organisation=context['organisation'],
                resource__extractable=True
                ).distinct()

        if not context['dataset'] and dataset:
            try:
                context['dataset'] = Dataset.objects.get(id=dataset)
            except Dataset.DoesNotExist:
                return context

        context['resources'] = \
            Resource.objects.filter(
                dataset=context['dataset'],
                extractable=True
                ).exclude(layer=None)

        if not context['resource'] and resource:
            try:
                context['resource'] = Resource.objects.get(id=resource)
            except Resource.DoesNotExist:
                return context

        layers = Layer.objects.filter(resource=context['resource'])

        if not context['layer'] and layers:
            context['layer'] = layers[0]

        return context

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404

        # try:
        context = self.get_context(
            user,
            organisation=request.GET.get('organisation'),
            dataset=request.GET.get('dataset'),
            resource=request.GET.get('resource'),
            task=request.GET.get('task'))
        # except Exception as e:
        #     print(e)
        #     raise Http404

        context['basemaps'] = BaseMaps.objects.all()

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
                task=request.GET.get('task'))
        except Exception:
            raise Http404

        footprint = json.loads(request.POST.get('footprint')).get('geometry')
        layer_name = request.POST.get('layer')
        dst_srs = request.POST.get('srs')

        source = 'PG:host=postgis-master user=datagis dbname=datagis'  # TODO
        footprint_srs = 'EPSG:4326'  # TODO
        dst_format = {'gdal_driver': 'ESRI Shapefile'}  # TODO

        data = {
            'user_id': user.username,
            'user_email_address': user.email,
            'user_name': user.last_name,
            'user_first_name': user.first_name,
            'user_company': user.profile.organisation.name,
            'user_address': user.profile.organisation.full_address,
            'source': source,
            'dst_format': dst_format,
            'dst_srs': dst_srs or 'EPSG:2154',
            'footprint': footprint,
            'footprint_srs': footprint_srs,
            'layer': layer_name}

        r = requests.post(EXTRACTOR_URL, json=data)

        if r.status_code == 201:
            d = r.json()

            uuid = UUID(d.get('task_id'))
            layer = Layer.objects.get(name=layer_name)
            submission_datetime = d.get('submission_datetime')
            details = d

            AsyncExtractorTask.objects.create(
                uuid=uuid, user=user, layer=layer,
                submission_datetime=submission_datetime, details=details)

            messages.success(request, '{}/{}'.format(EXTRACTOR_URL, str(uuid)))
            return HttpResponseRedirect(reverse('idgo_admin:extractor_dashboard'))
        else:
            messages.error(request, 'Ko')
            return render_with_info_profile(request, self.template, context=context)
