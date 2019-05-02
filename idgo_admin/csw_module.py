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


from django.utils.text import slugify
from functools import wraps
from idgo_admin.exceptions import CswBaseError
from idgo_admin import logger
import inspect
import os
from owslib.csw import CatalogueServiceWeb
from owslib.fes import PropertyIsEqualTo
import re
import timeout_decorator


CSW_TIMEOUT = 36000


def timeout(fun):
    t = CSW_TIMEOUT  # in seconds

    @timeout_decorator.timeout(t, use_signals=False)
    def return_with_timeout(fun, args=tuple(), kwargs=dict()):
        return fun(*args, **kwargs)

    @wraps(fun)
    def wrapper(*args, **kwargs):
        return return_with_timeout(fun, args=args, kwargs=kwargs)

    return wrapper


class CswReadError(CswBaseError):
    message = "L'url ne semble pas indiquer un service CSW."


class CswTimeoutError(CswBaseError):
    message = "Le service CSW met du temps à répondre, celui-ci est peut-être temporairement inaccessible."


class CswError(CswBaseError):
    message = "Une erreur est survenue."


class CswExceptionsHandler(object):

    def __init__(self, ignore=None):
        self.ignore = ignore or []

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):

            root_dir = os.path.dirname(os.path.abspath(__file__))
            info = inspect.getframeinfo(inspect.stack()[1][0])
            logger.debug(
                'Run {} (called by file "{}", line {}, in {})'.format(
                    f.__qualname__,
                    info.filename.replace(root_dir, '.'),
                    info.lineno,
                    info.function))

            try:
                return f(*args, **kwargs)
            except Exception as e:
                logger.exception(e)
                if isinstance(e, timeout_decorator.TimeoutError):
                    raise CswTimeoutError
                if self.is_ignored(e):
                    return f(*args, **kwargs)
                raise CswError(e.__str__())
        return wrapper

    def is_ignored(self, exception):
        return type(exception) in self.ignore


class CswBaseHandler(object):

    def __init__(self, url, username=None, password=None):
        self.url = url
        self.username = username
        self.password = password
        try:
            self.remote = CatalogueServiceWeb(
                self.url, timeout=3600, lang='fr-FR', version='2.0.2',
                skip_caps=True, username=self.username, password=self.password)
        except Exception:
            raise CswReadError()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        # Fake
        logger.info('Close CSW connection')

    @CswExceptionsHandler()
    def get_packages(self, *args, **kwargs):
        self.remote.getrecords2(**kwargs)
        results = self.remote.results.copy()
        records = self.remote.records.copy()

        return [self.get_package(k) for k in list(records.keys())]

    @CswExceptionsHandler()
    def get_package(self, id, *args, **kwargs):

        self.remote.getrecordbyid(
            [id], outputschema='http://www.isotc211.org/2005/gmd')

        records = self.remote.records.copy()

        rec = records[id]

        xml = rec.xml
        if not rec.__class__.__name__ == 'MD_Metadata':
            raise CswBaseError('outputschema error')
        # if not (rec.stdname == 'ISO 19115:2003/19139' and rec.stdver == '1.0'):
        #     raise CswBaseError('outputschema error: stdname:{} stdver:{}'.format(rec.stdname, rec.stdver))
        if not rec.hierarchy == 'dataset':
            raise CswBaseError('Not a Dataset')

        # _encoding = rec.charset

        id = rec.identifier
        title = rec.identification.title
        name = slugify(title)
        notes = description = rec.identification.abstract
        thumbnail = None

        keywords = [k for l in [
            m.keywords for m in rec.identification.keywords2
            if m.__class__.__name__ == 'MD_Keywords']
            for k in l]
        tags = []
        for keyword in keywords:
            keyword_match = re.compile('[\w\s\-.]*$', re.UNICODE)
            if keyword_match.match(keyword):
                tags.append({'display_name': keyword})

        groups = categories = [
            {'name': name} for name in rec.identification.topiccategory]

        dataset_creation_date = date_creation = None
        dataset_modification_date = date_modification = None
        dataset_publication_date = date_publication = None
        if rec.identification.date:
            for item in rec.identification.date:
                if not item.__class__.__name__ == 'CI_Date':
                    continue
                if item.type == 'creation':
                    dataset_creation_date = item.date
                elif item.type == 'publication':
                    dataset_publication_date = item.date
                elif item.type == 'modification':
                    dataset_modification_date = item.date

        frequency = update_frequency = None
        geocover = None
        granularity = None
        organisation = {
            'id': None,
            'name': None,
            'title': None,
            'description': None,
            'created': None,
            'is_organization': True,
            'state': 'active',
            'image_url': None,
            'type': 'organization',
            'approval_status': 'approved',
            }

        license_id = None
        license_title = None

        support = None
        data_type = None
        author = owner_name = None
        author_email = owner_email = None
        maintainer = None
        maintainer_email = None

        bbox = None
        if rec.identification.bbox:
            bbox = {
                'type': 'Polygon',
                'coordinates': [
                    [
                        [
                            rec.identification.bbox.minx,
                            rec.identification.bbox.miny
                            ],
                        [
                            rec.identification.bbox.maxx,
                            rec.identification.bbox.miny
                            ],
                        [
                            rec.identification.bbox.maxx,
                            rec.identification.bbox.maxy
                            ],
                        [
                            rec.identification.bbox.minx,
                            rec.identification.bbox.maxy
                            ],
                        [
                            rec.identification.bbox.minx,
                            rec.identification.bbox.miny
                            ],
                        ],
                    ]
                }

        resources = []
        for item in rec.distribution.online:
            resource = {
                'name': item.name,
                'description': item.description,
                'protocol': item.protocol,
                'mimetype': item.mimetype,
                'url': item.url,
                }
            resources.append(resource)

        return {
            'state': 'active',
            'type': 'dataset',
            'id': id,
            'name': name,
            'title': title,
            'notes': notes,
            'thumbnail': thumbnail,
            'num_tags': len(tags),
            'tags': tags,
            'groups': groups,
            'metadata_created': dataset_creation_date,
            'metadata_modified': dataset_modification_date,
            'dataset_creation_date': dataset_creation_date,
            'dataset_modification_date': dataset_modification_date,
            'dataset_publication_date': dataset_publication_date,
            'frequency': frequency,
            'geocover': geocover,
            'granularity': granularity,
            'organization': organisation,
            'license_id': license_id,
            'license_title': license_title,
            'support': support,
            'datatype': data_type,
            'author': author,
            'author_email': author_email,
            'maintainer': maintainer,
            'maintainer_email': maintainer_email,
            'num_resources': len(resources),
            'resources': resources,
            'spatial': bbox,
            }
