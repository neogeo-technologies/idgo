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


default_app_config = 'idgo_admin.apps.IdgoAdminConfig'

import logging  # noqa E402
import os  # noqa E402
import sys  # noqa E402
this = sys.modules[__name__]

from django.conf import settings  # noqa E402


logger = logging.getLogger('idgo_admin')


MANDATORY = (
    'CKAN_API_KEY',
    'CKAN_STORAGE_PATH',
    'CKAN_URL',
    'DATABASES',
    'DATAGIS_DB',
    'DEFAULT_USER_ID',
    'DEFAULT_FROM_EMAIL',
    'DEFAULT_FROM_EMAIL',
    'DEFAULTS_VALUES',
    'DOMAIN_NAME',
    'EXTRACTOR_URL',
    'EXTRACTOR_URL_PUBLIC',
    'FTP_DIR',
    'FTP_SERVICE_URL',
    'GEONETWORK_URL',
    'LOGIN_URL',
    'LOGOUT_URL',
    'MAPSERV_STORAGE_PATH',
    'MRA',
    'TERMS_URL',
    'OWS_URL_PATTERN',
    'OWS_PREVIEW_URL',
)

OPTIONAL = (
    ('HREF_WWW', None),
    ('CKAN_TIMEOUT', 36000),
    ('CSW_TIMEOUT', 36000),
    ('DCAT_TIMEOUT', 36000),
    ('DATA_TRANSMISSION_SIZE_LIMITATION', 104857600),
    ('DATAGIS_DB_SCHEMA', 'public'),
    ('DATAGIS_DB_GEOM_FIELD_NAME', 'the_geom'),
    ('DATAGIS_DB_EPSG', 4171),
    ('DEFAULT_PLATFORM_NAME', 'IDGO'),
    ('DEFAULT_CONTACT_EMAIL', 'contact@idgo.fr'),
    ('DISPLAY_FTP_IHM', True),
    ('DOWNLOAD_SIZE_LIMIT', 104857600),
    ('DISPLAY_FTP_ACCOUNT_MANAGER', True),
    ('ENABLE_FTP_ACCOUNT', True),
    ('ENABLE_FTP_INHERENT', False),
    ('ENABLE_ORGANISATION_CREATE', True),
    ('ENABLE_CSW_HARVESTER', True),
    ('ENABLE_CKAN_HARVESTER', True),
    ('ENABLE_DCAT_HARVESTER', False),
    ('EXTRACTOR_BOUNDS', [[40, -14], [55, 28]]),
    ('PHONE_REGEX', '^0\d{9}$'),
    ('FTP_URL', None),
    ('FTP_MECHANISM', 'cgi'),
    ('FTP_MECHANISM', ''),
    ('FTP_UPLOADS_DIR', 'uploads'),
    ('FTP_USER_PREFIX', ''),
    ('GEONETWORK_LOGIN', 'admin'),
    ('GEONETWORK_PASSWORD', 'admin'),
    ('GEONETWORK_TIMEOUT', 36000),
    ('MAPSERV_TIMEOUT', 60),
    ('MDEDIT_HTML_PATH', 'mdedit/html/'),
    ('MDEDIT_CONFIG_PATH', 'mdedit/config/'),
    ('MDEDIT_DATASET_MODEL', 'models/model-dataset-empty.json'),
    ('MDEDIT_SERVICE_MODEL', 'models/model-service-empty.json'),
    ('MDEDIT_LOCALES_PATH', os.path.join(
        settings.BASE_DIR, 'idgo_admin/static/mdedit/config/locales/fr/locales.json')),
    ('REDIS_HOST', 'localhost'),
    ('REDIS_PORT', 6379),
    ('REDIS_EXPIRATION', 120),
    ('READTHEDOC_URL', None),
)


for KEY in MANDATORY:
    try:
        setattr(this, KEY, getattr(settings, KEY))
    except AttributeError as e:
        raise AssertionError("Missing mandatory parameter: %s" % e.__str__())

for KEY, VALUE in OPTIONAL:
    setattr(this, KEY, getattr(settings, KEY, VALUE))

if hasattr(settings, 'STATIC_ROOT'):
    locales_path = os.path.join(
        settings.STATIC_ROOT,
        'mdedit/config/locales/fr/locales.json')
else:
    locales_path = os.path.join(
        settings.BASE_DIR,
        'idgo_admin/static/mdedit/config/locales/fr/locales.json')

try:
    PROTOCOL_CHOICES = []
    with open(locales_path, 'r', encoding='utf-8') as f:
        print("e", f)
        m = json.loads(f.read())
        PROTOCOL_CHOICES = (
            (protocol['id'], protocol['value'])
            for protocol in m['codelists']['MD_LinkageProtocolCode'])
except Exception as e:
    logger.warning(e)
    logger.warning("'PROTOCOL_CHOICES' could not be set.")
finally:
    setattr(this, 'PROTOCOL_CHOICES', PROTOCOL_CHOICES)
