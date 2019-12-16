# Copyright (c) 2019 Neogeo-Technologies.
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


import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse


User = get_user_model()
logger = logging.getLogger('django')


class SidRemoteUserMiddleware(object):

    IGNORE_PATH = (
        # Urls ouvertes:
        # ...
    )

    header = getattr(settings, 'HEADER_UID', 'OIDC_CLAIM_uid')
    oidc_setted = getattr(settings, 'OIDC_SETTED', False)

    def __init__(self, get_response):
        self.get_response = get_response

    def process_request(self, request):
        sid_user_id = request.META.get(self.header)
        if self.oidc_setted and sid_user_id:
            logger.info('HEADER_UID: {header_uid}, VALUE: {value}'.format(
                header_uid=self.header,
                value=sid_user_id,
            ))
            logout(request)
            try:
                user = User.objects.get(username=sid_user_id)
            except User.DoesNotExist as e:
                logger.debug(e)
                raise PermissionDenied()
            else:
                backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user, backend=backend)
        # Sinon rien

    def __call__(self, request):
        if request.path not in self.IGNORE_PATH or \
                not request.path.startswith(reverse('admin:index')):
            self.process_request(request)
        response = self.get_response(request)
        return response


class ForceRedirectToHome(object):

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user and hasattr(user, 'profile') \
                and request.path == reverse('server_cas:signIn'):
            return redirect(reverse('idgo_admin:home'))
        return self.get_response(request)
