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


import logging

from django.core.management.base import BaseCommand
from django.db import connections

from idgo_admin.models import Resource


from idgo_admin import IDGO_GEOGRAPHIC_LAYER_DB_NAME


logger = logging.getLogger(__name__)


def get_bbox(table_name):

    sql = """
SELECT ST_AsText(ST_Transform(ST_Envelope(ST_Union(ST_Envelope(the_geom))), 4171))
AS table_extent FROM {table_name};
""".format(
        table_name=table_name,
        )

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
        for resource in Resource.objects.all():
            layers = resource.get_layers()
            if layers:
                toggle = False
                for layer in layers:
                    if not layer.type == 'vector':
                        continue
                    bbox = get_bbox(layer.name)
                    layer.bbox = bbox
                    logger.info("Saving Layer %s" % layer.pk)
                    layer.save()
                    toggle = True

                if toggle:
                    logger.info("Saving Resource %s" % resource.pk)
                    resource.save(synchronize=True, skip_download=True)
