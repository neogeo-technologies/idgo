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


import io
import logging

from django.core import files
from django.http import Http404
from django.http import HttpResponse
import requests
from rest_framework import mixins
from rest_framework import permissions
from rest_framework import viewsets
from rest_framework import status
from rest_framework.parsers import MultiPartParser
import xmltodict

from idgo_admin.models import License
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType
from sid.xml_io import XMLRenderer
from sid.xml_io import XMLtParser
from sid.exceptions import SidGenericError


logger = logging.getLogger('sid')


class AbstractOrgViews(mixins.CreateModelMixin, mixins.UpdateModelMixin,
                       mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = Organisation.objects.all()
    parser_classes = [
        # Si le contenu est envoyé raw
        XMLtParser,
        # Si le fichier est envoyé dans le form-data dans la clé 'file'
        MultiPartParser,
    ]
    renderer_classes = [XMLRenderer, ]
    permission_classes = [
        # permissions.IsAuthenticated,  # TODO limiter aux connectés
        permissions.AllowAny
    ]
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'
    http_method_names = ['post', 'put']  # ['post', 'put', 'delete']

    license_slug = 'lov2'
    license_defaults = {
        'url': 'https://www.etalab.gouv.fr/licence-ouverte-open-licence',
        'title': "Licence Ouverte Version 2.0",
    }

    def get_object(self):
        try:
            instance = super().get_object()
        except Http404:
            raise SidGenericError(
                client_error_code='003',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': self.kwargs.get('slug', 'N/A'),
                },
                status_code=status.HTTP_404_NOT_FOUND
            )
        return instance

    def get_data(self, request):
        data = None
        if request.FILES.get('file'):
            _file = request.FILES.get('file')
            data = xmltodict.parse(_file)
        else:
            data = request.data
        return data

    def save_logo(self, instance, root):
        logo_url = root.get('logoUrl')
        if not logo_url:
            return

        res = requests.get(logo_url)
        if not res.status_code == 200:
            return

        file = io.BytesIO(res.content)

        instance.logo.delete()
        instance.logo.save('logo', files.File(file), save=True)
        file.close()

    def parse_and_create(self, data):
        root = data.get(self.class_type.lower(), {})
        sid_id = root.get('id', None)
        if Organisation.objects.filter(slug=sid_id).exists():
            raise SidGenericError(
                client_error_code='005',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': sid_id,
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            # TODO une fois qu'on sera sur base de dev un simple get suffira
            organisation_type, _ = OrganisationType.objects.get_or_create(
                code=self.organisation_type_code,
                defaults=self.organisation_type_defaults
            )
            lic, _ = License.objects.get_or_create(
                slug=self.license_slug,
                defaults=self.license_defaults
            )

            defaults = {
                'slug': root['id'],
                'legal_name': root['label'][:100],
                'description': root['name'],
                'email': root['email'],
                'address': root['address']['postalAddress'],
                'postcode': root['address']['postalCode'][:5],
                'city': root['address']['city'][:100],
                'is_active': True,
                'logo': root.get('logoUrl'),  # Optionnelle
                'phone': root.get('phone'),  # Optionnelle
                'organisation_type': organisation_type,
                'license': lic,
                'geonet_id': None,
                'is_crige_partner': False,
            }

            if self.class_type == 'ORGANISM':
                defaults['website'] = root['customer']['portalUrl']

            organisation = Organisation.objects.create(**defaults)
            self.save_logo(organisation, root)

        except Exception:
            logger.exception(self.__class__.__name__)
            raise SidGenericError(
                client_error_code='002',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': sid_id,
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )

        return organisation

    def parse_and_update(self, instance, data):
        root = data.get(self.class_type.lower(), {})
        sid_id = root.get('id', None)
        if sid_id != str(instance.slug):
            raise SidGenericError(
                client_error_code='002',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': instance.slug,
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )
        if not Organisation.objects.filter(slug=sid_id).exists():
            raise SidGenericError(
                client_error_code='003',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': instance.slug,
                },
                status_code=status.HTTP_404_NOT_FOUND
            )

        try:
            instance.legal_name = root['label'][:100]
            instance.description = root['name']
            instance.email = root['email']
            instance.address = root['address']['postalAddress']
            instance.postcode = root['address']['postalCode'][:5]
            instance.city = root['address']['city'][:100]

            if self.class_type == 'ORGANISM':
                instance.website = root['customer']['portalUrl']
                # instance.phone = root['phone']  # Manquant
            self.save_logo(instance, root)
            instance.save()
        except SidGenericError:
            raise
        except Exception:
            logger.exception(self.__class__.__name__)
            raise SidGenericError(
                client_error_code='002',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': instance.slug,
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )

        return instance

    def create(self, request, *args, **kwargs):
        data = self.get_data(request)

        if not data:
            raise SidGenericError(
                client_error_code='001',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )

        instance = self.parse_and_create(data)
        logger.info('Organisation::create() OK: id->{}, sid_id->{}'.format(
            instance.id,
            instance.slug,
        ))
        response = HttpResponse(status=201)
        response['Content-Location'] = ''  # Pas de content-Location
        return response

    def update(self, request, *args, **kwargs):

        data = self.get_data(request)
        sid_id = self.kwargs.get(self.lookup_url_kwarg, '')
        if not data:
            raise SidGenericError(
                client_error_code='001',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': sid_id,
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )
        else:
            # On permet la creation à partir du PUT
            try:
                # On appel get_object() pour le 404 custom
                instance = self.get_object()
            except SidGenericError:
                instance = self.parse_and_create(data)
                logger.info('create() from PUT OK: id->{}, slug->{}'.format(
                    instance.id,
                    instance.slug,
                ))
            else:
                instance = self.parse_and_update(instance, data)
                logger.info('update() OK: id->{}, slug->{}'.format(
                    instance.id,
                    instance.slug,
                ))
            return HttpResponse(status=200)

    def destroy(self, request, *args, **kwargs):
        # On appel get_object() pour le 404 custom
        instance = self.get_object()
        try:
            instance.delete()
        except Exception:
            raise SidGenericError(
                client_error_code='006',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': instance.slug,
                },
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return HttpResponse(status=200)


class OrganismViews(AbstractOrgViews):
    class_type = 'ORGANISM'
    organisation_type_code = 'organisme-public'
    organisation_type_defaults = {'name': 'Organisme publique'}


class CompanyViews(AbstractOrgViews):
    class_type = 'COMPANY'
    organisation_type_code = 'entreprise'
    organisation_type_defaults = {'name': 'Entreprise'}
