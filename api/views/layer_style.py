# Copyright (c) 2017-2020 Neogeo-Technologies.
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


from api.utils import parse_request
from django.http import Http404
from django.http import HttpResponse
from idgo_admin.models import Dataset
from rest_framework import permissions
from rest_framework.views import APIView
from uuid import UUID
from idgo_admin.mra_client import MRAHandler


def handler_get_request(request, dataset_name, resource_id, layer_name):
    user = request.user
    dataset = None
    if user.profile.is_admin:
        dataset = Dataset.objects.get(slug=dataset_name)
    else:
        s1 = set(Dataset.objects.filter(organisation__in=user.profile.referent_for))
        s2 = set(Dataset.objects.filter(editor=user))
        for item in list(s1 | s2):
            if item.slug == dataset_name:
                dataset = item
                break
    if not dataset:
        return []
    resource = dataset.get_resources(ckan_id=resource_id)
    if not resource:
        return []
    layer = resource[0].get_layers(name=layer_name)
    return layer[0]


class LayerStyleDefaultShow(APIView):

    permission_classes = [
        permissions.IsAuthenticated,
        ]

    def get(self, request, dataset_name, resource_id, layer_name):
        try:
            resource_id = UUID(resource_id)
        except ValueError:
            raise Http404()
        layer = handler_get_request(request, dataset_name, resource_id, layer_name)
        sld = layer.get_default_sld()
        return HttpResponse(sld, status=200, content_type='application/vnd.ogc.sld+xml')

    def put(self, request, dataset_name, resource_id, layer_name):
        if not request.content_type == 'application/vnd.ogc.sld+xml':
            raise Http404()

        try:
            resource_id = UUID(resource_id)
        except ValueError:
            raise Http404()
        sld = request.body
        MRAHandler.create_or_update_style(layer_name, data=sld)
        MRAHandler.update_layer_defaultstyle(layer_name, layer_name)

        return HttpResponse(status=204)