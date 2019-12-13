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


from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponse
# from django.utils import timezone
from idgo_admin.ckan_module import CkanBaseError
from idgo_admin.ckan_module import CkanHandler
# from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from rest_framework.views import APIView
import logging
from rest_framework import mixins
from rest_framework import permissions
from rest_framework import viewsets
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from sid.xml_io import XMLtParser
from sid.xml_io import XMLRenderer
from sid.exceptions import SidGenericError
import xmltodict


logger = logging.getLogger('django')


class AbstractUsrViews(
        mixins.CreateModelMixin,
        mixins.UpdateModelMixin,
        mixins.DestroyModelMixin,
        viewsets.GenericViewSet):
    queryset = User.objects.all()
    parser_classes = [
        # Si le contenu est envoyé en raw
        XMLtParser,
        # Si le fichier est envoyé dans le form-data dans la clé 'file'
        MultiPartParser,
    ]
    renderer_classes = [XMLRenderer, ]
    permission_classes = [
        # permissions.IsAuthenticated, # TODO limiter aux connectés
        permissions.AllowAny
    ]
    lookup_field = 'username'
    lookup_url_kwarg = 'username'
    http_method_names = ['post', 'put', 'delete']

    def get_object(self):
        try:
            instance = super().get_object()
        except Exception:
            raise SidGenericError(
                client_error_code='003',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': self.kwargs.get('username', 'N/A'),
                },
                status_code=status.HTTP_404_NOT_FOUND
            )
        return instance

    @transaction.atomic
    def parse_and_create(self, data):
        root = data.get(self.profile_element, {})
        sid_id = root.get('id', None)
        if User.objects.filter(username=sid_id).exists():
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
            data_orga = root[self.orga_dept_element]
            orga = None
            if data_orga.get(self.orga_element):
                orga_sid = data_orga[self.orga_element]['id']
                try:
                    orga = Organisation.objects.get(slug=orga_sid)
                except Organisation.DoesNotExist:
                    # TODO tester les mécanismes de rejeu de la synchronisation
                    raise SidGenericError(
                        client_error_code='004',
                        extra_context={
                            'classType': self.class_orga_type,
                            'methodType': self.request.method,  # method en cours ou POST de création d'orga
                            'resourceId': orga_sid,  # identifiant de la relation manquante ou de la ressource
                        },
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

            data_user = root['user']
            user = User.objects.create(
                username=root['id'],  # data_user['username']
                email=root['email'],
                first_name=data_user['firstname'],
                last_name=data_user['lastname'],
                is_superuser=root['roles']['role']['label'] == "Administrateur Global",
                is_staff=root['roles']['role']['label'] == "Administrateur Global",
                is_active=data_user['enabled'] == "true",
            )

            profile = Profile.objects.create(
                user=user,
                organisation=orga,
                is_active=data_user['enabled'] == 'true',
                membership=orga is not None,
                # crige_membership,  # Manquant
                # is_admin,  # Manquant
                # sftp_password,  # Manquant
                # phone,  # Manquant
            )
            # if orga:
            #     LiaisonsContributeurs.objects.create(
            #         profile=profile,
            #         organisation=orga,
            #         created_on=timezone.now().date(),
            #         validated_on=timezone.now().date(),
            #     )
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

        try:
            CkanHandler.add_user(user, 'fake', state='active')
        except CkanBaseError:
            logger.exception(CkanBaseError.message)
            raise SidGenericError(
                client_error_code='006',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': sid_id,
                },
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return user

    @transaction.atomic
    def parse_and_update(self, user, data):

        root = data.get(self.profile_element, {})
        sid_id = root.get('id', None)
        if sid_id != str(user.username):
            raise SidGenericError(
                client_error_code='002',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': user.username,
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )
        if not User.objects.filter(username=sid_id).exists():
            raise SidGenericError(
                client_error_code='003',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': user.username,
                },
                status_code=status.HTTP_404_NOT_FOUND
            )
        try:
            data_orga = root[self.orga_dept_element]
            orga = None
            user.profile.contributions.clear()
            if data_orga.get(self.orga_element):
                orga_sid = data_orga[self.orga_element]['id']
                try:
                    orga = Organisation.objects.get(slug=orga_sid)
                except Organisation.DoesNotExist:
                    # TODO tester les mécanismes de rejeu de la synchronisation
                    raise SidGenericError(
                        client_error_code='004',
                        extra_context={
                            'classType': self.class_orga_type,
                            'methodType': self.request.method,  # method en cours ou POST de création d'orga
                            'resourceId': orga_sid,  # identifiant de la relation manquante ou de la ressource en cours
                        },
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

            data_user = root['user']
            user.first_name = data_user['firstname']
            user.last_name = data_user['lastname']
            # user.username = data_user['username']  # Modifiable
            user.email = root['email']
            user.is_superuser = root['roles']['role']['name'] == "administrateur"
            user.is_staff = root['roles']['role']['name'] == "administrateur"
            user.is_active = data_user['enabled'] == "true"
            user.save()

            user.profile.organisation = orga
            user.profile.is_active = data_user['enabled'] == "true"
            user.profile.membership = orga is not None
            # if orga:
            #     LiaisonsContributeurs.objects.create(
            #         profile=user.profile,
            #         organisation=orga,
            #         created_on=timezone.now().date(),
            #         validated_on=timezone.now().date(),
            #     )

        except Exception:
            logger.exception(self.__class__.__name__)
            raise SidGenericError(
                client_error_code='002',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': user.username,
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            CkanHandler.update_user(user)
        except CkanBaseError:
            logger.exception(CkanBaseError.message)
            raise SidGenericError(
                client_error_code='006',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': user.username,
                },
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return user

    def get_data(self, request):
        data = None
        if request.FILES.get('file'):
            _file = request.FILES.get('file')
            data = xmltodict.parse(_file)
        else:
            data = request.data
        return data

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
        else:
            instance = self.parse_and_create(data)
            logger.info('create() OK: id->{}, sid_id->{}'.format(
                instance.id,
                instance.username,
            ))
            return HttpResponse(status=201)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        data = self.get_data(request)
        if not data:
            raise SidGenericError(
                client_error_code='001',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': instance.username,
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )
        else:
            instance = self.parse_and_update(instance, data)
            logger.info('update() OK: id->{}, sid_id->{}'.format(
                instance.id,
                instance.username,
            ))
            return HttpResponse(status=200)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
            instance.profile.contributions.clear()
            instance.profile.delete()
        except Exception:
            logger.exception(self.__class__.__name__)
            raise SidGenericError(
                client_error_code='006',
                extra_context={
                    'classType': self.class_type,
                    'methodType': self.request.method,
                    'resourceId': instance.username,
                },
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        else:
            return HttpResponse(status=200)


class AgentViews(AbstractUsrViews):

    class_type = 'AGENT_PROFILE'
    profile_element = 'agentProfile'
    class_orga_type = 'ORGANISM'
    orga_dept_element = 'organismDepartment'
    orga_element = 'organism'


class EmployeeViews(AbstractUsrViews):

    class_type = 'EMPLOYEE_PROFILE'
    profile_element = 'employeeProfile'
    class_orga_type = 'COMPANY'
    orga_dept_element = 'companyDepartment'
    orga_element = 'company'


class TestAuthentViews(APIView):
    queryset = Profile.objects.all()
    parser_classes = [
        # Si le contenu est envoyé en raw
        XMLtParser,
        # Si le fichier est envoyé dans le form-data dans la clé 'file'
        MultiPartParser,
    ]
    # renderer_classes = [XMLRenderer, ]
    permission_classes = [
        # permissions.IsAuthenticated,
        permissions.IsAdminUser,
        # permissions.AllowAny
    ]

    http_method_names = ['get', ]

    def get(self, request, *args, **kargs):
        prf = Profile.objects.get(user=request.user)
        data = {
            # 'username': prf.user.username,
            'first_name': prf.user.first_name,
            'last_name': prf.user.last_name,
            'is_staff': prf.user.is_staff,
            'sid_id': prf.user.username,
            'organisation': prf.organisation.legal_name if prf.organisation else ''
        }
        return Response(data=data, status=status.HTTP_200_OK)
