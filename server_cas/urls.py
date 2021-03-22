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


from django.conf.urls import url

from server_cas.views import SignIn
from server_cas.views import SignOut


urlpatterns = [
    url('^cas/login/?$', SignIn.as_view(), name='signIn'),
    url('^cas/logout/?$', SignOut.as_view(), name='signOut'),
    url('^signin/?$', SignIn.as_view(), name='signIn'),
    url('^signout/?$', SignOut.as_view(), name='signOut'),
]
