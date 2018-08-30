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


from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.models import Dataset
from idgo_admin.models import Layer
from idgo_admin.models import Resource
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
import json


@method_decorator([csrf_exempt], name='dispatch')
class Extractor(View):

    template = 'idgo_admin/extractor.html'
    namespace = 'idgo_admin:extractor'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404

        layer_id = request.GET.get('layer')
        resource_id = request.GET.get('resource')
        dataset_id = request.GET.get('dataset')

        if resource_id and dataset_id:
            organisation = get_object_or_404(Resource, id=resource_id, dataset__id=dataset_id).dataset.organisation
        elif dataset_id:
            organisation = get_object_or_404(Dataset, id=dataset_id).organisation
        else:
            raise Http404

        datasets = dict(
            (dataset.id, {
                'text': dataset.name,
                'resources': dict(
                    (resource.id, {
                        'text': resource.name,
                        'layer': [layer.mra_info for layer in Layer.objects.filter(resource=resource)][0]  # Contrainte actuelle
                        }) for resource in Resource.objects.filter(dataset=dataset))
                }) for dataset in Dataset.objects.filter(organisation=organisation).exclude(resource__layer=None))

        context = {
            'datasets': json.dumps(datasets),
            'focus_on': json.dumps({'dataset': dataset_id, 'resource': resource_id})}

        return render_with_info_profile(request, self.template, context=context)
