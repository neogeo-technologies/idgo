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


from django.conf import settings
from django.db import connections
from idgo_admin.exceptions import NotOGRError
from idgo_admin.exceptions import NotSupportedError
from osgeo import ogr
from uuid import uuid4


COLUMN_TYPE = {}  # TODO
GEOMETRY_TYPE = {}  # TODO

CREATE_TABLE = '''
CREATE TABLE {schema}."{table}"
(
  fid serial NOT NULL,
  {attrs},
  geom geometry({geometry_type}, {epsg}),
  CONSTRAINT "{table}_pkey" PRIMARY KEY (fid)
)
WITH (
  OIDS=FALSE
);
ALTER TABLE {schema}."{table}"
  OWNER TO {owner};
COMMENT ON TABLE {schema}."{table}"
  IS '{description}';
'''

INSERT_INTO = '''
INSERT INTO {schema}."{table}" ({attrs_name}, geom) VALUES ({attrs_value}, ST_GeomFromtext('{wkt}', {epsg}));
'''


def execute_sql(sqls):
    with connections[settings.DATAGIS].cursor() as cursor:
        for sql in sqls:
            cursor.execute(sql)
        cursor.close()


def get_layer_columns(ldefn):
    arr = []
    for k in range(ldefn.GetFieldCount()):
        fdefn = ldefn.GetFieldDefn(k)
        arr.append((fdefn.GetName(), COLUMN_TYPE.get(fdefn.GetType(), 'text')))
    return arr


def ogr_opener(filename, extension='zip'):
    vsi = {'zip': 'vsizip'}.get(extension)  # TODO
    if not vsi:
        raise NotSupportedError(
            "The format '{}' is not supported.".format(extension))

    ds = ogr.Open('/{}/{}'.format(vsi, filename))
    if not ds:
        raise NotOGRError('The file received is not recognized as being a GIS data.')

    sqls = []
    for i in range(ds.GetLayerCount()):
        table = uuid4()

        l = ds.GetLayer(i)
        columns = get_layer_columns(l.GetLayerDefn())
        description = l.GetDescription()

        # fid = l.GetFIDColumn() or 'fid'
        geometry_type = GEOMETRY_TYPE.get(l.GetGeomType(), 'geometry')
        # geom_col = l.GetGeometryColumn()

        sqls.append(CREATE_TABLE.format(
            attrs=',\n  '.join(
                ['{} {}'.format(item[0], item[1]) for item in columns]),
            description=description,
            epsg='4326',
            geometry_type=geometry_type,
            owner='postgres',
            schema='public',
            table=str(table)))

        for j in range(l.GetFeatureCount()):
            ft = l.GetFeature(j)
            sqls.append(INSERT_INTO.format(
                attrs_name=', '.join([item[0] for item in columns]),
                attrs_value=', '.join(
                    ["'{}'".format((ft.GetField(n) or '').replace("'", "''")) for n in range(ft.GetFieldCount())]),
                epsg='4326',  # TODO
                owner='idgo_admin',  # TODO
                schema='public',
                table=str(table),
                wkt=ft.GetGeometryRef().ExportToWkt()))  # TODO -> wkb

    execute_sql(sqls)
