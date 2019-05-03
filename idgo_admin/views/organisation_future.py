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


from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db import transaction
from django.http import Http404
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
import functools
from idgo_admin.ckan_module import CkanBaseHandler
# from idgo_admin.csw_module import CswBaseHandler
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import CswBaseError
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import GenericException
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.organisation import OrganisationForm as Form
from idgo_admin.forms.organisation import RemoteCkanForm
from idgo_admin.forms.organisation import RemoteCswForm
from idgo_admin.models import AccountActions
from idgo_admin.models import Dataset
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models.mail import send_contributor_confirmation_mail
from idgo_admin.models.mail import send_mail_asking_for_crige_partnership
from idgo_admin.models.mail import send_membership_confirmation_mail
from idgo_admin.models.mail import send_organisation_creation_confirmation_mail
from idgo_admin.models.mail import send_referent_confirmation_mail
from idgo_admin.models import Category
from idgo_admin.models import License
from idgo_admin.models import MappingCategory
from idgo_admin.models import MappingLicence
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.models import RemoteCkan
from idgo_admin.models import RemoteCsw
from idgo_admin.models import SupportedCrs
from idgo_admin.mra_client import MRAHandler
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
import operator
from urllib.parse import urljoin


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def handle_show_organisation(request, *args, **kwargs):
    user, profile = user_and_profile(request)

    pk = request.GET.get('id')
    if pk:
        try:
            pk = int(pk)
        except Exception:
            raise Http404()
    else:
        if profile.organisation:
            pk = profile.organisation.pk
        elif profile.is_referent:
            pk = profile.referent_for[0].pk
        elif profile.is_contributor:
            pk = profile.contribute_for[0].pk
    organisation = get_object_or_404(Organisation, pk=pk)
    return redirect(reverse('idgo_admin:show_organisation', kwargs={'id': organisation.id}))


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def show_organisation(request, id, *args, **kwargs):
    user, profile = user_and_profile(request)

    all_organisations = []
    for instance in Organisation.objects.filter(is_active=True):
        all_organisations.append({
            'pk': instance.pk,
            'legal_name': instance.legal_name,
            'member': (instance == profile.organisation),
            'contributor': (instance in profile.contribute_for),
            'referent': profile.is_admin and True or (instance in profile.referent_for),
            })
    all_organisations.sort(key=operator.itemgetter('contributor'), reverse=True)
    all_organisations.sort(key=operator.itemgetter('referent'), reverse=True)
    all_organisations.sort(key=operator.itemgetter('member'), reverse=True)

    organisation = get_object_or_404(Organisation, pk=id)
    context = {
        'all_organisations': all_organisations,
        'organisation': organisation,
        }

    return render_with_info_profile(
        request, 'idgo_admin/organisation/show.html', context=context)
