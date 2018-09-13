import logging
import os

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import User
from idgo_admin.models import Resource

AUTHORIZED_PREFIX = ['/maps/', '/wfs/', '/wms/', '/wxs/']

logger = logging.getLogger('auth_ogc')
logger.setLevel(logging.DEBUG)


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
        anonymous = True
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
                logger.error("resource %s not authorized to user %s", resource, user)
                return False
        except:
            logger.error("resource %s not authorized to anonymous", resource)
            return False

    return True
