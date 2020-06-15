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
from urllib.parse import parse_qs
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse

from mama_cas.compat import is_authenticated
from mama_cas.models import ServiceTicket
from mama_cas.models import ProxyTicket
from mama_cas.models import ProxyGrantingTicket

from sid import CKAN_URL
from sid import HEADER_UID
from sid import OIDC_SETTED
from sid import SSO_LOGOUT_URL
from sid import VIEWERSTUDIO_URL


User = get_user_model()

logger = logging.getLogger('sid')


class SidRemoteUserMiddleware(object):

    IGNORE_PATH = (
        # Urls ouvertes:
        # ...
    )

    header = HEADER_UID
    oidc_setted = OIDC_SETTED

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

        request_uri = request.META.get('REQUEST_URI')

        try:
            parsed_uri = urlparse(request_uri).query
            service_url = parse_qs(parsed_uri).get('service')[0]
            requester = urlparse(service_url).netloc
        except Exception:
            from_ckan = False
            from_viewerstudio = False
        else:
            from_ckan = requester == urlparse(CKAN_URL).netloc
            from_viewerstudio = requester == urlparse(VIEWERSTUDIO_URL).netloc

        if request.path not in self.IGNORE_PATH or \
                not request.path.startswith(reverse('admin:index')) \
                and not from_ckan \
                and not from_viewerstudio:
            self.process_request(request)

        response = self.get_response(request)
        return response


class ForceRedirectToHome(object):

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        request_uri = request.META.get('REQUEST_URI')

        try:
            parsed_uri = urlparse(request_uri).query
            service_url = parse_qs(parsed_uri).get('service')[0]
            requester = urlparse(service_url).netloc
        except Exception:
            from_ckan = False
            from_viewerstudio = False
        else:
            from_ckan = requester == urlparse(CKAN_URL).netloc
            from_viewerstudio = requester == urlparse(VIEWERSTUDIO_URL).netloc

        if user and hasattr(user, 'profile') \
                and request.path == reverse('server_cas:signIn') \
                and not from_ckan \
                and not from_viewerstudio:
            return redirect(reverse('idgo_admin:home'))

        return self.get_response(request)


class LogOut(object):

    sso_logout_url = SSO_LOGOUT_URL

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if user and hasattr(user, 'profile') \
                and request.path == reverse('server_cas:signOut') \
                and is_authenticated(user):

            ServiceTicket.objects.consume_tickets(user)
            ProxyTicket.objects.consume_tickets(user)
            ProxyGrantingTicket.objects.consume_tickets(user)
            ServiceTicket.objects.request_sign_out(user)

            logger.info("Single sign-on session ended for %s" % user)
            logout(request)

            return redirect(self.sso_logout_url)

        return self.get_response(request)
