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


from collections import OrderedDict
# from django.conf import settings
# from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.api.utils import BasicAuth
from idgo_admin.models import Organisation


def serialize(organisation):

    if organisation.organisation_type:
        type = organisation.organisation_type.code
    else:
        type = None

    if organisation.jurisdiction:
        jurisdiction = organisation.jurisdiction.code
    else:
        jurisdiction = None

    if organisation.license:
        license = organisation.license.slug
    else:
        license = None

    return OrderedDict([
        ('name', organisation.ckan_slug),
        ('legal_name', organisation.name),
        ('type', type),
        ('jurisdiction', jurisdiction),
        ('contact_information', OrderedDict([
            ('address', organisation.address or None),
            ('postcode', organisation.postcode or None),
            ('city', organisation.city or None),
            ('phone', organisation.phone or None),
            ])),
        ('license', license),
        ('active', organisation.is_active),
        ('crige', organisation.is_crige_partner),
        ])


def handler_get_request(request):
    user = request.user
    if user.profile.is_admin:
        # Un administrateur « métiers » peut tout voir.
        organisations = Organisation.objects.all()
    else:
        s1 = set(user.profile.referent_for)
        s2 = set(user.profile.contribute_for)
        s3 = set([user.profile.organisation])
        organisations = list(s1 | s2 | s3)
    return [serialize(organisation) for organisation in organisations]


# decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]
# decorators = [csrf_exempt, BasicAuth()]
decorators = [csrf_exempt]


@method_decorator(decorators, name='dispatch')
class OrganisationShow(View):

    def get(self, request, organisation_name):
        organisations = handler_get_request(request)
        for organisation in organisations:
            if organisation['name'] == organisation_name:
                return JsonResponse(organisation, safe=True)
        raise Http404()


@method_decorator(decorators, name='dispatch')
class OrganisationList(View):

    def get(self, request):
        organisations = handler_get_request(request)
        return JsonResponse(organisations, safe=False)
