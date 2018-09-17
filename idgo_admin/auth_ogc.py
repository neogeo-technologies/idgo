# Copyright (c) 2017-2018 Datasud.
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


import os
import logging

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import User  # noqa: E402
from idgo_admin.models import Resource  # noqa: E402

logger = logging.getLogger('auth_ogc')
logger.setLevel(logging.DEBUG)

AUTHORIZED_PREFIX = ['/maps/', '/wfs/', '/wms/', '/wxs/']


def check_password(environ, user, password):

    url = environ['REQUEST_URI']

    logger.debug('Checking user %s rights to url %s', user, url)

    # check path is authorized

    is_path_authorized = False
    for prefix in AUTHORIZED_PREFIX:
        if url.startswith(prefix):
            is_path_authorized = True

    if not is_path_authorized:
        logger.error("path '%s' is unauthorized", url)
        return False

    try:
        user = User.objects.get(username=user, is_active=True)
    except User.DoesNotExist:
        logger.debug("User %s does not exist (or is not active :()" % user)
    else:
        if not user.check_password(password):
            logger.error("User %s provided bad password", user)
            return False

    try:
        resources = Resource.get_resources_by_mapserver_url(url)
    except Exception as e:
        logger.debug(" unable to get ressources: %s", e)
        return True

    # refuse query if one of the resources is not available/authorized
    for resource in resources:
        if resource.anonymous_access:
            continue

        try:
            if not resource.is_profile_authorized(user):
                logger.error("resource %s not authorized to user %s",
                             resource,
                             user)
                return False
        except Exception:
            logger.error("resource %s not authorized to anonymous", resource)
            return False

    return True
