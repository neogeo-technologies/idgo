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


from api.utils import parse_request
from collections import OrderedDict
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import GenericException
from idgo_admin.forms.resource import ResourceForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models.mail import send_resource_creation_mail
from idgo_admin.models.mail import send_resource_delete_mail
from idgo_admin.models.mail import send_resource_update_mail
from idgo_admin.models import Organisation
from idgo_admin.models import Resource
from idgo_admin.shortcuts import get_object_or_404_extended
from rest_framework import permissions
from rest_framework.views import APIView
from uuid import UUID


def serialize(resource):

    if resource.format_type:
        format = OrderedDict([
            ('id', resource.format_type.pk),
            ('description', resource.format_type.description),
            ])
    else:
        format = None

    if resource.up_file:
        source = OrderedDict([
            ('type', 'uploaded'),
            ('filename', resource.up_file.name),
            ])
    elif resource.dl_url:
        source = OrderedDict([
            ('type', 'downloaded'),
            ('url', resource.dl_url),
            ])
    elif resource.referenced_url:
        source = OrderedDict([
            ('type', 'referenced'),
            ('url', resource.dl_url),
            ])
    elif resource.ftp_file:
        source = OrderedDict([
            ('type', 'ftp'),
            ('filename', resource.ftp_file.name),
            ])

    return OrderedDict([
        ('id', resource.ckan_id),
        ('title', resource.title),
        ('description', resource.description),
        ('format', format),
        ('source', source),
        ('type', resource.data_type),
        # TODO
        ])


def handler_get_request(request, dataset_name):
    user = request.user
    dataset = None
    if user.profile.is_admin:
        dataset = Dataset.objects.get(slug=dataset_name)
    else:
        s1 = set(Dataset.objects.filter(organisation__in=user.profile.referent_for))
        s2 = set(Dataset.objects.filter(editor=user))
        for item in list(s1 | s2):
            if item.slug == dataset_name:
                dataset = item
                break
    return dataset and dataset.get_resources() or []


def handle_pust_request(request, dataset_name, resource_id=None):
    # title -> name
    # description -> description
    # language -> lang
    # format -> format_type.pk
    # type -> data_type raw|annexe|service
    # restricted_level -> public|registered|only_allowed_users|same_organization|any_organization
    # restricted_list -> list of: user.username|organisation.slug
    # up_file -> {File}
    user = request.user
    dataset = get_object_or_404_extended(
        Dataset, user, include={'slug': dataset_name})
    resource = None
    if resource_id:
        resource = get_object_or_404(Resource, ckan_id=resource_id)

    # TODO: Vérifier les droits

    data = getattr(request, request.method).dict()

    restricted_list = data.get('restricted_list', [])
    profiles_allowed = None
    organisations_allowed = None

    restricted_level = data.get('restricted_level')
    if restricted_level == 'only_allowed_users':
        profiles_allowed = User.objects.filter(username__in=restricted_list)
    elif restricted_level in ('same_organization', 'any_organization'):
        organisations_allowed = Organisation.objects.filter(slug__in=restricted_list)

    data_form = {
        'title': data.get('title'),
        'description': data.get('description'),
        'lang': data.get('language', 'french'),
        'format_type': data.get('format'),
        'data_type': data.get('type'),
        'restricted_level': restricted_level,
        'profiles_allowed': profiles_allowed,
        'organisations_allowed': organisations_allowed,
        # 'up_file': '',
        # 'dl_url': '',
        # 'synchronisation': '',
        # 'sync_frequency': '',
        # 'referenced_url': '',
        # 'ftp_file': '',
        'crs': data.get('crs', None),
        'encoding': data.get('encoding', None),
        # 'extractable': data.get('extractable'),
        # 'ogc_services': data.get('ogc_services'),
        # 'geo_restriction': data.get('geo_restriction'),
        # 'last_update': data.get('last_update'),
        }

    form = Form(
        data_form, request.FILES,
        instance=resource, dataset=dataset, user=user)
    if not form.is_valid():
        raise GenericException(details=form._errors)

    data = form.cleaned_data
    kvp = {
        'dataset': dataset,
        'title': data['title'],
        'description': data['description'],
        'lang': data['lang'],
        'data_type': data['data_type'],
        'format_type': data['format_type'],
        'last_update': data['last_update'],
        'restricted_level': data['restricted_level'],
        'up_file': data['up_file'],
        # 'dl_url': data['dl_url'],
        # 'synchronisation': data['synchronisation'],
        # 'sync_frequency': data['sync_frequency'],
        # 'referenced_url': data['referenced_url'],
        # 'ftp_file': data['ftp_file'],
        'crs': data['crs'],
        'encoding': data.get('encoding') or None,
        'extractable': data['extractable'],
        'ogc_services': data['ogc_services'],
        'geo_restriction': data['geo_restriction'],
        }

    profiles_allowed = None
    organisations_allowed = None
    if data['restricted_level'] == 'only_allowed_users':
        profiles_allowed = data['profiles_allowed']
    if data['restricted_level'] == 'same_organization':
        organisations_allowed = [form._dataset.organisation]
    if data['restricted_level'] == 'any_organization':
        organisations_allowed = data['organisations_allowed']

    memory_up_file = request.FILES.get('up_file')
    file_extras = memory_up_file and {
        'mimetype': memory_up_file.content_type,
        'resource_type': memory_up_file.name,
        'size': memory_up_file.size} or None

    try:
        with transaction.atomic():
            save_opts = {
                'current_user': user,
                'file_extras': file_extras,
                'synchronize': True}
            if not id:
                resource = Resource.default.create(save_opts=save_opts, **kvp)
            else:
                resource = Resource.objects.get(pk=id)
                for k, v in kvp.items():
                    setattr(resource, k, v)
            if organisations_allowed:
                resource.organisations_allowed = organisations_allowed
            if profiles_allowed:
                resource.profiles_allowed = profiles_allowed
                save_opts['synchronize'] = True
                save_opts['file_extras'] = None  # IMPORTANT
                resource.save(**save_opts)
    except ValidationError as e:
        if e.code == 'crs':
            form.add_error(e.code, '')
            form.add_error('__all__', e.message)
        elif e.code == 'encoding':
            form.add_error(e.code, '')
            form.add_error('__all__', e.message)
        else:
            form.add_error(e.code, e.message)
    except CkanBaseError as e:
        form.add_error('__all__', e.__str__())
    else:
        if resource_id:
            send_resource_update_mail(user, resource)
        else:
            send_resource_creation_mail(user, resource)
        return resource
    raise GenericException(details=form._errors)


class ResourceShow(APIView):

    permission_classes = [
        permissions.IsAuthenticated,
        ]

    def get(self, request, dataset_name, resource_id):
        """Voir la ressource."""
        try:
            resource_id = UUID(resource_id)
        except ValueError:
            raise Http404()
        resources = handler_get_request(request, dataset_name)
        for resource in resources:
            if resource.ckan_id == resource_id:
                return JsonResponse(serialize(resource), safe=True)
        raise Http404()

    def put(self, request, dataset_name, resource_id):
        """Modifier la ressource."""
        # Django fait les choses à moitié...
        request.PUT, request._files = parse_request(request)
        try:
            resource_id = UUID(resource_id)
        except ValueError:
            raise Http404()
        try:
            handle_pust_request(request, dataset_name, resource_id=resource_id)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        return HttpResponse(status=204)

    def delete(self, request, dataset_name, resource_id):
        """Supprimer la ressource."""
        try:
            resource_id = UUID(resource_id)
        except ValueError:
            raise Http404()
        instance = None
        for resource in handler_get_request(request, dataset_name):
            if resource.ckan_id == resource_id:
                instance = resource
                break
        if not instance:
            raise Http404()
        instance.delete(current_user=request.user)
        send_resource_delete_mail(request.user, instance)
        return HttpResponse(status=204)


class ResourceList(APIView):

    permission_classes = [
        permissions.IsAuthenticated,
        ]

    def get(self, request, dataset_name):
        """Voir les ressources du jeu de données."""
        resources = handler_get_request(request, dataset_name)
        return JsonResponse(
            [serialize(resource) for resource in resources], safe=False)

    def post(self, request, dataset_name):
        """Ajouter une ressource au jeu de données."""
        try:
            handle_pust_request(request, dataset_name)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        response = HttpResponse(status=201)
        response['Content-Location'] = ''
        return response
