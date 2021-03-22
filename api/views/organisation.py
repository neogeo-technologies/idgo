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


from collections import OrderedDict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions
from rest_framework.views import APIView

from idgo_admin.exceptions import GenericException
from idgo_admin.forms.organisation import OrganisationForm as Form
from idgo_admin.models import AccountActions
from idgo_admin.models import Organisation

from api.utils import parse_request


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
        ('name', organisation.slug),
        ('legal_name', organisation.legal_name),
        ('logo', organisation.logo_url),
        ('type', type),
        ('jurisdiction', jurisdiction),
        ('contact_information', OrderedDict([
            ('address', organisation.address or None),
            ('postcode', organisation.postcode or None),
            ('city', organisation.city or None),
            ('phone', organisation.phone or None),
            # ('email', organisation.email or None),
            ])),
        ('website', organisation.website),
        ('license', license),
        ('active', organisation.is_active),
        ('is_idgo_partner', organisation.is_crige_partner),
    ])


def handler_get_request(request):
    # user = request.user
    # if user.profile.is_admin:
    #     # Un administrateur « métiers » peut tout voir.
    #     organisations = Organisation.objects.all()
    # else:
    #     s1 = set(user.profile.referent_for)
    #     s2 = set(user.profile.contribute_for)
    #     s3 = set([user.profile.organisation])
    #     organisations = list(s1 | s2 | s3)
    organisations = Organisation.objects.all()
    return [serialize(organisation) for organisation in organisations]


def handle_pust_request(request, organisation_name=None):
    user = request.user

    organisation = None
    if organisation_name:
        organisation = get_object_or_404(Organisation, slug=organisation_name)

    query_data = getattr(request, request.method)  # QueryDict

    is_idgo_partner = query_data.pop('is_idgo_partner', ['False'])
    if is_idgo_partner and is_idgo_partner[-1] in ['True', 'true', '1', 1]:
        is_idgo_partner = True
    else:
        is_idgo_partner = False

    # Slug/Name
    slug = query_data.pop('name', organisation and [organisation.slug])
    if slug:
        query_data.__setitem__('slug', slug[-1])

    # `legal_name` est obligatoire
    legal_name = query_data.pop('legal_name', organisation and [organisation.legal_name])
    if legal_name:
        query_data.__setitem__('legal_name', legal_name[-1])

    form = Form(query_data, request.FILES,
                instance=organisation, include={'user': user})
    if not form.is_valid():
        raise GenericException(details=form._errors)

    data = form.cleaned_data
    kvp = dict((item, form.cleaned_data[item])
               for item in form.Meta.organisation_fields)

    try:
        with transaction.atomic():
            if organisation_name:
                for item in form.Meta.fields:
                    if item in data:
                        setattr(organisation, item, data[item])
                setattr(organisation, 'is_crige_partner', is_idgo_partner)
                organisation.save()
            else:
                kvp['is_active'] = True
                organisation = Organisation.objects.create(**kvp)
                AccountActions.objects.create(
                    action='created_organisation_through_api',
                    organisation=organisation,
                    profile=user.profile,
                    closed=timezone.now())
    except ValidationError as e:
        return GenericException(details=e.__str__())

    return organisation


class OrganisationShow(APIView):

    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
    ]

    def get(self, request, organisation_name):
        """Voir l'organisation."""
        organisations = handler_get_request(request)
        for organisation in organisations:
            if organisation['name'] == organisation_name:
                return JsonResponse(organisation, safe=True)
        raise Http404()

    def put(self, request, organisation_name):
        """Mettre à jour l'organisation."""
        request.PUT, request._files = parse_request(request)
        request.PUT._mutable = True

        if not request.user.profile.is_admin:
            raise Http404()
        try:
            handle_pust_request(request, organisation_name=organisation_name)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        return HttpResponse(status=204)


class OrganisationList(APIView):

    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
    ]

    def get(self, request):
        """Voir les organisations."""
        organisations = handler_get_request(request)
        return JsonResponse(organisations, safe=False)

    def post(self, request):
        """Créer une nouvelle organisation."""
        request.POST._mutable = True
        if not request.user.profile.is_admin:
            raise Http404()
        try:
            organisation = handle_pust_request(request)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        response = HttpResponse(status=201)
        response['Content-Location'] = organisation.api_location
        return response
