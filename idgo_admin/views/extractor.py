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
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.models import AsyncExtractorTask
from idgo_admin.models import Dataset
from idgo_admin.models import Layer
from idgo_admin.models import Resource
from idgo_admin.models import SupportedCrs
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
import json
import requests
from uuid import UUID


EXTRACTOR_URL = settings.EXTRACTOR_URL


@method_decorator([csrf_exempt], name='dispatch')
class ExtractorDashboard(View):

    template = 'idgo_admin/extractor_dashboard.html'
    namespace = 'idgo_admin:extractor_dashboard'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404

        context = {'tasks': AsyncExtractorTask.objects.filter(user=user)}

        return render_with_info_profile(request, self.template, context=context)


@method_decorator([csrf_exempt], name='dispatch')
class Extractor(View):

    template = 'idgo_admin/extractor.html'
    namespace = 'idgo_admin:extractor'

    def get_context(self, user, **kwargs):

        layer_id = kwargs.get('layer')
        resource_id = kwargs.get('resource')
        dataset_id = kwargs.get('dataset')

        if resource_id and dataset_id:
            resource = get_object_or_404(Resource, id=resource_id,
                                         dataset__id=dataset_id,
                                         dataset__published=True)
            dataset = resource.dataset
            organisation = dataset.organisation
        elif dataset_id:
            dataset = get_object_or_404(Dataset, id=dataset_id, published=True)
            organisation = dataset.organisation
        else:
            raise Http404

        d = {}

        resources = Resource.objects.filter(
            dataset__organisation=organisation, dataset__published=True).exclude(layer=None)

        for resource in resources:
            if not resource.is_profile_authorized(user):
                continue

            r = {
                'text': resource.name,
                'layer': [
                    layer.mra_info for layer
                    in Layer.objects.filter(resource=resource)
                    ][0]}  # 1 ressource = 1 layer

            if resource.dataset.id in d:
                d[resource.dataset.id]['resources'][resource.id] = r
            else:
                d[resource.dataset.id] = {
                    'text': resource.dataset.name,
                    'resources': {resource.id: r}}

        return {
            'supported_crs': SupportedCrs.objects.all(),
            'datasets': json.dumps(d),
            'focus_on': json.dumps({'dataset': dataset_id, 'resource': resource_id})}

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404

        context = self.get_context(
            user, layer=request.GET.get('layer'),
            resource=request.GET.get('resource'),
            dataset=request.GET.get('dataset'))

        return render_with_info_profile(request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404

        context = self.get_context(
            user, layer=request.GET.get('layer'),
            resource=request.GET.get('resource'),
            dataset=request.GET.get('dataset'))

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
        else:
            messages.error(request, 'Ko')

        return render_with_info_profile(request, self.template, context=context)
