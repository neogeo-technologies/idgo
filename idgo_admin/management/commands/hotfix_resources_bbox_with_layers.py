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


""" HOTFIX """


import logging

from django.core.management.base import BaseCommand
from django.db import connections

from idgo_admin.models import Resource


from idgo_admin import IDGO_GEOGRAPHIC_LAYER_DB_NAME


logger = logging.getLogger(__name__)


def get_bbox(table_name):

    sql = """
SELECT ST_AsText(ST_Transform(ST_Envelope(ST_Union(ST_Envelope(the_geom))), 4171))
AS table_extent FROM "{table_name}";
""".format(table_name=table_name)

    with connections[IDGO_GEOGRAPHIC_LAYER_DB_NAME].cursor() as cursor:
        try:
            cursor.execute(sql)
        except Exception as e:
            logger.exception(e)
            if e.__class__.__qualname__ != 'ProgrammingError':
                raise e
        else:
            records = cursor.fetchall()
            return records[0][0]


class Command(BaseCommand):

    help = "Fix bbox for Layers instance and Resources instance"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        queryset = Resource.objects.all().order_by('id')
        total = queryset.count()
        count = 0
        for instance in queryset:
            count += 1
            logger.info("[%d/%d] - Checking: %s | %s" % (
                count, total, instance.pk, instance.ckan_url))
            layers = instance.get_layers()
            if layers:
                toggle = False
                for layer in layers:
                    try:
                        if not layer.type == 'vector':
                            continue

                        x_min, y_min, x_max, y_max = layer.bbox.extent
                        if (x_min >= -180 and x_min <= 180) and \
                                (x_max >= -180 and x_max <= 180) and \
                                (y_min >= -90 and y_min <= 90) and \
                                (y_max >= -90 and y_max <= 90):

                            logger.info("[%d/%d] - BBox for %s is OK: %s" % (
                                count, total, layer.pk, str(layer.bbox.extent)))
                            continue

                        logger.warn("[%d/%d] - BBox for %s is not OK: %s" % (
                            count, total, layer.pk, str(layer.bbox.extent)))
                        logger.info("[%d/%d] - Proceed to fix it." % (count, total))

                        bbox = get_bbox(layer.name)
                        layer.bbox = bbox
                        logger.info("[%d/%d] - Saving Layer %s" % (
                            count, total, layer.pk))
                        layer.save()
                        toggle = True
                    except Exception as e:
                        logger.exception(e)
                        logger.error("[%d/%d] - ERROR: %s" % (
                            count, total, e.__str__()))
                        continue

                if toggle:
                    logger.info("[%d/%d] - Saving Resource %s" % (
                        count, total, instance.pk))
                    try:
                        instance.save(synchronize=True, skip_download=False)
                    except Exception as e:
                        logger.exception(e)
                        logger.error("[%d/%d] - ERROR: %s" % (
                            count, total, e.__str__()))
                        continue
