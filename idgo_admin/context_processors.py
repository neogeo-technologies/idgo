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


from django.conf import settings
from django.apps import apps


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
        'HREF_WWW': getattr(settings, 'HREF_WWW', None),
        'ENABLE_FTP_ACCOUNT': getattr(settings, 'ENABLE_FTP_ACCOUNT', True),
        'DEFAULT_PLATFORM_NAME': getattr(settings, 'DEFAULT_PLATFORM_NAME', 'IDGO'),
        'DEFAULT_CONTACT_EMAIL': getattr(settings, 'DEFAULT_CONTACT_EMAIL', 'contact@idgo.fr'),
        'FTP_URL': getattr(settings, 'FTP_URL', None),
        'READTHEDOC_URL': getattr(settings, 'READTHEDOC_URL', None),
        'CKAN_URL': getattr(settings, 'CKAN_URL', None),
        'CONTRIBUTOR': contributor,
        'REFERENT': referent,
    }
