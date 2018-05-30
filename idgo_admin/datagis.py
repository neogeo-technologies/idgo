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


import datetime
from django.conf import settings
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.gdal.error import SRSException
from django.db import connections
from idgo_admin.exceptions import NotOGRError
from idgo_admin.exceptions import NotSupportedError
import re
from uuid import uuid4


DATABASE = settings.DATAGIS_DB
OWNER = settings.DATABASES[DATABASE]['USER']
MRA_DATAGIS_USER = settings.MRA['DATAGIS_DB_USER']

SCHEMA = 'public'
THE_GEOM = 'the_geom'

PROJ4_EPSG_FILENAME = settings.PROJ4_EPSG_FILENAME


def retreive_epsg_through_proj4(proj4):
    with open(settings.PROJ4_EPSG_FILENAME) as stream:
        for line in stream:
            if line.find(proj4) > -1:
                res = re.search('<(\d+)>', line)
                if res:
                    return res.group(1)
    raise NotSupportedError('SRS Not found')


class OgrOpener(object):

    VSI_PROTOCOLE = (
        ('zip', 'vsizip'),
        ('tar', 'vsitar'))

    _datastore = None

    def __init__(self, filename, extension=None):
        vsi = dict(self.VSI_PROTOCOLE).get(extension)

        if not vsi:
            raise NotSupportedError(
                "The format '{}' is not supported.".format(extension))

        ds = DataSource('/{}/{}'.format(vsi, filename))
        if not ds:
            raise NotOGRError(
                'The file received is not recognized as being a GIS data.')

        self._datastore = ds

    def get_layers(self):
        yield from self._datastore


CREATE_TABLE = '''
CREATE TABLE {schema}."{table}" (
  fid serial NOT NULL,
  {attrs},
  {the_geom} geometry({geometry}, 4326),
  CONSTRAINT "{table}_pkey" PRIMARY KEY (fid)) WITH (OIDS=FALSE);
ALTER TABLE {schema}."{table}" OWNER TO {owner};
COMMENT ON TABLE {schema}."{table}" IS '{description}';
CREATE UNIQUE INDEX "{table}_fid" ON {schema}."{table}" USING btree (fid);
CREATE INDEX "{table}_gix" ON {schema}."{table}" USING GIST ({the_geom});
GRANT SELECT ON TABLE  {schema}."{table}" TO {mra_datagis_user};
'''


INSERT_INTO = '''
INSERT INTO {schema}."{table}" ({attrs_name}, {the_geom})
VALUES ({attrs_value}, ST_Transform(ST_GeomFromtext('{wkt}', {epsg}), 4326));'''


def ogr_field_2_pg(k, n=None, p=None):
    return {
        'OFTInteger': 'integer',
        'OFTIntegerList': 'integer[]',
        'OFTReal': 'numeric({n}, {p})',
        'OFTRealList': 'numeric({n}, {p})[]',
        'OFTString': 'varchar({n})',
        'OFTStringList': 'varchar({n})[]',
        'OFTWideString': 'text',
        'OFTWideStringList': 'text[]',
        'OFTBinary': 'bytea',
        'OFTDate': 'date',
        'OFTTime': 'time',
        'OFTDateTime': 'datetime',
        'OFTInteger64': 'integer',
        'OFTInteger64List': 'integer[]'}.get(k, 'text').format(n=n, p=p)


def ogr2postgis(filename, extension='zip'):
    ds = OgrOpener(filename, extension='zip')

    sql = []
    table_ids = []
    for layer in ds.get_layers():
        table_id = uuid4()
        table_ids.append(table_id)

        try:
            epsg = layer.srs.identify_epsg()
            if not epsg:
                raise SRSException
        except SRSException:
            epsg = retreive_epsg_through_proj4(layer.srs.proj4)

        attrs = {}
        for i, k in enumerate(layer.fields):
            t = ogr_field_2_pg(
                layer.field_types[i].__qualname__,
                n=layer.field_widths[i],
                p=layer.field_precisions[i])
            attrs[k] = t

        sql.append(CREATE_TABLE.format(
            attrs=',\n  '.join(
                ['{} {}'.format(k, v) for k, v in attrs.items()]),
            description=layer.name,
            epsg=epsg,
            geometry=layer.geom_type,
            owner=OWNER,
            mra_datagis_user=MRA_DATAGIS_USER,
            schema=SCHEMA,
            table=str(table_id),
            the_geom=THE_GEOM))

        for feature in layer:

            attrs = {}
            for field in feature.fields:
                k = field.decode()
                v = feature.get(k)
                if isinstance(v, type(None)):
                    attrs[k] = 'null'
                elif isinstance(v, (datetime.date, datetime.time, datetime.datetime)):
                    attrs[k] = "'{}'".format(v.isoformat())
                elif isinstance(v, str):
                    attrs[k] = "'{}'".format(v.replace("'", "''"))
                else:
                    attrs[k] = "{}".format(v)

            sql.append(INSERT_INTO.format(
                attrs_name=', '.join(attrs.keys()),
                attrs_value=', '.join(attrs.values()),
                epsg=epsg,
                owner=OWNER,
                schema=SCHEMA,
                table=str(table_id),
                the_geom=THE_GEOM,
                wkt=feature.geom))

    with connections[DATABASE].cursor() as cursor:
        for q in sql:
            try:
                cursor.execute(q)
            except Exception as e:
                for table_id in table_ids:
                    drop_table(table_id)
                raise e
        cursor.close()

    return tuple(table_ids)


def drop_table(table, schema=SCHEMA):
    sql = 'DROP TABLE {schema}."{table}";'.format(schema=schema, table=table)
    with connections[DATABASE].cursor() as cursor:
        try:
            cursor.execute(sql)
        except Exception as e:
            if e.__class__.__qualname__ != 'ProgrammingError':
                raise e
        cursor.close()
