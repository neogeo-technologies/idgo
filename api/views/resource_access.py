# Copyright (c) 2017-2021 Neogeo-Technologies.
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


from functools import reduce
import logging
from operator import ior

from django.apps import apps
from django.db.models import Q
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from rest_framework import permissions
from rest_framework.views import APIView

from idgo_admin.models import Dataset
from idgo_admin.models import Resource
from idgo_admin.models import Organisation


logger = logging.getLogger('api.views')


if apps.is_installed('idgo_resource') \
        and apps.is_installed('idgo_geographic_layer'):
    from idgo_resource.models import Resource as ResourceBeta
    from idgo_geographic_layer.models import GeographicLayer as GeographicLayerBeta
    BETA = True
else:
    BETA = False


def serialize_resources(resources, resources_beta=None):

    data = []
    for resource in resources:
        data.append({
            'id': resource.id,
            'title': resource.title,
            'anonymous_access': resource.anonymous_access,
            })
    if BETA:
        for resource in resources_beta:
            data.append({
                'id': resource.id,
                'title': resource.title,
                'anonymous_access': resource.resourcerestricted.anonymous_access,
                })
    return data


class ResourceAccessShow(APIView):

    permission_classes = [
        permissions.IsAuthenticated,
    ]

    def get(self, request, resource_id):
        """Voir si l'utilisateur a le droit de voir la ressource"""
        user = request.user

        try:
            resource = get_object_or_404(Resource, id=resource_id)
            if resource.is_profile_authorized(user):
                return JsonResponse(dict(access='granted'))
        except Http404 as e:
            if BETA:
                resource = get_object_or_404(ResourceBeta, id=resource_id)
                if resource.resourcerestricted.is_profile_authorized(user):
                    return JsonResponse(dict(access='granted'))

        return JsonResponse(dict(access='denied'))


class ResourceAccessList(APIView):

    def get(self, request):
        """Voir la ressource associée au layer/ressource."""

        resources = None
        resources_beta = None

        try:
            layers = request.GET['layers']
            layers = set(layers.replace(' ', '').split(','))
            layers = [layer.split(':')[-1] for layer in layers]

            datasets_filters = [
                Q(slug__in=layers),
                Q(organisation__in=Organisation.objects.filter(slug__in=layers).distinct()),
                ]
            datasets = Dataset.objects.filter(reduce(ior, datasets_filters)).distinct()
            resources_filters = [
                Q(dataset__in=datasets),
                Q(layer__name__in=layers),
                ]
            resources = Resource.objects.filter(reduce(ior, resources_filters)).distinct()

            if BETA:
                resources_beta_filters = [
                    Q(dataset__in=datasets),
                    Q(geographiclayer__name__in=layers),
                    ]
                resources_beta = ResourceBeta.objects.filter(
                    reduce(ior, resources_beta_filters)).distinct()
        except ValueError as e:
            logger.error(e)
            raise Http404()

        if resources or resources_beta:
            return JsonResponse(
                serialize_resources(resources, resources_beta=resources_beta),
                safe=False)

        raise Http404()
