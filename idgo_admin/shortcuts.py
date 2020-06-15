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


from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import reverse

from idgo_admin.models import Profile
from idgo_admin.models import Resource


def on_profile_http404():
    return HttpResponseRedirect(reverse('server_cas:signIn'))


def get_object_or_404_extended(MyModel, user, include):
    res = None
    profile = get_object_or_404(Profile, user=user)
    instance = get_object_or_404(MyModel, **include)

    i_am_resource = (MyModel.__name__ == Resource.__name__)
    dataset = instance.dataset if i_am_resource else instance

    is_referent = dataset.is_referent(profile)
    is_contributor = dataset.is_contributor(profile)
    is_editor = dataset.editor == profile.user

    if profile.is_admin or is_referent:
        res = instance
    if is_contributor and is_editor:
        res = instance

    if not res:
        raise PermissionDenied
    return res
