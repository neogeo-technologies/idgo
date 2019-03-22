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
from django.db.models import Q
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from functools import reduce
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import GenericException
from idgo_admin.forms.account import SignUpForm
from idgo_admin.forms.account import UpdateAccountForm
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from operator import iand
from operator import ior
from rest_framework import permissions
from rest_framework.views import APIView


def serialize(user):

    def nullify(m):
        return m or None

    try:
        return OrderedDict([
            # Information de base sur l'utilisateur
            ('username', user.username),
            ('first_name', user.first_name),
            ('last_name', user.last_name),
            ('admin', user.profile.is_admin),
            ('crige', user.profile.crige_membership),
            # Organisation de rattachement de l'utilisateur
            ('organisation', user.profile.organisation and OrderedDict([
                ('name', user.profile.organisation.slug),
                ('legal_name', user.profile.organisation.legal_name)
                ]) or None),
            # Listes des organisations pour lesquelles l'utilisateur est référent
            ('referent', nullify([OrderedDict([
                ('name', organisation.slug),
                ('legal_name', organisation.legal_name)
                ]) for organisation in user.profile.referent_for])),
            # Listes des organisations pour lesquelles l'utilisateur est contributeur
            ('contribute', nullify([OrderedDict([
                ('name', organisation.slug),
                ('legal_name', organisation.legal_name)
                ]) for organisation in user.profile.contribute_for]))
            ])
    except Exception as e:
        if e.__class__.__name__ == 'RelatedObjectDoesNotExist':
            return None
        raise e


def user_list(order_by='last_name', or_clause=None, **and_clause):

    and_clause.update({'profile__pk__isnull': False})

    l1 = [Q(**{k: v}) for k, v in and_clause.items()]
    if or_clause:
        l2 = [Q(**{k: v}) for k, v in or_clause.items()]
        filter = ior(reduce(iand, l1), reduce(iand, l2))
    else:
        filter = reduce(iand, l1)

    return [serialize(user) for user in User.objects.filter(filter).order_by(order_by)]


def handler_get_request(request):
    qs = request.GET.dict()
    or_clause = dict()

    user = request.user
    if user.profile.is_admin:
        # Un administrateur « métiers » peut tout voir.
        pass
    elif user.profile.is_referent:
        # Un référent « métiers » peut voir les utilisateurs des
        # organisations pour lesquelles il est référent.
        qs.update({'profile__organisation__in': user.profile.referent_for})
        or_clause.update({'username': user.username})
    else:
        # L'utilisateur peut se voir lui même.
        qs.update({'username': user.username})

    return user_list(**qs)


def handle_pust_request(request, username=None):

    user = None
    if username:
        user = get_object_or_404(User, username=username)

    data = getattr(request, request.method).dict()

    organisation = data.get('organisation')
    if organisation:
        try:
            organisation = Organisation.objects.get(slug=organisation).pk
        except Organisation.DoesNotExist:
            details = {'organisation': ["L'organisation n'existe pas."]}
            raise GenericException(details=details)

    data_form = {
        'username': data.get('username'),
        'first_name': data.get('first_name'),
        'last_name': data.get('last_name'),
        'email': data.get('email'),
        'phone': data.get('phone'),
        'organisation': organisation,
        'password1': data.get('password'),
        'password2': data.get('password'),
        }

    if username:
        form = UpdateAccountForm(data_form, instance=user)
    else:
        form = SignUpForm(data_form, unlock_terms=True)
    if not form.is_valid():
        raise GenericException(details=form._errors)
    try:
        with transaction.atomic():
            if username:
                phone = form.cleaned_data.pop('phone', None)
                for k, v in form.cleaned_data.items():
                    setattr(user, k, v)
                user.save()
                if phone:
                    user.profile.phone = phone
                    user.profile.save
                CkanHandler.update_user(user)
            else:
                user = User.objects.create_user(**form.cleaned_user_data)
                profile_data = {**form.cleaned_profile_data, **{'user': user, 'is_active': True}}
                Profile.objects.create(**profile_data)
                CkanHandler.add_user(user, form.cleaned_user_data['password'], state='active')
    except (ValidationError, CkanBaseError) as e:
        raise GenericException(details=e.__str__())

    return user


class UserShow(APIView):

    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
        ]

    def get(self, request, username):
        data = handler_get_request(request)
        for item in data:
            if item['username'] == username:
                return JsonResponse(item, safe=True)
        raise Http404()

    def put(self, request, username):
        """Mettre à jour un utilisateur."""
        request.PUT, request._files = parse_request(request)
        if not request.user.profile.is_admin:
            raise Http404()
        try:
            handle_pust_request(request, username=username)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        return HttpResponse(status=204)


class UserList(APIView):

    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
        ]

    def get(self, request):
        if not hasattr(request.user, 'profile'):
            raise Http404()
        data = handler_get_request(request)
        return JsonResponse(data, safe=False)

    def post(self, request):
        """Créer un utilisateur."""
        if not request.user.profile.is_admin:
            raise Http404()
        try:
            handle_pust_request(request)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        # else:
        response = HttpResponse(status=201)
        response['Content-Location'] = ''
        return response
