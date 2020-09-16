# Copyright (c) 2017-2020 Neogeo-Technologies.
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


from django.apps import apps

from idgo_admin import HREF_WWW
from idgo_admin import ENABLE_CSW_HARVESTER
from idgo_admin import ENABLE_CKAN_HARVESTER
from idgo_admin import ENABLE_DCAT_HARVESTER
from idgo_admin import ENABLE_FTP_ACCOUNT
from idgo_admin import ENABLE_ORGANISATION_CREATE
from idgo_admin import DEFAULT_PLATFORM_NAME
from idgo_admin import DEFAULT_CONTACT_EMAIL
from idgo_admin import DISPLAY_FTP_ACCOUNT_MANAGER
from idgo_admin import FTP_URL
from idgo_admin import READTHEDOC_URL
from idgo_admin import CKAN_URL
from idgo_admin import IDGO_CMS_LOGIN_URL
from idgo_admin import IDGO_REDUCED_TO_PARTNER


def global_vars(request):

    user = request.user
    if user.is_authenticated and hasattr(user, 'profile'):
        Organisation = apps.get_model(app_label='idgo_admin', model_name='Organisation')
        profile = request.user.profile
        contributor = Organisation.extras.get_contribs(
            profile).values_list('pk', 'legal_name')
        referent = Organisation.extras.get_subordinated_organisations(
            profile).values_list('pk', 'legal_name')
    else:
        contributor, referent = [], []

    return {
        'HREF_WWW': HREF_WWW,
        'ENABLE_CSW_HARVESTER': ENABLE_CSW_HARVESTER,
        'ENABLE_CKAN_HARVESTER': ENABLE_CKAN_HARVESTER,
        'ENABLE_DCAT_HARVESTER': ENABLE_DCAT_HARVESTER,
        'ENABLE_FTP_ACCOUNT': ENABLE_FTP_ACCOUNT,
        'ENABLE_ORGANISATION_CREATE': ENABLE_ORGANISATION_CREATE,
        'DEFAULT_PLATFORM_NAME': DEFAULT_PLATFORM_NAME,
        'DEFAULT_CONTACT_EMAIL': DEFAULT_CONTACT_EMAIL,
        'DISPLAY_FTP_ACCOUNT_MANAGER': DISPLAY_FTP_ACCOUNT_MANAGER,
        'FTP_URL': FTP_URL,
        'READTHEDOC_URL': READTHEDOC_URL,
        'CKAN_URL': CKAN_URL,
        'CONTRIBUTOR': contributor,
        'REFERENT': referent,
        'IDGO_CMS_LOGIN_URL': IDGO_CMS_LOGIN_URL,
        'IDGO_REDUCED_TO_PARTNER': IDGO_REDUCED_TO_PARTNER,
    }
