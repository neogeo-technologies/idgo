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
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.forms.layer import LayerForm as Form
from idgo_admin.models import Layer
from idgo_admin.mra_client import MRAHandler
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
import json


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class LayerView(View):

    namespace = 'idgo_admin:layer_editor'
    template = 'idgo_admin/dataset/resource/layer/edit.html'

    def get(self, request, dataset_id=None, resource_id=None, layer_id=None, *args, **kwargs):

        user, profile = user_and_profile(request)

        layer = get_object_or_404(Layer, resource=resource_id)
        form = Form(instance=layer, include={'user': user})

        context = {
            'form': form,
            'layer': layer}

        return render_with_info_profile(request, self.template, context=context)

    def post(self, request, dataset_id=None, resource_id=None, layer_id=None, *args, **kwargs):

        user, profile = user_and_profile(request)

        layer = get_object_or_404(Layer, resource=resource_id)
        form = Form(request.POST, instance=layer, include={'user': user})

        context = {
            'form': form,
            'layer': layer}

        if not form.is_valid():
            return render_with_info_profile(request, self.template, context=context)

        try:
            MRAHandler.update_layer(layer_id, {
                'name': layer_id,
                'title': form.cleaned_data['title'],
                'abstract': form.cleaned_data['abstract']})
        except ValidationError as e:
            messages.error(request, ' '.join(e))
        except Exception as e:
            messages.error(request, e.__str__())
        else:
            messages.success(request, 'Les informations ont été mise à jour avec succès.')

        if 'save' in request.POST:
            to = reverse('idgo_admin:layer_editor', kwargs={
                'dataset_id': dataset_id,
                'resource_id': resource_id,
                'layer_id': layer_id})
        else:
            to = reverse('idgo_admin:layer_editor', kwargs={
                'dataset_id': dataset_id,
                'resource_id': resource_id,
                'layer_id': layer_id})

        return HttpResponseRedirect(to)


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def layer_styles(request, dataset_id=None, resource_id=None, layer_id=None, *args, **kwargs):

    user, profile = user_and_profile(request)

    layer = get_object_or_404(Layer, resource=resource_id)

    context = {
        'layer': layer}

    return render_with_info_profile(
        request, 'idgo_admin/dataset/resource/layer/style/styles.html', context=context)


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def layer_style(request, dataset_id=None, resource_id=None, layer_id=None, *args, **kwargs):

    user, profile = user_and_profile(request)

    style_id = request.GET.get('id', None)
    if not id:
        raise Http404

    layer = get_object_or_404(Layer, resource=resource_id)

    return redirect(reverse('idgo_admin:layer_style_editor', kwargs={
        'dataset_id': dataset_id,
        'resource_id': resource_id,
        'layer_id': layer_id,
        'style_id': style_id}))


def get_layer(resource, datagis_id):
    if datagis_id not in resource.datagis_id:
        raise Http404

    datagis_id = str(datagis_id)
    layer = MRAHandler.get_layer(datagis_id)
    if layer['type'] == 'RASTER':
        c = MRAHandler.get_coverage(resource.dataset.organisation.ckan_slug, datagis_id, datagis_id)
        ll = c['coverage']['latLonBoundingBox']
        bbox = [[ll['miny'], ll['minx']], [ll['maxy'], ll['maxx']]]
        attributes = []
        default_style_name = None
        styles = []
    else:
        ft = MRAHandler.get_featuretype(resource.dataset.organisation.ckan_slug, 'public', datagis_id)
        ll = ft['featureType']['latLonBoundingBox']
        bbox = [[ll['miny'], ll['minx']], [ll['maxy'], ll['maxx']]]
        attributes = [item['name'] for item in ft['featureType']['attributes']]
        default_style_name = layer['defaultStyle']['name']
        styles = [{
            'name': 'default',
            'text': 'Style par défaut',
            'url': layer['defaultStyle']['href'].replace('json', 'sld'),
            'sld': MRAHandler.get_style(layer['defaultStyle']['name'])}]
        if layer.get('styles'):
            for style in layer.get('styles')['style']:
                styles.append({
                    'name': style['name'],
                    'text': style['name'],
                    'url': style['href'].replace('json', 'sld'),
                    'sld': MRAHandler.get_style(style['name'])})

    return {
        'id': datagis_id,
        'name': layer['name'],
        'title': layer['title'],
        'type': layer['type'],
        'enabled': layer['enabled'],
        'bbox': bbox,
        'attributes': attributes,
        'styles': {'default': default_style_name, 'styles': styles}}


def get_layers(resource):
    layers = []
    for datagis_id in resource.datagis_id:
        data = get_layer(resource, datagis_id)
        layers.append([
            data['id'],
            data['name'],
            data['title'],
            data['type'],
            data['enabled'],
            data['bbox'],
            data['attributes'],
            data['styles']])
    return(layers)


@method_decorator(decorators, name='dispatch')
class LayerStyleEditorView(View):

    namespace = 'idgo_admin:layer_style_editor'

    def get(self, request, dataset_id=None, resource_id=None, layer_id=None, style_id=None, *args, **kwargs):

        user, profile = user_and_profile(request)

        layer = get_object_or_404(Layer, resource=resource_id)

        layer_asjson = json.dumps(get_layer(layer.resource, layer_id))

        context = {
            'layer': layer,
            'fonts_asjson': json.dumps(MRAHandler.get_fonts()),
            'layer_asjson': layer_asjson}

        return render_with_info_profile(request, 'idgo_admin/dataset/resource/layer/style/edit.html', context=context)

    def post(self, request, dataset_id=None, resource_id=None, layer_id=None, style_id=None, *args, **kwargs):

        user, profile = user_and_profile(request)

        sld = request.POST.get('sldBody')

        try:
            MRAHandler.create_or_update_style(layer_id, data=sld.encode('utf-8'))
            MRAHandler.update_layer_defaultstyle(layer_id, layer_id)
        except ValidationError as e:
            messages.error(request, ' '.join(e))
        except Exception as e:
            messages.error(request, e.__str__())
        else:
            message = 'Le style a été mis à jour avec succès.'
            messages.success(request, message)

        if 'save' in request.POST:
            to = reverse('idgo_admin:layer_styles', kwargs={
                'dataset_id': dataset_id,
                'resource_id': resource_id,
                'layer_id': layer_id})
        else:
            to = reverse('idgo_admin:layer_style_editor', kwargs={
                'dataset_id': dataset_id,
                'resource_id': resource_id,
                'layer_id': layer_id,
                'style_id': style_id})

        return HttpResponseRedirect(to)
