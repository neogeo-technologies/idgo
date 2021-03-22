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


import redis
import urllib.parse
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.http import HttpResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View

from idgo_admin import REDIS_HOST
from idgo_admin import REDIS_EXPIRATION
from idgo_admin import LOGIN_URL

from idgo_admin import HOST_INTERNAL
from idgo_admin import PORT_INTERNAL


strict_redis = redis.StrictRedis(REDIS_HOST)


@method_decorator([csrf_exempt, login_required(login_url=LOGIN_URL)], name='dispatch')
class SLDPreviewSetter(View):

    def post(self, request, *args, **kwargs):

        sld = request.POST.get('sld')
        key = str(uuid.uuid4())
        strict_redis.set(key, sld)
        strict_redis.expire(key, REDIS_EXPIRATION)

        response = HttpResponse(status=201)
        location = request.build_absolute_uri(
            reverse('idgo_admin:sld_preview_getter', kwargs={'key': key}))

        # C'est moche
        if HOST_INTERNAL and PORT_INTERNAL:
            netloc = '{host}:{port}'.format(
                host=HOST_INTERNAL, port=PORT_INTERNAL)
            parsed = urllib.parse.urlparse(location)
            replaced = parsed._replace(netloc=netloc)
            response['Content-Location'] = replaced.geturl()
        else:
            response['Content-Location'] = location

        return response


@method_decorator([csrf_exempt], name='dispatch')
class SLDPreviewGetter(View):

    def get(self, request, key=None, *args, **kwargs):

        sld = strict_redis.get(key)
        if not sld:
            raise Http404
        return HttpResponse(sld, status=200, content_type='application/vnd.ogc.sld+xml')
