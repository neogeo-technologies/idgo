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


default_app_config = 'sid.apps.SidConfig'


from django.conf import settings  # noqa E402


try:
    CKAN_URL = getattr(settings, 'CKAN_URL')
    SSO_LOGOUT_URL = getattr(settings, 'SSO_LOGOUT_URL')
    VIEWERSTUDIO_URL = getattr(settings, 'VIEWERSTUDIO_URL')
except AttributeError as e:
    raise AssertionError("Missing mandatory parameter: %s" % e.__str__())

HEADER_UID = getattr(settings, 'HEADER_UID', 'OIDC_CLAIM_uid')
OIDC_SETTED = getattr(settings, 'OIDC_SETTED', False)


__all__ = [
    CKAN_URL,
    HEADER_UID,
    OIDC_SETTED,
    SSO_LOGOUT_URL,
    VIEWERSTUDIO_URL,
]
