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


from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


try:
    TERMS_URL = getattr(settings, 'TERMS_URL')
    LOGIN_URL = getattr(settings, 'LOGIN_URL')
    LOGOUT_URL = getattr(settings, 'LOGOUT_URL')
except AttributeError as e:
    raise AssertionError("Missing mandatory parameter: %s" % e.__str__())


class BaseMiddleware(object):

    IGNORE_PATH = (
        reverse(TERMS_URL),
        reverse(LOGIN_URL),
        reverse(LOGOUT_URL),
    )

    def __init__(self, get_response):
        self.get_response = get_response


class ProfileRequired(BaseMiddleware):

    ADMIN_INDEX_URL = reverse('admin:index')

    def __call__(self, request):
        user = request.user
        if request.path not in self.IGNORE_PATH:
            if user.is_authenticated() and not hasattr(user, 'profile'):
                if not request.path.startswith(self.ADMIN_INDEX_URL):
                    return redirect(self.ADMIN_INDEX_URL)
        return self.get_response(request)


class TermsRequired(BaseMiddleware):

    def __call__(self, request):
        user = request.user
        if request.path not in self.IGNORE_PATH:
            if user.is_authenticated() and hasattr(user, 'profile'):
                if not user.profile.is_admin and not user.profile.is_agree_with_terms:
                    return redirect(reverse(TERMS_URL))
        return self.get_response(request)
