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
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import FieldError
# from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponseBadRequest
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from functools import reduce
from idgo_admin.api.utils import pagination_handler
from operator import iand
from operator import ior


def serializer(user):
    nullify = lambda m: m or None
    try:
        return OrderedDict([
            # Information de base sur l'utilisateur
            ('username', user.username),
            ('first_name', user.first_name),
            ('last_name', user.last_name),
            ('admin', user.profile.is_admin),
            ('crige', user.profile.crige_membership),
            # ('email_address', user.email),  # Information privée
            # Organisation de rattachement de l'utilisateur
            ('organisation', user.profile.organisation and OrderedDict([
                ('name', user.profile.organisation.ckan_slug),
                ('legal_name', user.profile.organisation.name)
                ]) or None),
            # Listes des organisations pour lesquelles l'utilisateur est référent
            ('referent', nullify([OrderedDict([
                ('name', organisation.ckan_slug),
                ('legal_name', organisation.name)
                ]) for organisation in user.profile.referent_for])),
            # Listes des organisations pour lesquelles l'utilisateur est contributeur
            ('contribute', nullify([OrderedDict([
                ('name', organisation.ckan_slug),
                ('legal_name', organisation.name)
                ]) for organisation in user.profile.contribute_for]))
            ])
    except Exception as e:
        if e.__class__.__name__ == 'RelatedObjectDoesNotExist':
            return None
        raise e


@pagination_handler
def user_list(i=None, j=None, order_by='last_name', or_clause=None, **and_clause):

    and_clause.update({'profile__pk__isnull': False})

    l1 = [Q(**{k: v}) for k, v in and_clause.items()]
    if or_clause:
        l2 = [Q(**{k: v}) for k, v in or_clause.items()]
        filter = ior(reduce(iand, l1), reduce(iand, l2))
    else:
        filter = reduce(iand, l1)

    return [serializer(user) for user
            in User.objects.filter(filter).order_by(order_by)[i:j]]


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class UserShow(View):

    def get(self, request, username):
        qs = request.GET.dict()

        user = request.user
        if user.username == username:
            # L'utilisateur peut se voir lui même
            qs.update({'username': user.username})
            pass
        elif not user.profile.is_admin:
            # Sinon seuls les administrateurs « métiers » peuvent accéder au service
            raise Http404()  # PermissionDenied()

        try:
            data = user_list(**qs)
        except (FieldError, ValueError):
            return HttpResponseBadRequest()
        else:
            if len(data) == 0:
                raise Http404()
            if len(data) == 1:
                return JsonResponse(data[0], safe=True)
            if len(data) > 1:
                raise HttpResponseBadRequest()


@method_decorator(decorators, name='dispatch')
class UserList(View):

    def get(self, request):
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

        try:
            data = user_list(or_clause=or_clause, **qs)
        except (FieldError, ValueError):
            return HttpResponseBadRequest()
        else:
            return JsonResponse(data, safe=False)
