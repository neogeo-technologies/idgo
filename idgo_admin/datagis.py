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
import re
from uuid import uuid4


DATABASE = settings.DATAGIS_DB
OWNER = settings.DATABASES[DATABASE]['USER']

SCHEMA = 'public'
THE_GEOM = 'the_geom'

PROJ4_EPSG_FILENAME = settings.PROJ4_EPSG_FILENAME


def retreive_epsg(srs):
    if srs.IsGeographic() == 1:
        cs_type = 'GEOGCS'
    elif srs.IsProjected() == 1:
        cs_type = 'PROJCS'

    authority_name = srs.GetAuthorityName(cs_type)
    authority_code = srs.GetAuthorityCode(cs_type)
    if authority_name == 'EPSG' and authority_code:
        return authority_code

    as_proj4 = srs.ExportToProj4()
    if as_proj4:
        with open(settings.PROJ4_EPSG_FILENAME) as stream:
            for line in stream:
                if line.find(as_proj4) > -1:
                    res = re.search('<(\d+)>', line)
                    if res:
                        return res.group(1)


class OgrFeature(object):

    _ft = None

    def __init__(self, ft):
        self._ft = ft

    @property
    def fields(self):
        fields = {}
        for i in range(self._ft.GetFieldCount()):
            fld = self._ft.GetFieldDefnRef(i)
            fields[fld.GetName()] = self._ft.GetField(i)
        return fields

    @property
    def wkt(self):
        return self._ft.GetGeometryRef().ExportToWkt()


class OgrLayer(object):

    COLUMN_TYPE = (  # TODO
        (4, 'text'),)

    GEOMETRY_TYPE = (
        # (0, 'Unknown'),
        (1, 'Point'),
        (2, 'LineString'),
        (3, 'Polygon'),
        (4, 'MultiPoint'),
        (5, 'MULTILINESTRING'),
        (6, 'MultiPolygon'),
        (7, 'GeometryCollection'))

    _epsg = None
    _l = None
    _uuid = uuid4()

    def __init__(self, l):
        self._l = l
        self._epsg = retreive_epsg(self._l.GetSpatialRef())
        if not self._epsg:
            raise NotSupportedError('SRS is not supported.')

    @property
    def columns(self):
        ldefn = self._l.GetLayerDefn()
        arr = []
        for k in range(ldefn.GetFieldCount()):
            fdefn = ldefn.GetFieldDefn(k)
            arr.append((
                fdefn.GetName(),
                dict(self.COLUMN_TYPE).get(fdefn.GetType(), 'text')))
        return tuple(arr)

    @property
    def description(self):
        return self._l.GetDescription()

    @property
    def epsg(self):
        return self._epsg

    @property
    def geometry(self):
        return dict(self.GEOMETRY_TYPE).get(self._l.GetGeomType(), 'GEOMETRY')

    @property
    def table_id(self):
        return self._uuid

    def get_features(self):
        for i in range(self._l.GetFeatureCount()):
            yield OgrFeature(self._l.GetFeature(i))


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

        ds = ogr.Open('/{}/{}'.format(vsi, filename))
        if not ds:
            raise NotOGRError(
                'The file received is not recognized as being a GIS data.')

        self._datastore = ds

    def get_layers(self):
        for i in range(self._datastore.GetLayerCount()):
            yield OgrLayer(self._datastore.GetLayer(i))


CREATE_TABLE = '''
CREATE TABLE {schema}."{table}" (
  fid serial NOT NULL,
  {attrs},
  {the_geom} geometry({geometry}, {epsg}),
  CONSTRAINT "{table}_pkey" PRIMARY KEY (fid)) WITH (OIDS=FALSE);
ALTER TABLE {schema}."{table}" OWNER TO {owner};
COMMENT ON TABLE {schema}."{table}" IS '{description}';
CREATE UNIQUE INDEX "{table}_fid" ON {schema}."{table}" USING btree (fid);
CREATE INDEX "{table}_gix" ON {schema}."{table}" USING GIST ({the_geom});'''


INSERT_INTO = '''
INSERT INTO {schema}."{table}" ({attrs_name}, {the_geom})
VALUES ({attrs_value}, ST_GeomFromtext('{wkt}', {epsg}));'''


def ogr2postgis(filename, extension='zip'):
    ds = OgrOpener(filename, extension='zip')
    sql = []

    table_ids = []
    for layer in ds.get_layers():
        table_ids.append(layer.table_id)

        sql.append(CREATE_TABLE.format(
            attrs=',\n  '.join(
                ['{} {}'.format(item[0], item[1]) for item in layer.columns]),
            description=layer.description,
            epsg=layer.epsg,
            geometry=layer.geometry,
            owner=OWNER,
            schema=SCHEMA,
            table=layer.table_id,
            the_geom=THE_GEOM))

        for feature in layer.get_features():
            sql.append(INSERT_INTO.format(
                attrs_name=', '.join(feature.fields.keys()),
                attrs_value=', '.join([
                    val and "'{}'".format(val.replace("'", "''")) or 'null'
                    for val in feature.fields.values()]),
                epsg=layer.epsg,
                owner=OWNER,
                schema=SCHEMA,
                table=layer.table_id,
                the_geom=THE_GEOM,
                wkt=feature.wkt))

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
