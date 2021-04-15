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


from collections import OrderedDict
import csv
import logging
from operator import ior
import unicodecsv
from urllib.parse import urljoin
from uuid import UUID

from django.contrib.postgres.aggregates import StringAgg
from django.db.models import Case
from django.db.models import CharField
from django.db.models import Count
from django.db.models import F
from django.db.models import Func
from django.db.models.functions import Concat
from django.db.models import Q
from django.db.models import Value
from django.db.models import When
from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View

from idgo_admin.ckan_module import CkanHandler
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.models import Dataset
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Profile
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.views.dataset import get_filtered_datasets

from idgo_admin import CKAN_URL
from idgo_admin import DEFAULT_PLATFORM_NAME
from idgo_admin import IDGO_EXPORT_CSV_ODL_EXTENT_PREFIX


logger = logging.getLogger('idgo_admin')


COLL_NOM = F('organisation__legal_name')
COLL_SIRET = Value('', output_field=CharField())
ID = F('ckan_id')
TITRE = F('title')
DESCRIPTION = F('description')
THEME = StringAgg('categories__name', distinct=True, delimiter=';')
DIFFUSEUR = Case(
    When(
        Q(broadcaster_name__isnull=False) & ~Q(broadcaster_name=''),
        then=F('broadcaster_name')),
    When(
        (Q(broadcaster_name__isnull=True) | Q(broadcaster_name='')) & Q(support__isnull=False),
        then=F('support__name')),
    default=Value(DEFAULT_PLATFORM_NAME),
    output_field=CharField())
PRODUCTEUR_NOM = F('organisation__legal_name')
PRODUCTEUR_SIRET = COLL_SIRET
COUV_SPAT_MAILLE = F('granularity')
COUV_SPAT_NOM = F('geocover')
COUV_TEMP_DEBUT = Value('', output_field=CharField())
COUV_TEMP_FIN = Value('', output_field=CharField())
DATE_PUBL = F('date_publication')
FREQ_MAJ = Case(*[
    When(Q(update_frequency=kvp[0]), then=Value(kvp[1]))
    for kvp in Dataset._meta.get_field('update_frequency').flatchoices],
    default=Value(''),
    output_field=CharField())
DATE_MAJ = F('date_modification')
MOTS_CLES = StringAgg('keywords__name', distinct=True, delimiter=';')
LICENCE = F('license__title')
NOMBRE_RESSOURCES = Count('resource', distinct=True)
FORMAT_RESSOURCES = Func(
    StringAgg('resource__format_type__extension', distinct=True, delimiter=';'),
    function='LOWER')
PROJECTION = StringAgg('resource__crs__auth_code', distinct=True, delimiter=';')
LANG = Value('FR', output_field=CharField())  # StringAgg('resource__lang', distinct=True, delimiter=';')
URL = Concat(
    Value(urljoin(CKAN_URL, 'dataset/')), F('slug'),
    output_field=CharField())


# Définition des champs IDGO (demande initiale de DATASUD)
PREFIX = IDGO_EXPORT_CSV_ODL_EXTENT_PREFIX or 'IDGO'
IDGO_ID = F('slug')
IDGO_ORGA_ID = F('organisation__slug')
IDGO_ORGA_URL = F('organisation__website')
IDGO_PRODUCTEUR_NOM = F('owner_name')
IDGO_DIFFUSEUR_NOM = F('broadcaster_name')
IDGO_DIFFUSEUR_EMAIL = F('broadcaster_email')
IDGO_COUV_TERR = F('granularity')
IDGO_DATE_CREATION = F('date_creation')
IDGO_RESSOURCE_TYPES = FORMAT_RESSOURCES
IDGO_DATASET_VUES = Value('', output_field=CharField())
IDGO_RESSOURCES_TELECHARGEMENT = Value('', output_field=CharField())
IDGO_DATASET_NOTE = Value('', output_field=CharField())
IDGO_DATASET_NB_NOTES = Value('', output_field=CharField())


@method_decorator([csrf_exempt], name='dispatch')
class Export(View):

    def handle(self, request, *args, **kwargs):

        user = request.user
        if user.is_anonymous:
            profile = None
        else:
            try:
                profile = get_object_or_404(Profile, user=user)
            except Exception:
                raise ProfileHttp404

        qs = request.POST or request.GET

        outputformat = qs.get('format')
        if not outputformat or outputformat not in ('odl', 'odl-idgo-extent'):
            logger.error("Export `outputformat` value '%s' is not supported." % outputformat)
            raise Http404()

        if outputformat == 'odl':
            annotate = OrderedDict((
                ('COLL_NOM', COLL_NOM),
                ('COLL_SIRET', COLL_SIRET),
                ('ID', ID),
                ('TITRE', TITRE),
                ('DESCRIPTION', DESCRIPTION),
                ('THEME', THEME),
                # ('DIFFUSEUR', DIFFUSEUR),
                ('PRODUCTEUR_NOM', PRODUCTEUR_NOM),
                ('PRODUCTEUR_SIRET', PRODUCTEUR_SIRET),
                ('COUV_SPAT_MAILLE', COUV_SPAT_MAILLE),
                ('COUV_SPAT_NOM', COUV_SPAT_NOM),
                ('COUV_TEMP_DEBUT', COUV_TEMP_DEBUT),
                ('COUV_TEMP_FIN', COUV_TEMP_DEBUT),
                ('DATE_PUBL', DATE_PUBL),
                ('FREQ_MAJ', FREQ_MAJ),
                ('DATE_MAJ', DATE_MAJ),
                ('MOTS_CLES', MOTS_CLES),
                ('LICENCE', LICENCE),
                ('NOMBRE_RESSOURCES', NOMBRE_RESSOURCES),
                ('FORMAT_RESSOURCES', FORMAT_RESSOURCES),
                # ('PROJECTION', PROJECTION),
                # ('LANG', LANG),
                ('URL', URL)
                ))
        elif outputformat == 'odl-idgo-extent':
            annotate = OrderedDict((
                ('COLL_NOM', COLL_NOM),
                ('COLL_SIRET', COLL_SIRET),
                ('ID', ID),
                ('TITRE', TITRE),
                ('DESCRIPTION', DESCRIPTION),
                ('THEME', THEME),
                ('PRODUCTEUR_NOM', PRODUCTEUR_NOM),
                ('PRODUCTEUR_SIRET', PRODUCTEUR_SIRET),
                ('COUV_SPAT_MAILLE', COUV_SPAT_MAILLE),
                ('COUV_SPAT_NOM', COUV_SPAT_NOM),
                ('COUV_TEMP_DEBUT', COUV_TEMP_DEBUT),
                ('COUV_TEMP_FIN', COUV_TEMP_DEBUT),
                ('DATE_PUBL', DATE_PUBL),
                ('FREQ_MAJ', FREQ_MAJ),
                ('DATE_MAJ', DATE_MAJ),
                ('MOTS_CLES', MOTS_CLES),
                ('LICENCE', LICENCE),
                ('NOMBRE_RESSOURCES', NOMBRE_RESSOURCES),
                ('FORMAT_RESSOURCES', FORMAT_RESSOURCES),
                ('URL', URL),
                ('%s_ID' % PREFIX, IDGO_ID),
                ('%s_ORGA_ID' % PREFIX, IDGO_ORGA_ID),
                ('%s_ORGA_URL' % PREFIX, IDGO_ORGA_URL),
                ('%s_PRODUCTEUR_NOM' % PREFIX, IDGO_PRODUCTEUR_NOM),
                ('%s_DIFFUSEUR_NOM' % PREFIX, IDGO_DIFFUSEUR_NOM),
                ('%s_COUV_TERR' % PREFIX, IDGO_COUV_TERR),
                ('%s_DATE_CREATION' % PREFIX, IDGO_DATE_CREATION),
                ('%s_RESSOURCE_TYPES' % PREFIX, IDGO_RESSOURCE_TYPES),
                ('%s_DATASET_VUES' % PREFIX, IDGO_DATASET_VUES),
                ('%s_RESSOURCES_TELECHARGEMENT' % PREFIX, IDGO_RESSOURCES_TELECHARGEMENT),
                ('%s_DATASET_NOTE' % PREFIX, IDGO_DATASET_NOTE),
                ('%s_DATASET_NB_NOTES' % PREFIX, IDGO_DATASET_NB_NOTES),
                ('DIFFUSEUR', DIFFUSEUR),
                ('PROJECTION', PROJECTION),
                ('LANG', LANG),
                ))
        else:
            raise Http404()

        values = list(annotate.keys())

        if not profile:
            ckan_id__in = []
            for id in qs.get('ids', '').split(','):
                try:
                    ckan_id__in.append(UUID(id))
                except ValueError as e:
                    logger.error("%s: id = `%s`" % (e.__str__(), id))
                    continue
            datasets = Dataset.objects.filter(ckan_id__in=ckan_id__in)

        elif 'mode' in qs:
            mode = qs.get('mode')
            if mode == 'all':
                roles = profile.get_roles()
                if roles['is_admin']:
                    QuerySet = Dataset.default.all()
                elif roles['is_referent']:
                    kwargs = {'profile': profile, 'validated_on__isnull': False}
                    organisation__in = set(
                        instance.organisation for instance
                        in LiaisonsReferents.objects.filter(**kwargs))
                    filter = ior(Q(editor=user), Q(organisation__in=organisation__in))
                    QuerySet = Dataset.default.filter(filter)
            elif mode == 'mine':
                QuerySet = Dataset.default.filter(editor=user)
            elif mode == 'ckan_harvested':
                QuerySet = Dataset.harvested_ckan
            elif mode == 'csw_harvested':
                QuerySet = Dataset.harvested_csw
            elif mode == 'dcat_harvested':
                QuerySet = Dataset.harvested_dcat
            else:
                logger.error("Export `mode` value '%s' is not supported." % mode)
                raise Http404()
            datasets = get_filtered_datasets(QuerySet, qs)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=dataset_export.csv'
        response['Cache-Control'] = 'no-cache'

        writer = unicodecsv.writer(response, encoding='utf-8', quoting=csv.QUOTE_ALL, delimiter=',', quotechar='"')
        writer.writerow(values)
        for row in datasets.annotate(**annotate).values(*values):
            if outputformat == 'odl-idgo-extent':
                dataset_view = 0
                resources_dl = 0
                package = CkanHandler.get_package(str(row['ID']), include_tracking=True)
                if 'tracking_summary' in package:
                    dataset_view = package['tracking_summary'].get('total')
                    resources_dl = package['tracking_summary'].get('download')
                row['%s_DATASET_VUES' % PREFIX] = dataset_view
                row['%s_RESSOURCES_TELECHARGEMENT' % PREFIX] = resources_dl
                row['%s_DATASET_NOTE' % PREFIX] = package.get('rating')
                row['%s_DATASET_NB_NOTES' % PREFIX] = package.get('ratings_count')

            writer.writerow([row[value] for value in values])

        return response

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):
        return self.handle(request, *args, **kwargs)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, *args, **kwargs):
        return self.handle(request, *args, **kwargs)
