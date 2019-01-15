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


from collections import OrderedDict
import csv
from django.conf import settings
from django.contrib.postgres.aggregates import StringAgg
from django.db.models import Case
from django.db.models import CharField
from django.db.models import F
from django.db.models import Func
from django.db.models.functions import Concat
from django.db.models import Q
from django.db.models import Value
from django.db.models import When
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from djqscsv import render_to_csv_response
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.models import Dataset
from idgo_admin.models import Profile
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.views.dataset import get_datasets
from urllib.parse import urljoin
from uuid import UUID


# Définition des champs ODL :
COLL_NOM = F('organisation__name')
COLL_SIRET = Value('', output_field=CharField())
ID = F('ckan_id')
TITRE = F('name')
DESCRIPTION = F('description')
THEME = StringAgg('categories__name', distinct=True, delimiter=';')
DIFFUSEUR = Case(
    When(
        Q(broadcaster_name__isnull=False) & ~Q(broadcaster_name=''),
        then=F('broadcaster_name')),
    When(
        (Q(broadcaster_name__isnull=True) | Q(broadcaster_name='')) & Q(support__isnull=False),
        then=F('support__name')),
    default=Value(settings.DEFAULT_PLATFORM_NAME),
    output_field=CharField())
PRODUCTEUR = F('organisation__name')
COUV_SPAT = Value('', output_field=CharField())
COUV_TEMP_DEBUT = Value('', output_field=CharField())
COUV_TEMP_FIN = Value('', output_field=CharField())
DATE_PUBL = F('date_publication')
FREQ_MAJ = F('update_freq')
DATE_MAJ = F('date_modification')
MOT_CLES = StringAgg('keywords__name', distinct=True, delimiter=';')
LICENCE = F('license__title')
FORMATS = Func(
    StringAgg('resource__format_type__extension', distinct=True, delimiter=';'),
    function='LOWER')
PROJECTION = F('resource__crs__auth_code')
LANG = Value('FR', output_field=CharField())  # StringAgg('resource__lang', distinct=True, delimiter=';')
URL = Concat(
    Value(urljoin(settings.CKAN_URL, 'dataset/')), F('ckan_slug'),
    output_field=CharField())

# Définition des champs DATASUD :
DATASUD_ID = F('ckan_slug')
DATASUD_ORGA_ID = F('organisation__ckan_slug')
DATASUD_ORGA_URL = F('organisation__website')
DATASUD_PRODUCTEUR_NAME = F('owner_name')
DATASUD_PRODUCTEUR_EMAIL = F('owner_email')
DATASUD_DIFFUSEUR_NAME = F('broadcaster_name')
DATASUD_DIFFUSEUR_EMAIL = F('broadcaster_email')
DATASUD_COUV_TERR = F('granularity')
DATASUD_INSPIRE = F('is_inspire')
# DATASUD_DATASET_URL =
# DATASUD_INSPIRE_URL =
# ..un ou plusieurs champs liens vers les APIs à précider.
# ..un ou plusieurs champs statistique à précider.
DATASUD_DATE_CREATION = F('date_creation')
# ..champs import/export (catalogue source, dernier moissonage, etc.)
# DATASUD_RESSOURCE_URLS =
# DATASUD_RESSOURCE_TAILLE =
DATASUD_RESSOURCE_TYPES = FORMATS  # ???


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

        params = request.POST or request.GET

        if not profile:
            ids = params.get('ids', '').split(',')
            qs = Dataset.objects.filter(ckan_id__in=[UUID(id) for id in ids])
        else:
            strict = params.get('mode') == 'all' and False and True
            if not strict:
                roles = profile.get_roles()
                if not roles['is_referent'] and not roles['is_admin']:
                    raise Http404
            qs = get_datasets(profile, params, strict=strict)

        outputformat = params.get('format')
        if not outputformat or outputformat not in ('odl', 'datasud'):
            raise Http404

        if outputformat == 'odl':
            annotate = OrderedDict((
                ('COLL_NOM', COLL_NOM),
                ('COLL_SIRET', COLL_SIRET),
                ('ID', ID),
                ('TITRE', TITRE),
                ('DESCRIPTION', DESCRIPTION),
                ('THEME', THEME),
                ('DIFFUSEUR', DIFFUSEUR),
                ('PRODUCTEUR', PRODUCTEUR),
                ('COUV_SPAT', COUV_SPAT),
                ('COUV_TEMP_DEBUT', COUV_TEMP_DEBUT),
                ('COUV_TEMP_FIN', COUV_TEMP_DEBUT),
                ('DATE_PUBL', DATE_PUBL),
                ('FREQ_MAJ', FREQ_MAJ),
                ('DATE_MAJ', DATE_MAJ),
                ('MOT_CLES', MOT_CLES),
                ('LICENCE', LICENCE),
                ('FORMATS', FORMATS),
                ('PROJECTION', PROJECTION),
                ('LANG', LANG),
                ('URL', URL)
                ))
        else:
            annotate = OrderedDict((
                ('COLL_NOM', COLL_NOM),
                ('COLL_SIRET', COLL_SIRET),
                ('ID', ID),
                ('TITRE', TITRE),
                ('DESCRIPTION', DESCRIPTION),
                ('THEME', THEME),
                ('DIFFUSEUR', DIFFUSEUR),
                ('PRODUCTEUR', PRODUCTEUR),
                ('COUV_SPAT', COUV_SPAT),
                ('COUV_TEMP_DEBUT', COUV_TEMP_DEBUT),
                ('COUV_TEMP_FIN', COUV_TEMP_DEBUT),
                ('DATE_PUBL', DATE_PUBL),
                ('FREQ_MAJ', FREQ_MAJ),
                ('DATE_MAJ', DATE_MAJ),
                ('MOT_CLES', MOT_CLES),
                ('LICENCE', LICENCE),
                ('FORMATS', FORMATS),
                ('PROJECTION', PROJECTION),
                ('LANG', LANG),
                ('URL', URL),
                ('DATASUD_ID', DATASUD_ID),
                # ('DATASUD_MOT_CLES', DATASUD_MOT_CLES),
                # ('DATASUD_ORGA', DATASUD_ORGA),
                ('DATASUD_ORGA_ID', DATASUD_ORGA_ID),
                ('DATASUD_ORGA_URL', DATASUD_ORGA_URL),
                ('DATASUD_PRODUCTEUR_NAME', DATASUD_PRODUCTEUR_NAME),
                ('DATASUD_PRODUCTEUR_EMAIL', DATASUD_PRODUCTEUR_EMAIL),
                ('DATASUD_DIFFUSEUR_NAME', DATASUD_DIFFUSEUR_NAME),
                ('DATASUD_DIFFUSEUR_EMAIL', DATASUD_DIFFUSEUR_EMAIL),
                ('DATASUD_COUV_TERR', DATASUD_COUV_TERR),
                ('DATASUD_INSPIRE', DATASUD_INSPIRE),
                # ('DATASUD_DATASET_URL', DATASUD_DATASET_URL),
                # ('DATASUD_INSPIRE_URL', DATASUD_INSPIRE_URL),
                # ...
                ('DATASUD_DATE_CREATION', DATASUD_DATE_CREATION),
                # ('DATASUD_RESSOURCE_URLS', DATASUD_RESSOURCE_URLS),
                # ('DATASUD_RESSOURCE_TAILLE', DATASUD_RESSOURCE_TAILLE),
                ('DATASUD_RESSOURCE_TYPES', DATASUD_RESSOURCE_TYPES)))

        values = list(annotate.keys())

        return render_to_csv_response(

            qs.annotate(**annotate).values(*values),

            delimiter=';', field_order=values,
            quotechar='"', quoting=csv.QUOTE_ALL)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):
        return self.handle(request, *args, **kwargs)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, *args, **kwargs):
        return self.handle(request, *args, **kwargs)
