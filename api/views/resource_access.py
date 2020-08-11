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

from functools import reduce
import logging
from operator import ior

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
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


def serialize_resources(resources):
    return [dict(id=resource.id,
                 title=resource.title,
                 anonymous_access=resource.anonymous_access,)
            for resource in resources]


class ResourceAccessShow(APIView):

    permission_classes = [
        permissions.IsAuthenticated,
    ]

    def get(self, request, resource_id):
        """Voir si l'utilisateur a le droit de voir la ressource"""
        user = request.user

        resource = Resource.objects.get(id=resource_id)
        if resource.is_profile_authorized(user):
            return JsonResponse(dict(access='granted'))

        return JsonResponse(dict(access='denied'))

class ResourceAccessList(APIView):

    def get(self, request, ):
        """Voir la ressource associée au layer/ressource."""
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

        except ValueError:
            raise Http404()
        if resources:
            return JsonResponse(serialize_resources(resources), safe=False)
        raise Http404()

