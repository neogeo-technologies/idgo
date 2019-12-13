# Copyright (c) 2017-2019 Neogeo-Technologies.
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
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth import logout
from django.urls import reverse
import logging


User = get_user_model()
logger = logging.getLogger('django')


class SidRemoteUserMiddleware(object):

    # TODO definir les url ouvertes
    IGNORE_PATH = (
        # reverse(settings.TERMS_URL),
        # Un utilisateur doit pouvoir se connecter et se déconnecter
        # reverse(settings.LOGIN_URL),
        # reverse(settings.LOGOUT_URL),
    )

    header = getattr(settings, 'HEADER_UID', 'OIDC_CLAIM_uid')

    oidc_setted = getattr(settings, 'OIDC_SETTED', False)

    def __init__(self, get_response):
        self.get_response = get_response

    def get_user(self, unique_id):
        try:
            return User.objects.get(username=unique_id)
        except Exception:
            logger.exception(self.__class__.__name__)

    def process_request(self, request):
        sid_user_id = request.META.get(self.header)
        if sid_user_id and self.oidc_setted:
            logger.info("HEADER_UID: {}, VALUE: {}".format(self.header, sid_user_id))
            logout(request)
            user = self.get_user(sid_user_id)
            if user:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    def __call__(self, request):
        if request.path not in self.IGNORE_PATH or \
                not request.path.startswith(reverse('admin:index')):
            self.process_request(request)
        response = self.get_response(request)
        return response
