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
from django.core.serializers import serialize
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.jurisdiction import JurisdictionForm as Form
from idgo_admin.models import BaseMaps
from idgo_admin.models import Commune
from idgo_admin.models import Jurisdiction
from idgo_admin.models import JurisdictionCommune
from idgo_admin.models import Organisation
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile


CKAN_URL = settings.CKAN_URL

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class JurisdictionView(View):

    namespace = 'idgo_admin:jurisdiction'
    template = 'idgo_admin/jurisdiction/edit.html'

    @ExceptionsHandler(
        ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, code):

        user, profile = user_and_profile(request)

        jurisdiction = get_object_or_404(Jurisdiction, code=code)

        organisation = None
        organisation_id = request.GET.get('organisation')
        if organisation_id:
            try:
                organisation = Organisation.objects.get(id=organisation_id)
            except Organisation.DoesNotExist:
                pass

        form = Form(instance=jurisdiction, include={'user': user})

        basemaps = BaseMaps.objects.all()
        communes = serialize(
            'geojson', Commune.objects.all().transform(srid=4326),
            geometry_field='geom')

        context = {
            'basemaps': basemaps,
            'communes': communes,
            'form': form,
            'organisation': organisation}

        return render_with_info_profile(request, self.template, context=context)

    @ExceptionsHandler(
        ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, code):

        user, profile = user_and_profile(request)

        jurisdiction = get_object_or_404(Jurisdiction, code=code)

        organisation = None
        organisation_id = request.GET.get('organisation')
        if organisation_id:
            try:
                organisation = Organisation.objects.get(id=organisation_id)
            except Organisation.DoesNotExist:
                pass

        form = Form(request.POST, instance=jurisdiction, include={'user': user})

        basemaps = BaseMaps.objects.all()
        communes = serialize(
            'geojson', Commune.objects.all().transform(srid=4326),
            geometry_field='geom')

        context = {
            'basemaps': basemaps,
            'communes': communes,
            'form': form,
            'organisation': organisation}

        if not form.is_valid():
            return render_with_info_profile(
                request, self.template, context=context)

        for item in form.Meta.property_fields:
            setattr(jurisdiction, item, form.cleaned_data[item])
        jurisdiction.save(back=code)

        for instance in JurisdictionCommune.objects.filter(jurisdiction=jurisdiction):
            if instance.commune not in form.cleaned_data['communes']:
                instance.delete()
        for commune in form.cleaned_data['communes']:
            kvp = {'jurisdiction': jurisdiction, 'commune': commune}
            try:
                JurisdictionCommune.objects.get(**kvp)
            except JurisdictionCommune.DoesNotExist:
                kvp['created_by'] = profile
                JurisdictionCommune.objects.create(**kvp)

        messages.success(
            request, 'Le territoire de compétence a été mis à jour avec succès.')

        if jurisdiction.code != code:
            redirect_to = reverse(self.namespace, kwargs={'code': jurisdiction.code})
            if organisation:
                redirect_to = '{0}?organisation={1}'.format(reversed, organisation.id)
            return HttpResponseRedirect(redirect_to)
        else:
            return render_with_info_profile(request, self.template, context=context)
