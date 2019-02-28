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
from django.db.models import Q
from django.http import Http404
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from functools import reduce
# from idgo_admin.api.utils import BasicAuth
from operator import iand
from operator import ior


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


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]
# decorators = [csrf_exempt, BasicAuth()]


@method_decorator(decorators, name='dispatch')
class UserShow(View):

    def get(self, request, username):
        data = handler_get_request(request)
        for item in data:
            if item['username'] == username:
                return JsonResponse(item, safe=True)
        raise Http404()


@method_decorator(decorators, name='dispatch')
class UserList(View):

    def get(self, request):
        data = handler_get_request(request)
        return JsonResponse(data, safe=False)
