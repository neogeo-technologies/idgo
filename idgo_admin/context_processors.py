# Copyright (c) 2017-2021 Neogeo-Technologies.
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
from django.conf import settings

from idgo_admin import HREF_WWW
from idgo_admin import ENABLE_CSW_HARVESTER
from idgo_admin import ENABLE_CKAN_HARVESTER
from idgo_admin import ENABLE_DCAT_HARVESTER
from idgo_admin import ENABLE_FTP_ACCOUNT
from idgo_admin import ENABLE_ORGANISATION_CREATE
from idgo_admin import DEFAULT_PLATFORM_NAME
from idgo_admin import DEFAULT_CONTACT_EMAIL
from idgo_admin import DISPLAY_FTP_ACCOUNT_MANAGER
from idgo_admin import FTP_PORT
from idgo_admin import FTP_URL
from idgo_admin import READTHEDOC_URL
from idgo_admin import CKAN_URL

from idgo_admin import IDGO_SITE_HEADING_LOGO
from idgo_admin import IDGO_SITE_HEADING_SECOND_LOGO
from idgo_admin import IDGO_SITE_HEADING_TITLE
from idgo_admin import IDGO_EXTRACTOR_SITE_CSS
from idgo_admin import IDGO_EXTRACTOR_SITE_FOOTER
from idgo_admin import IDGO_EXTRACTOR_SITE_HEADING_LOGO
from idgo_admin import IDGO_EXTRACTOR_SITE_HEADING_SECOND_LOGO
from idgo_admin import IDGO_EXTRACTOR_SITE_HEADING_TITLE
from idgo_admin import IDGO_COPYRIGHT
from idgo_admin import IDGO_CMS_LOGIN_URL
from idgo_admin import IDGO_EXPORT_CSV_ODL_EXTENT_LABEL
from idgo_admin import IDGO_ORGANISATION_PARTNER_LABEL
from idgo_admin import IDGO_ORGANISATION_PARTNER_LABEL_PLURAL
from idgo_admin import IDGO_FONCTIONAL_REDUCED_TO_PARTNERS
from idgo_admin import IDGO_CONTRIBUTION_REDUCED_TO_PARTNERS
from idgo_admin import IDGO_USER_PARTNER_LABEL
from idgo_admin import IDGO_USER_PARTNER_LABEL_PLURAL
from idgo_admin import IDGO_EXTRACTOR_CAUTION_MESSAGE


IDGO_MAGIC_ACTIVATE = False
IDGO_LME_ACTIVATE = False
if apps.is_installed('idgo_lme_majic'):
    IDGO_LME_ACTIVATE = getattr(settings, 'IDGO_LME_ACTIVATE', True)
    IDGO_MAJIC_ACTIVATE = getattr(settings, 'IDGO_MAJIC_ACTIVATE', True)

if apps.is_installed('idgo_resource'):
    from idgo_resource.models import Resource as ResourceModel_Beta
    BETA = True
else:
    BETA = False


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
        'ENABLE_RESOURCE_BETA': BETA,
        'HREF_WWW': HREF_WWW,
        'ENABLE_CSW_HARVESTER': ENABLE_CSW_HARVESTER,
        'ENABLE_CKAN_HARVESTER': ENABLE_CKAN_HARVESTER,
        'ENABLE_DCAT_HARVESTER': ENABLE_DCAT_HARVESTER,
        'ENABLE_FTP_ACCOUNT': ENABLE_FTP_ACCOUNT,
        'ENABLE_ORGANISATION_CREATE': ENABLE_ORGANISATION_CREATE,
        'DEFAULT_PLATFORM_NAME': DEFAULT_PLATFORM_NAME,
        'DEFAULT_CONTACT_EMAIL': DEFAULT_CONTACT_EMAIL,
        'DISPLAY_FTP_ACCOUNT_MANAGER': DISPLAY_FTP_ACCOUNT_MANAGER,
        'FTP_PORT': FTP_PORT,
        'FTP_URL': FTP_URL,
        'READTHEDOC_URL': READTHEDOC_URL,
        'CKAN_URL': CKAN_URL,
        'CONTRIBUTOR': contributor,
        'REFERENT': referent,

        'IDGO_SITE_HEADING_LOGO': IDGO_SITE_HEADING_LOGO,
        'IDGO_SITE_HEADING_SECOND_LOGO': IDGO_SITE_HEADING_SECOND_LOGO,
        'IDGO_SITE_HEADING_TITLE': IDGO_SITE_HEADING_TITLE,
        'IDGO_EXTRACTOR_CAUTION_MESSAGE': IDGO_EXTRACTOR_CAUTION_MESSAGE,
        'IDGO_EXTRACTOR_SITE_CSS': IDGO_EXTRACTOR_SITE_CSS,
        'IDGO_EXTRACTOR_SITE_FOOTER': IDGO_EXTRACTOR_SITE_FOOTER,
        'IDGO_EXTRACTOR_SITE_HEADING_LOGO': IDGO_EXTRACTOR_SITE_HEADING_LOGO,
        'IDGO_EXTRACTOR_SITE_HEADING_SECOND_LOGO': IDGO_EXTRACTOR_SITE_HEADING_SECOND_LOGO,
        'IDGO_EXTRACTOR_SITE_HEADING_TITLE': IDGO_EXTRACTOR_SITE_HEADING_TITLE,
        'IDGO_COPYRIGHT': IDGO_COPYRIGHT,
        'IDGO_CMS_LOGIN_URL': IDGO_CMS_LOGIN_URL,
        'IDGO_EXPORT_CSV_ODL_EXTENT_LABEL': IDGO_EXPORT_CSV_ODL_EXTENT_LABEL,
        'IDGO_FONCTIONAL_REDUCED_TO_PARTNERS': IDGO_FONCTIONAL_REDUCED_TO_PARTNERS,
        'IDGO_CONTRIBUTION_REDUCED_TO_PARTNERS': IDGO_CONTRIBUTION_REDUCED_TO_PARTNERS,
        'IDGO_ORGANISATION_PARTNER_LABEL': IDGO_ORGANISATION_PARTNER_LABEL,
        'IDGO_ORGANISATION_PARTNER_LABEL_PLURAL': IDGO_ORGANISATION_PARTNER_LABEL_PLURAL,
        'IDGO_USER_PARTNER_LABEL': IDGO_USER_PARTNER_LABEL,
        'IDGO_USER_PARTNER_LABEL_PLURAL': IDGO_USER_PARTNER_LABEL_PLURAL,

        'IDGO_LME_ACTIVATE': IDGO_LME_ACTIVATE,
        'IDGO_MAJIC_ACTIVATE': IDGO_MAJIC_ACTIVATE,
        }
