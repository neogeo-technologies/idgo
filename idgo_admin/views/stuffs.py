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
from django.contrib.sites.models import Site
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.models import License
from idgo_admin.shortcuts import user_and_profile
import redis
import requests
import uuid


strict_redis = redis.StrictRedis()
REDIS_EXPIRATION = 10

try:
    IS_SECURE = settings.IS_SECURE
except AttributeError:
    IS_SECURE = False

OWS_PREVIEW_URL = settings.OWS_PREVIEW_URL

try:
    MAPSERV_TIMEOUT = settings.MAPSERV_TIMEOUT
except AttributeError:
    MAPSERV_TIMEOUT = 60


@method_decorator([csrf_exempt], name='dispatch')
class DisplayLicenses(View):

    def get(self, request):
        data = [{
            'domain_content': license.domain_content,
            'domain_data': license.domain_data,
            'domain_software': license.domain_software,
            'family': '',  # TODO?
            'id': license.ckan_id,  # license.license_id
            'maintainer': license.maintainer,
            'od_conformance': license.od_conformance,
            'osd_conformance': license.osd_conformance,
            'status': license.status,
            'title': license.title,
            'url': license.url} for license in License.objects.all()]
        return JsonResponse(data, safe=False)


@csrf_exempt
def ows_preview(request):
    user, profile = user_and_profile(request)

    r = requests.get(
        OWS_PREVIEW_URL, params=dict(request.GET), timeout=MAPSERV_TIMEOUT)
    r.raise_for_status()
    return HttpResponse(r.content, content_type=r.headers['Content-Type'])


@method_decorator([csrf_exempt, login_required(login_url=settings.LOGIN_URL)], name='dispatch')
class SLDPreviewSetter(View):

    def post(self, request, *args, **kwargs):
        sld = request.POST.get('sld')
        key = str(uuid.uuid4())
        strict_redis.set(key, sld)
        strict_redis.expire(key, REDIS_EXPIRATION)

        location = 'http{secure}://{domain}{path}'.format(
            secure=IS_SECURE and 's' or '',
            domain=Site.objects.get(name='admin').domain,
            path=reverse('idgo_admin:sld_preview_getter', kwargs={'key': key})
            )

        response = HttpResponse(status=201)
        response['Content-Location'] = location
        return response


@method_decorator([csrf_exempt, login_required(login_url=settings.LOGIN_URL)], name='dispatch')
class SLDPreviewGetter(View):

    def get(self, request, key=None, *args, **kwargs):

        sld = strict_redis.get(key)
        if not sld:
            raise Http404
        return HttpResponse(sld, status=200, content_type='application/vnd.ogc.sld+xml')
