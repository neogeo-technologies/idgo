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
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.api.utils import BasicAuth
from idgo_admin.api.utils import parse_request
from idgo_admin.exceptions import GenericException
from idgo_admin.forms.organisation import OrganizationForm as Form
from idgo_admin.models import AccountActions
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
        ('logo', organisation.logo_url),
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


def handle_pust_request(request, organisation_name=None):
    # legal_name -> name
    # type -> organisation_type
    # jurisdiction -> jurisdiction.pk
    # address -> address
    # postcode -> postcode
    # city -> city
    # phone -> phone
    # email -> email
    # license -> license.pk
    user = request.user

    organisation = None
    if organisation_name:
        organisation = get_object_or_404(
            Organisation, ckan_slug=organisation_name)

    data = getattr(request, request.method).dict()
    data_form = {
        'name': data.get('legal_name'),
        'description': data.get('description'),
        'organisation_type': data.get('type'),
        'address': data.get('address'),
        'postcode': data.get('postcode'),
        'city': data.get('city'),
        'phone': data.get('phone'),
        'email': data.get('email'),
        'license': data.get('license'),
        'jurisdiction': data.get('jurisdiction'),
        }

    form = Form(
        data_form, request.FILES,
        instance=organisation, include={'user': user})
    if not form.is_valid():
        return GenericException(details=form._errors)

    data = form.cleaned_data
    kvp = dict((item, form.cleaned_data[item])
               for item in form.Meta.organisation_fields)

    try:
        with transaction.atomic():
            if organisation_name:
                for item in form.Meta.fields:
                    if item in data_form:
                        setattr(organisation, item, data_form[item])
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


# decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]
# decorators = [csrf_exempt, BasicAuth()]
decorators = [csrf_exempt]


@method_decorator(decorators, name='dispatch')
class OrganisationShow(View):

    def get(self, request, organisation_name):
        """Voir l'organisation."""
        organisations = handler_get_request(request)
        for organisation in organisations:
            if organisation['name'] == organisation_name:
                return JsonResponse(organisation, safe=True)
        raise Http404()

    @BasicAuth()
    def put(self, request, organisation_name):
        """Créer une nouvelle organisation."""
        # Django fait les choses à moitié...
        request.PUT, request._files = parse_request(request)
        if not request.user.profile.is_admin:
            raise Http404()
        try:
            handle_pust_request(request, organisation_name=organisation_name)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        return HttpResponse(status=204)


@method_decorator(decorators, name='dispatch')
class OrganisationList(View):

    def get(self, request):
        """Voir les organisations."""
        organisations = handler_get_request(request)
        return JsonResponse(organisations, safe=False)

    @BasicAuth()
    def post(self, request):
        """Créer une nouvelle organisation."""
        if not request.user.profile.is_admin:
            raise Http404()
        try:
            handle_pust_request(request)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        response = HttpResponse(status=201)
        response['Content-Location'] = ''
        return response
